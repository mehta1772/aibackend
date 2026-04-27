
# """
# Documents Router
# Handles document management with 5-stage pipeline
# Storage: AWS S3
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Form
# from datetime import datetime
# from bson import ObjectId
# from typing import Optional, List

# from app.models.schemas import DocumentStage, UserRole
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user, require_admin
# from app.utils.s3_service import upload_document, delete_document, get_presigned_url

# router = APIRouter()

# STAGES = ["Agreement", "Pitch Deck", "DPR", "Application", "Others"]

# @router.get("/bookings")
# async def get_bookings_with_documents(
#     search: Optional[str] = Query(None, description="Search company name or mobile"),
#     service: Optional[str] = Query(None, description="Filter by service"),
#     start_date: Optional[datetime] = Query(None),
#     end_date: Optional[datetime] = Query(None),
#     # Individual stage filters (completed/pending)
#     agreement_status: Optional[str] = Query(None, description="completed or pending"),
#     pitchdeck_status: Optional[str] = Query(None, description="completed or pending"),
#     dpr_status: Optional[str] = Query(None, description="completed or pending"),
#     application_status: Optional[str] = Query(None, description="completed or pending"),
#     others_status: Optional[str] = Query(None, description="completed or pending"),
#     # Quick filters
#     doc_status: Optional[str] = Query(None, description="all_complete, any_pending, any_overdue"),
#     page: int = Query(1, ge=1),
#     page_size: int = Query(100, ge=1, le=1000),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all bookings with document status - FAST VERSION with overdue tracking"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     # Build query
#     query = {"isDeleted": False}
    
#     # Search by company name OR mobile number
#     if search:
#         search_term = search.strip()
#         # Remove any non-digit characters for phone matching
#         search_digits = ''.join(c for c in search_term if c.isdigit())
        
#         search_conditions = [
#             {"company_name": {"$regex": search_term, "$options": "i"}},
#         ]
        
#         # Add contact_no search conditions
#         # Handle both string and numeric contact_no fields
#         if search_digits:
#             # For string field - regex match
#             search_conditions.append({"contact_no": {"$regex": search_digits, "$options": "i"}})
#             # For numeric field - try exact match or convert to regex on string version
#             try:
#                 search_conditions.append({"contact_no": int(search_digits)})
#             except:
#                 pass
#             # Also try partial match by converting to string in aggregation
#             search_conditions.append({"$expr": {"$regexMatch": {"input": {"$toString": "$contact_no"}, "regex": search_digits, "options": "i"}}})
        
#         query["$or"] = search_conditions
    
#     if service:
#         query["services"] = service
    
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     # Get total count before stage filtering
#     total_before_filter = await bookings_collection.count_documents(query)
    
#     # Get all bookings (we'll filter by stage status in memory for speed)
#     cursor = bookings_collection.find(query).sort("date", -1)
    
#     # Get all bookings first
#     booking_list = []
#     booking_ids = []
#     now = datetime.utcnow()
    
#     async for booking in cursor:
#         booking_id = str(booking["_id"])
#         booking_ids.append(booking_id)
        
#         term_1 = booking.get("term_1") or 0
#         term_2 = booking.get("term_2") or 0
#         term_3 = booking.get("term_3") or 0
#         received_amount = term_1 + term_2 + term_3
        
#         # Calculate days since booking
#         booking_date = booking.get("date") or booking.get("createdAt") or now
#         if isinstance(booking_date, str):
#             try:
#                 booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
#             except:
#                 booking_date = now
#         days_since_booking = (now - booking_date).days
        
#         booking_list.append({
#             "id": booking_id,
#             "company_name": booking.get("company_name", ""),
#             "contact_person": booking.get("contact_person", ""),
#             "contact_no": str(booking.get("contact_no", "")),
#             "email": booking.get("email", ""),
#             "services": booking.get("services", []),
#             "total_amount": booking.get("total_amount", 0),
#             "term_1": term_1,
#             "term_2": term_2,
#             "term_3": term_3,
#             "received_amount": received_amount,
#             "status": booking.get("status", "Pending"),
#             "bdm": booking.get("bdm", ""),
#             "date": booking.get("date"),
#             "days_since_booking": days_since_booking,
#             "document_stages": {s: 0 for s in STAGES},
#             "overdue_stages": {},
#             "total_documents": 0,
#             "all_complete": False
#         })
    
#     # Get document counts in ONE aggregation query
#     if booking_ids:
#         doc_pipeline = [
#             {"$match": {"booking_id": {"$in": booking_ids}}},
#             {"$group": {
#                 "_id": {"booking_id": "$booking_id", "stage": "$stage"},
#                 "count": {"$sum": 1}
#             }}
#         ]
#         doc_counts = await documents_collection.aggregate(doc_pipeline).to_list(None)
        
#         # Map counts to bookings
#         count_map = {}
#         for dc in doc_counts:
#             bid = dc["_id"]["booking_id"]
#             stage = dc["_id"]["stage"]
#             count = dc["count"]
#             if bid not in count_map:
#                 count_map[bid] = {}
#             count_map[bid][stage] = count
        
#         # Update booking list with document counts and overdue status
#         for booking in booking_list:
#             if booking["id"] in count_map:
#                 for stage, count in count_map[booking["id"]].items():
#                     if stage in booking["document_stages"]:
#                         booking["document_stages"][stage] = count
#                 booking["total_documents"] = sum(booking["document_stages"].values())
            
#             # Calculate overdue status for each stage
#             days = booking["days_since_booking"]
#             for stage in STAGES:
#                 has_doc = booking["document_stages"].get(stage, 0) > 0
#                 if stage == "Agreement":
#                     booking["overdue_stages"][stage] = not has_doc and days > 6
#                 else:
#                     booking["overdue_stages"][stage] = not has_doc and days > 25
            
#             # Check if all stages are complete
#             booking["all_complete"] = all(
#                 booking["document_stages"].get(s, 0) > 0 for s in STAGES
#             )
    
#     # Apply individual stage filters (combination filters)
#     filtered_list = booking_list
    
#     if agreement_status:
#         if agreement_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Agreement", 0) > 0]
#         elif agreement_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Agreement", 0) == 0]
    
#     if pitchdeck_status:
#         if pitchdeck_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Pitch Deck", 0) > 0]
#         elif pitchdeck_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Pitch Deck", 0) == 0]
    
#     if dpr_status:
#         if dpr_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("DPR", 0) > 0]
#         elif dpr_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("DPR", 0) == 0]
    
#     if application_status:
#         if application_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Application", 0) > 0]
#         elif application_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Application", 0) == 0]
    
#     if others_status:
#         if others_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Others", 0) > 0]
#         elif others_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Others", 0) == 0]
    
#     # Apply quick doc_status filter
#     if doc_status:
#         if doc_status == "all_complete":
#             filtered_list = [b for b in filtered_list if b["all_complete"]]
#         elif doc_status == "any_pending":
#             filtered_list = [b for b in filtered_list if not b["all_complete"]]
#         elif doc_status == "any_overdue":
#             filtered_list = [b for b in filtered_list if any(b["overdue_stages"].values())]
    
#     # Apply pagination after filtering
#     total = len(filtered_list)
#     skip = (page - 1) * page_size
#     paginated_list = filtered_list[skip:skip + page_size]
    
#     return {
#         "items": paginated_list,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
#     }

# @router.get("/booking/{booking_id}")
# async def get_booking_documents(
#     booking_id: str,
#     stage: Optional[str] = Query(None),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all documents for a specific booking"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid booking ID")
    
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
    
#     query = {"booking_id": booking_id}
#     if stage:
#         query["stage"] = stage
    
#     cursor = documents_collection.find(query).sort("uploaded_at", -1)
    
#     documents = []
#     async for doc in cursor:
#         # Get presigned URL for secure access
#         presigned_url = await get_presigned_url(doc["file_url"])
        
#         documents.append({
#             "id": str(doc["_id"]),
#             "booking_id": doc["booking_id"],
#             "stage": doc["stage"],
#             "file_name": doc["file_name"],
#             "file_url": presigned_url or doc["file_url"],
#             "uploaded_by": doc["uploaded_by"],
#             "uploaded_by_name": doc["uploaded_by_name"],
#             "uploaded_at": doc["uploaded_at"]
#         })
    
#     # Group by stage
#     by_stage = {s: [] for s in STAGES}
#     for doc in documents:
#         if doc["stage"] in by_stage:
#             by_stage[doc["stage"]].append(doc)
    
#     return {
#         "booking": {
#             "id": str(booking["_id"]),
#             "company_name": booking.get("company_name", ""),
#             "services": booking.get("services", [])
#         },
#         "documents": documents,
#         "by_stage": by_stage
#     }

# @router.post("/upload")
# async def upload_booking_document(
#     booking_id: str = Form(...),
#     stage: str = Form(...),
#     file: UploadFile = File(...),
#     current_user: dict = Depends(require_admin)
# ):
#     """Upload document for a booking stage"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     # Validate stage
#     if stage not in STAGES:
#         raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {STAGES}")
    
#     # Verify booking exists
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid booking ID")
    
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
    
#     # Read file content
#     file_content = await file.read()
    
#     # Upload to S3
#     file_url = await upload_document(
#         file_content=file_content,
#         file_name=file.filename,
#         booking_id=booking_id,
#         stage=stage,
#         content_type=file.content_type
#     )
    
#     if not file_url:
#         raise HTTPException(status_code=500, detail="Failed to upload document")
    
#     # Save document record
#     document = {
#         "booking_id": booking_id,
#         "stage": stage,
#         "file_name": file.filename,
#         "file_url": file_url,
#         "file_size": len(file_content),
#         "content_type": file.content_type,
#         "uploaded_by": current_user["id"],
#         "uploaded_by_name": current_user["name"],
#         "uploaded_at": datetime.utcnow()
#     }
    
#     result = await documents_collection.insert_one(document)
    
#     return {
#         "id": str(result.inserted_id),
#         "file_name": file.filename,
#         "file_url": file_url,
#         "stage": stage,
#         "message": "Document uploaded successfully"
#     }

# @router.delete("/{document_id}")
# async def delete_booking_document(document_id: str, current_user: dict = Depends(require_admin)):
#     """Delete a document"""
#     documents_collection = get_collection("documents")
    
#     try:
#         document = await documents_collection.find_one({"_id": ObjectId(document_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid document ID")
    
#     if not document:
#         raise HTTPException(status_code=404, detail="Document not found")
    
#     # Delete from S3
#     await delete_document(document["file_url"])
    
#     # Delete from database
#     await documents_collection.delete_one({"_id": ObjectId(document_id)})
    
#     return {"message": "Document deleted successfully"}

# @router.get("/analytics")
# async def get_document_analytics(current_user: dict = Depends(require_admin)):
#     """Get document analytics - count per stage"""
#     documents_collection = get_collection("documents")
#     bookings_collection = get_collection("bookings")
    
#     total_bookings = await bookings_collection.count_documents({"isDeleted": False})
    
#     analytics = []
#     for stage in STAGES:
#         # Count documents in this stage
#         doc_count = await documents_collection.count_documents({"stage": stage})
        
#         # Count unique bookings with documents in this stage
#         pipeline = [
#             {"$match": {"stage": stage}},
#             {"$group": {"_id": "$booking_id"}},
#             {"$count": "total"}
#         ]
#         result = await documents_collection.aggregate(pipeline).to_list(1)
#         bookings_with_docs = result[0]["total"] if result else 0
        
#         analytics.append({
#             "stage": stage,
#             "total_documents": doc_count,
#             "bookings_with_documents": bookings_with_docs,
#             "completion_percentage": round((bookings_with_docs / total_bookings) * 100, 1) if total_bookings > 0 else 0
#         })
    
#     return {
#         "total_bookings": total_bookings,
#         "stages": analytics
#     }

# @router.get("/stage/{stage}")
# async def get_documents_by_stage(
#     stage: str,
#     page: int = Query(1, ge=1),
#     page_size: int = Query(20, ge=1, le=100),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all documents for a specific stage"""
#     if stage not in STAGES:
#         raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {STAGES}")
    
#     documents_collection = get_collection("documents")
#     bookings_collection = get_collection("bookings")
    
#     total = await documents_collection.count_documents({"stage": stage})
    
#     skip = (page - 1) * page_size
#     cursor = documents_collection.find({"stage": stage}).skip(skip).limit(page_size).sort("uploaded_at", -1)
    
#     documents = []
#     async for doc in cursor:
#         # Get booking info
#         try:
#             booking = await bookings_collection.find_one({"_id": ObjectId(doc["booking_id"])})
#             company_name = booking.get("company_name", "Unknown") if booking else "Unknown"
#         except:
#             company_name = "Unknown"
        
#         presigned_url = await get_presigned_url(doc["file_url"])
        
#         documents.append({
#             "id": str(doc["_id"]),
#             "booking_id": doc["booking_id"],
#             "company_name": company_name,
#             "file_name": doc["file_name"],
#             "file_url": presigned_url or doc["file_url"],
#             "uploaded_by_name": doc["uploaded_by_name"],
#             "uploaded_at": doc["uploaded_at"]
#         })
    
#     return {
#         "stage": stage,
#         "items": documents,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
#     }

# # ==================== NOTES ENDPOINTS ====================

# @router.get("/notes/{booking_id}")
# async def get_booking_notes(
#     booking_id: str,
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all notes for a booking"""
#     notes_collection = get_collection("booking_notes")
    
#     cursor = notes_collection.find({"booking_id": booking_id}).sort("created_at", -1)
    
#     notes = []
#     async for note in cursor:
#         notes.append({
#             "id": str(note["_id"]),
#             "booking_id": note["booking_id"],
#             "content": note["content"],
#             "created_by": note["created_by"],
#             "created_by_name": note["created_by_name"],
#             "created_at": note["created_at"],
#             "updated_at": note.get("updated_at")
#         })
    
#     return {"notes": notes}

# @router.post("/notes")
# async def create_booking_note(
#     data: dict,
#     current_user: dict = Depends(require_admin)
# ):
#     """Create a new note for a booking"""
#     booking_id = data.get("booking_id")
#     content = data.get("content", "")
    
#     if not booking_id:
#         raise HTTPException(status_code=400, detail="booking_id is required")
#     if not content or not content.strip():
#         raise HTTPException(status_code=400, detail="Note content cannot be empty")
    
#     notes_collection = get_collection("booking_notes")
#     bookings_collection = get_collection("bookings")
    
#     # Verify booking exists
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#         if not booking:
#             raise HTTPException(status_code=404, detail="Booking not found")
#     except:
#         raise HTTPException(status_code=400, detail="Invalid booking ID")
    
#     note = {
#         "booking_id": booking_id,
#         "content": content.strip(),
#         "created_by": current_user["id"],
#         "created_by_name": current_user["name"],
#         "created_at": datetime.utcnow(),
#     }
    
#     result = await notes_collection.insert_one(note)
    
#     return {
#         "id": str(result.inserted_id),
#         "message": "Note created successfully"
#     }

# @router.put("/notes/{note_id}")
# async def update_booking_note(
#     note_id: str,
#     data: dict,
#     current_user: dict = Depends(require_admin)
# ):
#     """Update an existing note"""
#     content = data.get("content", "")
    
#     if not content or not content.strip():
#         raise HTTPException(status_code=400, detail="Note content cannot be empty")
    
#     notes_collection = get_collection("booking_notes")
    
#     try:
#         result = await notes_collection.update_one(
#             {"_id": ObjectId(note_id)},
#             {"$set": {
#                 "content": content.strip(),
#                 "updated_at": datetime.utcnow()
#             }}
#         )
#     except:
#         raise HTTPException(status_code=400, detail="Invalid note ID")
    
#     if result.matched_count == 0:
#         raise HTTPException(status_code=404, detail="Note not found")
    
#     return {"message": "Note updated successfully"}

# @router.delete("/notes/{note_id}")
# async def delete_booking_note(
#     note_id: str,
#     current_user: dict = Depends(require_admin)
# ):
#     """Delete a note"""
#     notes_collection = get_collection("booking_notes")
    
#     try:
#         result = await notes_collection.delete_one({"_id": ObjectId(note_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid note ID")
    
#     if result.deleted_count == 0:
#         raise HTTPException(status_code=404, detail="Note not found")
    
#     return {"message": "Note deleted successfully"}

# # ============================================
# # ADMIN UPLOAD ACTIVITY TRACKING
# # ============================================

# @router.get("/admin-activity")
# async def get_admin_upload_activity(
#     start_date: Optional[datetime] = Query(None, description="Start date filter"),
#     end_date: Optional[datetime] = Query(None, description="End date filter"),
#     admin_id: Optional[str] = Query(None, description="Filter by specific admin"),
#     current_user: dict = Depends(require_admin)
# ):
#     """
#     Get admin document upload activity summary
#     Shows how many documents each admin uploaded per day
#     """
#     documents_collection = get_collection("documents")
#     users_collection = get_collection("users")
    
#     # Build date filter
#     date_filter = {}
#     if start_date:
#         date_filter["$gte"] = start_date
#     if end_date:
#         # Set end_date to end of day
#         end_of_day = end_date.replace(hour=23, minute=59, second=59)
#         date_filter["$lte"] = end_of_day
    
#     # Build query
#     query = {}
#     if date_filter:
#         query["uploaded_at"] = date_filter
#     if admin_id:
#         query["uploaded_by"] = admin_id
    
#     # Aggregate by admin and date
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {
#                 "admin_id": "$uploaded_by",
#                 "admin_name": "$uploaded_by_name",
#                 "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$uploaded_at"}},
#                 "stage": "$stage"
#             },
#             "count": {"$sum": 1}
#         }},
#         {"$sort": {"_id.date": -1, "_id.admin_name": 1}}
#     ]
    
#     results = await documents_collection.aggregate(pipeline).to_list(1000)
    
#     # Organize data by date and admin
#     activity_by_date = {}
#     admin_totals = {}
    
#     for item in results:
#         date = item["_id"]["date"]
#         admin_name = item["_id"]["admin_name"]
#         admin_id = item["_id"]["admin_id"]
#         stage = item["_id"]["stage"]
#         count = item["count"]
        
#         # By date
#         if date not in activity_by_date:
#             activity_by_date[date] = {}
        
#         if admin_name not in activity_by_date[date]:
#             activity_by_date[date][admin_name] = {
#                 "admin_id": admin_id,
#                 "admin_name": admin_name,
#                 "total": 0,
#                 "by_stage": {}
#             }
        
#         activity_by_date[date][admin_name]["total"] += count
#         activity_by_date[date][admin_name]["by_stage"][stage] = count
        
#         # Admin totals
#         if admin_name not in admin_totals:
#             admin_totals[admin_name] = {
#                 "admin_id": admin_id,
#                 "admin_name": admin_name,
#                 "total": 0,
#                 "by_stage": {}
#             }
#         admin_totals[admin_name]["total"] += count
#         if stage not in admin_totals[admin_name]["by_stage"]:
#             admin_totals[admin_name]["by_stage"][stage] = 0
#         admin_totals[admin_name]["by_stage"][stage] += count
    
#     # Convert to list format
#     daily_activity = []
#     for date, admins in sorted(activity_by_date.items(), reverse=True):
#         daily_activity.append({
#             "date": date,
#             "admins": list(admins.values()),
#             "total": sum(a["total"] for a in admins.values())
#         })
    
#     return {
#         "daily_activity": daily_activity,
#         "admin_totals": list(admin_totals.values()),
#         "stages": STAGES
#     }

# @router.get("/admin-activity/details")
# async def get_admin_upload_details(
#     date: str = Query(..., description="Date in YYYY-MM-DD format"),
#     admin_id: Optional[str] = Query(None, description="Filter by specific admin"),
#     stage: Optional[str] = Query(None, description="Filter by document stage"),
#     current_user: dict = Depends(require_admin)
# ):
#     """
#     Get detailed list of documents uploaded by admins on a specific date
#     Shows booking details for each upload
#     """
#     documents_collection = get_collection("documents")
#     bookings_collection = get_collection("bookings")
    
#     # Parse date
#     try:
#         target_date = datetime.strptime(date, "%Y-%m-%d")
#         next_date = target_date.replace(hour=23, minute=59, second=59)
#     except:
#         raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
#     # Build query
#     query = {
#         "uploaded_at": {"$gte": target_date, "$lte": next_date}
#     }
#     if admin_id:
#         query["uploaded_by"] = admin_id
#     if stage:
#         query["stage"] = stage
    
#     # Get documents
#     cursor = documents_collection.find(query).sort("uploaded_at", -1)
    
#     documents = []
#     booking_ids = set()
    
#     async for doc in cursor:
#         booking_ids.add(doc["booking_id"])
#         documents.append({
#             "id": str(doc["_id"]),
#             "booking_id": doc["booking_id"],
#             "stage": doc["stage"],
#             "file_name": doc["file_name"],
#             "uploaded_by": doc["uploaded_by"],
#             "uploaded_by_name": doc["uploaded_by_name"],
#             "uploaded_at": doc["uploaded_at"]
#         })
    
#     # Get booking details
#     bookings_map = {}
#     if booking_ids:
#         cursor = bookings_collection.find(
#             {"_id": {"$in": [ObjectId(bid) for bid in booking_ids]}},
#             {"company_name": 1, "contact_person": 1, "services": 1, "bdm": 1}
#         )
#         async for booking in cursor:
#             bookings_map[str(booking["_id"])] = {
#                 "company_name": booking.get("company_name", ""),
#                 "contact_person": booking.get("contact_person", ""),
#                 "services": booking.get("services", []),
#                 "bdm": booking.get("bdm", "")
#             }
    
#     # Attach booking info to documents
#     for doc in documents:
#         doc["booking"] = bookings_map.get(doc["booking_id"], {})
    
#     # Group by admin
#     by_admin = {}
#     for doc in documents:
#         admin_name = doc["uploaded_by_name"]
#         if admin_name not in by_admin:
#             by_admin[admin_name] = {
#                 "admin_name": admin_name,
#                 "admin_id": doc["uploaded_by"],
#                 "uploads": [],
#                 "total": 0
#             }
#         by_admin[admin_name]["uploads"].append(doc)
#         by_admin[admin_name]["total"] += 1
    
#     return {
#         "date": date,
#         "admins": list(by_admin.values()),
#         "total_uploads": len(documents)
#     }

# @router.get("/admin-list")
# async def get_document_admins(current_user: dict = Depends(require_admin)):
#     """Get list of admins who have uploaded documents"""
#     documents_collection = get_collection("documents")
    
#     pipeline = [
#         {"$group": {
#             "_id": {
#                 "admin_id": "$uploaded_by",
#                 "admin_name": "$uploaded_by_name"
#             },
#             "total_uploads": {"$sum": 1},
#             "last_upload": {"$max": "$uploaded_at"}
#         }},
#         {"$sort": {"total_uploads": -1}}
#     ]
    
#     results = await documents_collection.aggregate(pipeline).to_list(100)
    
#     admins = []
#     for item in results:
#         admins.append({
#             "admin_id": item["_id"]["admin_id"],
#             "admin_name": item["_id"]["admin_name"],
#             "total_uploads": item["total_uploads"],
#             "last_upload": item["last_upload"]
#         })
    
#     return admins




























# """
# Documents Router
# Handles document management with 5-stage pipeline
# Storage: AWS S3
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Form
# from datetime import datetime
# from bson import ObjectId
# from typing import Optional, List

# from app.models.schemas import DocumentStage, UserRole
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user, require_admin
# from app.utils.s3_service import upload_document, delete_document, get_presigned_url

# router = APIRouter()

# STAGES = ["Agreement", "Pitch Deck", "DPR", "Application", "Others"]

# @router.get("/bookings")
# async def get_bookings_with_documents(
#     search: Optional[str] = Query(None, description="Search company name or mobile"),
#     service: Optional[str] = Query(None, description="Filter by service"),
#     start_date: Optional[datetime] = Query(None),
#     end_date: Optional[datetime] = Query(None),
#     # Individual stage filters (completed/pending)
#     agreement_status: Optional[str] = Query(None, description="completed or pending"),
#     pitchdeck_status: Optional[str] = Query(None, description="completed or pending"),
#     dpr_status: Optional[str] = Query(None, description="completed or pending"),
#     application_status: Optional[str] = Query(None, description="completed or pending"),
#     others_status: Optional[str] = Query(None, description="completed or pending"),
#     # Quick filters
#     doc_status: Optional[str] = Query(None, description="all_complete, any_pending, any_overdue"),
#     page: int = Query(1, ge=1),
#     page_size: int = Query(100, ge=1, le=1000),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all bookings with document status - FAST VERSION with overdue tracking"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     # Build query
#     query = {"isDeleted": False}
    
#     # Search by company name OR mobile number
#     if search:
#         search_term = search.strip()
#         # Remove any non-digit characters for phone matching
#         search_digits = ''.join(c for c in search_term if c.isdigit())
        
#         search_conditions = [
#             {"company_name": {"$regex": search_term, "$options": "i"}},
#         ]
        
#         # Add contact_no search conditions
#         # Handle both string and numeric contact_no fields
#         if search_digits:
#             # For string field - regex match
#             search_conditions.append({"contact_no": {"$regex": search_digits, "$options": "i"}})
#             # For numeric field - try exact match or convert to regex on string version
#             try:
#                 search_conditions.append({"contact_no": int(search_digits)})
#             except:
#                 pass
#             # Also try partial match by converting to string in aggregation
#             search_conditions.append({"$expr": {"$regexMatch": {"input": {"$toString": "$contact_no"}, "regex": search_digits, "options": "i"}}})
        
#         query["$or"] = search_conditions
    
#     if service:
#         query["services"] = service
    
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     # Get total count before stage filtering
#     total_before_filter = await bookings_collection.count_documents(query)
    
#     # Get all bookings (we'll filter by stage status in memory for speed)
#     cursor = bookings_collection.find(query).sort("date", -1)
    
#     # Get all bookings first
#     booking_list = []
#     booking_ids = []
#     now = datetime.utcnow()
    
#     async for booking in cursor:
#         booking_id = str(booking["_id"])
#         booking_ids.append(booking_id)
        
#         term_1 = booking.get("term_1") or 0
#         term_2 = booking.get("term_2") or 0
#         term_3 = booking.get("term_3") or 0
#         received_amount = term_1 + term_2 + term_3
        
#         # Calculate days since booking
#         booking_date = booking.get("date") or booking.get("createdAt") or now
#         if isinstance(booking_date, str):
#             try:
#                 booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
#             except:
#                 booking_date = now
#         days_since_booking = (now - booking_date).days
        
#         booking_list.append({
#             "id": booking_id,
#             "company_name": booking.get("company_name", ""),
#             "contact_person": booking.get("contact_person", ""),
#             "contact_no": str(booking.get("contact_no", "")),
#             "email": booking.get("email", ""),
#             "services": booking.get("services", []),
#             "total_amount": booking.get("total_amount", 0),
#             "term_1": term_1,
#             "term_2": term_2,
#             "term_3": term_3,
#             "received_amount": received_amount,
#             "status": booking.get("status", "Pending"),
#             "bdm": booking.get("bdm", ""),
#             "date": booking.get("date"),
#             "days_since_booking": days_since_booking,
#             "document_stages": {s: 0 for s in STAGES},
#             "overdue_stages": {},
#             "total_documents": 0,
#             "all_complete": False
#         })
    
#     # Get document counts in ONE aggregation query
#     if booking_ids:
#         doc_pipeline = [
#             {"$match": {"booking_id": {"$in": booking_ids}}},
#             {"$group": {
#                 "_id": {"booking_id": "$booking_id", "stage": "$stage"},
#                 "count": {"$sum": 1}
#             }}
#         ]
#         doc_counts = await documents_collection.aggregate(doc_pipeline).to_list(None)
        
#         # Map counts to bookings
#         count_map = {}
#         for dc in doc_counts:
#             bid = dc["_id"]["booking_id"]
#             stage = dc["_id"]["stage"]
#             count = dc["count"]
#             if bid not in count_map:
#                 count_map[bid] = {}
#             count_map[bid][stage] = count
        
#         # Update booking list with document counts and overdue status
#         for booking in booking_list:
#             if booking["id"] in count_map:
#                 for stage, count in count_map[booking["id"]].items():
#                     if stage in booking["document_stages"]:
#                         booking["document_stages"][stage] = count
#                 booking["total_documents"] = sum(booking["document_stages"].values())
            
#             # Calculate overdue status for each stage
#             days = booking["days_since_booking"]
#             for stage in STAGES:
#                 has_doc = booking["document_stages"].get(stage, 0) > 0
#                 if stage == "Agreement":
#                     booking["overdue_stages"][stage] = not has_doc and days > 6
#                 else:
#                     booking["overdue_stages"][stage] = not has_doc and days > 25
            
#             # Check if all stages are complete
#             booking["all_complete"] = all(
#                 booking["document_stages"].get(s, 0) > 0 for s in STAGES
#             )
    
#     # Apply individual stage filters (combination filters)
#     filtered_list = booking_list
    
#     if agreement_status:
#         if agreement_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Agreement", 0) > 0]
#         elif agreement_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Agreement", 0) == 0]
    
#     if pitchdeck_status:
#         if pitchdeck_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Pitch Deck", 0) > 0]
#         elif pitchdeck_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Pitch Deck", 0) == 0]
    
#     if dpr_status:
#         if dpr_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("DPR", 0) > 0]
#         elif dpr_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("DPR", 0) == 0]
    
#     if application_status:
#         if application_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Application", 0) > 0]
#         elif application_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Application", 0) == 0]
    
#     if others_status:
#         if others_status == "completed":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Others", 0) > 0]
#         elif others_status == "pending":
#             filtered_list = [b for b in filtered_list if b["document_stages"].get("Others", 0) == 0]
    
#     # Apply quick doc_status filter
#     if doc_status:
#         if doc_status == "all_complete":
#             filtered_list = [b for b in filtered_list if b["all_complete"]]
#         elif doc_status == "any_pending":
#             filtered_list = [b for b in filtered_list if not b["all_complete"]]
#         elif doc_status == "any_overdue":
#             filtered_list = [b for b in filtered_list if any(b["overdue_stages"].values())]
    
#     # Apply pagination after filtering
#     total = len(filtered_list)
#     skip = (page - 1) * page_size
#     paginated_list = filtered_list[skip:skip + page_size]
    
#     return {
#         "items": paginated_list,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
#     }

# @router.get("/booking/{booking_id}")
# async def get_booking_documents(
#     booking_id: str,
#     stage: Optional[str] = Query(None),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all documents for a specific booking"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid booking ID")
    
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
    
#     query = {"booking_id": booking_id}
#     if stage:
#         query["stage"] = stage
    
#     cursor = documents_collection.find(query).sort("uploaded_at", -1)
    
#     documents = []
#     async for doc in cursor:
#         # Get presigned URL for secure access
#         presigned_url = await get_presigned_url(doc["file_url"])
        
#         documents.append({
#             "id": str(doc["_id"]),
#             "booking_id": doc["booking_id"],
#             "stage": doc["stage"],
#             "file_name": doc["file_name"],
#             "file_url": presigned_url or doc["file_url"],
#             "uploaded_by": doc["uploaded_by"],
#             "uploaded_by_name": doc["uploaded_by_name"],
#             "uploaded_at": doc["uploaded_at"]
#         })
    
#     # Group by stage
#     by_stage = {s: [] for s in STAGES}
#     for doc in documents:
#         if doc["stage"] in by_stage:
#             by_stage[doc["stage"]].append(doc)
    
#     return {
#         "booking": {
#             "id": str(booking["_id"]),
#             "company_name": booking.get("company_name", ""),
#             "services": booking.get("services", [])
#         },
#         "documents": documents,
#         "by_stage": by_stage
#     }

# @router.post("/upload")
# async def upload_booking_document(
#     booking_id: str = Form(...),
#     stage: str = Form(...),
#     file: UploadFile = File(...),
#     current_user: dict = Depends(require_admin)
# ):
#     """Upload document for a booking stage"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     # Validate stage
#     if stage not in STAGES:
#         raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {STAGES}")
    
#     # Verify booking exists
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid booking ID")
    
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
    
#     # Read file content
#     file_content = await file.read()
    
#     # Upload to S3
#     file_url = await upload_document(
#         file_content=file_content,
#         file_name=file.filename,
#         booking_id=booking_id,
#         stage=stage,
#         content_type=file.content_type
#     )
    
#     if not file_url:
#         raise HTTPException(status_code=500, detail="Failed to upload document")
    
#     # Save document record
#     document = {
#         "booking_id": booking_id,
#         "stage": stage,
#         "file_name": file.filename,
#         "file_url": file_url,
#         "file_size": len(file_content),
#         "content_type": file.content_type,
#         "uploaded_by": current_user["id"],
#         "uploaded_by_name": current_user["name"],
#         "uploaded_at": datetime.utcnow()
#     }
    
#     result = await documents_collection.insert_one(document)
    
#     return {
#         "id": str(result.inserted_id),
#         "file_name": file.filename,
#         "file_url": file_url,
#         "stage": stage,
#         "message": "Document uploaded successfully"
#     }

# @router.delete("/{document_id}")
# async def delete_booking_document(document_id: str, current_user: dict = Depends(require_admin)):
#     """Delete a document"""
#     documents_collection = get_collection("documents")
    
#     try:
#         document = await documents_collection.find_one({"_id": ObjectId(document_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid document ID")
    
#     if not document:
#         raise HTTPException(status_code=404, detail="Document not found")
    
#     # Delete from S3
#     await delete_document(document["file_url"])
    
#     # Delete from database
#     await documents_collection.delete_one({"_id": ObjectId(document_id)})
    
#     return {"message": "Document deleted successfully"}

# @router.get("/analytics")
# async def get_document_analytics(current_user: dict = Depends(require_admin)):
#     """Get document analytics - count per stage"""
#     documents_collection = get_collection("documents")
#     bookings_collection = get_collection("bookings")
    
#     total_bookings = await bookings_collection.count_documents({"isDeleted": False})
    
#     analytics = []
#     for stage in STAGES:
#         # Count documents in this stage
#         doc_count = await documents_collection.count_documents({"stage": stage})
        
#         # Count unique bookings with documents in this stage
#         pipeline = [
#             {"$match": {"stage": stage}},
#             {"$group": {"_id": "$booking_id"}},
#             {"$count": "total"}
#         ]
#         result = await documents_collection.aggregate(pipeline).to_list(1)
#         bookings_with_docs = result[0]["total"] if result else 0
        
#         analytics.append({
#             "stage": stage,
#             "total_documents": doc_count,
#             "bookings_with_documents": bookings_with_docs,
#             "completion_percentage": round((bookings_with_docs / total_bookings) * 100, 1) if total_bookings > 0 else 0
#         })
    
#     return {
#         "total_bookings": total_bookings,
#         "stages": analytics
#     }

# @router.get("/stage/{stage}")
# async def get_documents_by_stage(
#     stage: str,
#     page: int = Query(1, ge=1),
#     page_size: int = Query(20, ge=1, le=100),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all documents for a specific stage"""
#     if stage not in STAGES:
#         raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {STAGES}")
    
#     documents_collection = get_collection("documents")
#     bookings_collection = get_collection("bookings")
    
#     total = await documents_collection.count_documents({"stage": stage})
    
#     skip = (page - 1) * page_size
#     cursor = documents_collection.find({"stage": stage}).skip(skip).limit(page_size).sort("uploaded_at", -1)
    
#     documents = []
#     async for doc in cursor:
#         # Get booking info
#         try:
#             booking = await bookings_collection.find_one({"_id": ObjectId(doc["booking_id"])})
#             company_name = booking.get("company_name", "Unknown") if booking else "Unknown"
#         except:
#             company_name = "Unknown"
        
#         presigned_url = await get_presigned_url(doc["file_url"])
        
#         documents.append({
#             "id": str(doc["_id"]),
#             "booking_id": doc["booking_id"],
#             "company_name": company_name,
#             "file_name": doc["file_name"],
#             "file_url": presigned_url or doc["file_url"],
#             "uploaded_by_name": doc["uploaded_by_name"],
#             "uploaded_at": doc["uploaded_at"]
#         })
    
#     return {
#         "stage": stage,
#         "items": documents,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
#     }

# # ==================== NOTES ENDPOINTS ====================

# @router.get("/notes/{booking_id}")
# async def get_booking_notes(
#     booking_id: str,
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all notes for a booking"""
#     notes_collection = get_collection("booking_notes")
    
#     cursor = notes_collection.find({"booking_id": booking_id}).sort("created_at", -1)
    
#     notes = []
#     async for note in cursor:
#         notes.append({
#             "id": str(note["_id"]),
#             "booking_id": note["booking_id"],
#             "content": note["content"],
#             "created_by": note["created_by"],
#             "created_by_name": note["created_by_name"],
#             "created_at": note["created_at"],
#             "updated_at": note.get("updated_at")
#         })
    
#     return {"notes": notes}

# @router.post("/notes")
# async def create_booking_note(
#     data: dict,
#     current_user: dict = Depends(require_admin)
# ):
#     """Create a new note for a booking"""
#     booking_id = data.get("booking_id")
#     content = data.get("content", "")
    
#     if not booking_id:
#         raise HTTPException(status_code=400, detail="booking_id is required")
#     if not content or not content.strip():
#         raise HTTPException(status_code=400, detail="Note content cannot be empty")
    
#     notes_collection = get_collection("booking_notes")
#     bookings_collection = get_collection("bookings")
    
#     # Verify booking exists
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#         if not booking:
#             raise HTTPException(status_code=404, detail="Booking not found")
#     except:
#         raise HTTPException(status_code=400, detail="Invalid booking ID")
    
#     note = {
#         "booking_id": booking_id,
#         "content": content.strip(),
#         "created_by": current_user["id"],
#         "created_by_name": current_user["name"],
#         "created_at": datetime.utcnow(),
#     }
    
#     result = await notes_collection.insert_one(note)
    
#     return {
#         "id": str(result.inserted_id),
#         "message": "Note created successfully"
#     }

# @router.put("/notes/{note_id}")
# async def update_booking_note(
#     note_id: str,
#     data: dict,
#     current_user: dict = Depends(require_admin)
# ):
#     """Update an existing note"""
#     content = data.get("content", "")
    
#     if not content or not content.strip():
#         raise HTTPException(status_code=400, detail="Note content cannot be empty")
    
#     notes_collection = get_collection("booking_notes")
    
#     try:
#         result = await notes_collection.update_one(
#             {"_id": ObjectId(note_id)},
#             {"$set": {
#                 "content": content.strip(),
#                 "updated_at": datetime.utcnow()
#             }}
#         )
#     except:
#         raise HTTPException(status_code=400, detail="Invalid note ID")
    
#     if result.matched_count == 0:
#         raise HTTPException(status_code=404, detail="Note not found")
    
#     return {"message": "Note updated successfully"}

# @router.delete("/notes/{note_id}")
# async def delete_booking_note(
#     note_id: str,
#     current_user: dict = Depends(require_admin)
# ):
#     """Delete a note"""
#     notes_collection = get_collection("booking_notes")
    
#     try:
#         result = await notes_collection.delete_one({"_id": ObjectId(note_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid note ID")
    
#     if result.deleted_count == 0:
#         raise HTTPException(status_code=404, detail="Note not found")
    
#     return {"message": "Note deleted successfully"}

# # ============================================
# # ADMIN UPLOAD ACTIVITY TRACKING
# # ============================================

# @router.get("/admin-activity")
# async def get_admin_upload_activity(
#     start_date: Optional[datetime] = Query(None, description="Start date filter"),
#     end_date: Optional[datetime] = Query(None, description="End date filter"),
#     admin_id: Optional[str] = Query(None, description="Filter by specific admin"),
#     current_user: dict = Depends(require_admin)
# ):
#     """
#     Get admin document upload activity summary
#     Shows how many documents each admin uploaded per day
#     """
#     documents_collection = get_collection("documents")
#     users_collection = get_collection("users")
    
#     # Build date filter
#     date_filter = {}
#     if start_date:
#         date_filter["$gte"] = start_date
#     if end_date:
#         # Set end_date to end of day
#         end_of_day = end_date.replace(hour=23, minute=59, second=59)
#         date_filter["$lte"] = end_of_day
    
#     # Build query
#     query = {}
#     if date_filter:
#         query["uploaded_at"] = date_filter
#     if admin_id:
#         query["uploaded_by"] = admin_id
    
#     # Aggregate by admin and date
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {
#                 "admin_id": "$uploaded_by",
#                 "admin_name": "$uploaded_by_name",
#                 "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$uploaded_at"}},
#                 "stage": "$stage"
#             },
#             "count": {"$sum": 1}
#         }},
#         {"$sort": {"_id.date": -1, "_id.admin_name": 1}}
#     ]
    
#     results = await documents_collection.aggregate(pipeline).to_list(1000)
    
#     # Organize data by date and admin
#     activity_by_date = {}
#     admin_totals = {}
    
#     for item in results:
#         date = item["_id"]["date"]
#         admin_name = item["_id"]["admin_name"]
#         admin_id = item["_id"]["admin_id"]
#         stage = item["_id"]["stage"]
#         count = item["count"]
        
#         # By date
#         if date not in activity_by_date:
#             activity_by_date[date] = {}
        
#         if admin_name not in activity_by_date[date]:
#             activity_by_date[date][admin_name] = {
#                 "admin_id": admin_id,
#                 "admin_name": admin_name,
#                 "total": 0,
#                 "by_stage": {}
#             }
        
#         activity_by_date[date][admin_name]["total"] += count
#         activity_by_date[date][admin_name]["by_stage"][stage] = count
        
#         # Admin totals
#         if admin_name not in admin_totals:
#             admin_totals[admin_name] = {
#                 "admin_id": admin_id,
#                 "admin_name": admin_name,
#                 "total": 0,
#                 "by_stage": {}
#             }
#         admin_totals[admin_name]["total"] += count
#         if stage not in admin_totals[admin_name]["by_stage"]:
#             admin_totals[admin_name]["by_stage"][stage] = 0
#         admin_totals[admin_name]["by_stage"][stage] += count
    
#     # Convert to list format
#     daily_activity = []
#     for date, admins in sorted(activity_by_date.items(), reverse=True):
#         daily_activity.append({
#             "date": date,
#             "admins": list(admins.values()),
#             "total": sum(a["total"] for a in admins.values())
#         })
    
#     return {
#         "daily_activity": daily_activity,
#         "admin_totals": list(admin_totals.values()),
#         "stages": STAGES
#     }

# @router.get("/admin-activity/details")
# async def get_admin_upload_details(
#     date: str = Query(..., description="Date in YYYY-MM-DD format"),
#     admin_id: Optional[str] = Query(None, description="Filter by specific admin"),
#     stage: Optional[str] = Query(None, description="Filter by document stage"),
#     current_user: dict = Depends(require_admin)
# ):
#     """
#     Get detailed list of documents uploaded by admins on a specific date
#     Shows booking details for each upload
#     """
#     documents_collection = get_collection("documents")
#     bookings_collection = get_collection("bookings")
    
#     # Parse date
#     try:
#         target_date = datetime.strptime(date, "%Y-%m-%d")
#         next_date = target_date.replace(hour=23, minute=59, second=59)
#     except:
#         raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
#     # Build query
#     query = {
#         "uploaded_at": {"$gte": target_date, "$lte": next_date}
#     }
#     if admin_id:
#         query["uploaded_by"] = admin_id
#     if stage:
#         query["stage"] = stage
    
#     # Get documents
#     cursor = documents_collection.find(query).sort("uploaded_at", -1)
    
#     documents = []
#     booking_ids = set()
    
#     async for doc in cursor:
#         booking_ids.add(doc["booking_id"])
#         documents.append({
#             "id": str(doc["_id"]),
#             "booking_id": doc["booking_id"],
#             "stage": doc["stage"],
#             "file_name": doc["file_name"],
#             "uploaded_by": doc["uploaded_by"],
#             "uploaded_by_name": doc["uploaded_by_name"],
#             "uploaded_at": doc["uploaded_at"]
#         })
    
#     # Get booking details
#     bookings_map = {}
#     if booking_ids:
#         cursor = bookings_collection.find(
#             {"_id": {"$in": [ObjectId(bid) for bid in booking_ids]}},
#             {"company_name": 1, "contact_person": 1, "services": 1, "bdm": 1, "date": 1, "createdAt": 1}
#         )
#         async for booking in cursor:
#             booking_date = booking.get("date") or booking.get("createdAt")
#             bookings_map[str(booking["_id"])] = {
#                 "company_name": booking.get("company_name", ""),
#                 "contact_person": booking.get("contact_person", ""),
#                 "services": booking.get("services", []),
#                 "bdm": booking.get("bdm", ""),
#                 "booking_date": booking_date
#             }
    
#     # Attach booking info to documents
#     for doc in documents:
#         doc["booking"] = bookings_map.get(doc["booking_id"], {})
    
#     # Group by admin
#     by_admin = {}
#     for doc in documents:
#         admin_name = doc["uploaded_by_name"]
#         if admin_name not in by_admin:
#             by_admin[admin_name] = {
#                 "admin_name": admin_name,
#                 "admin_id": doc["uploaded_by"],
#                 "uploads": [],
#                 "total": 0
#             }
#         by_admin[admin_name]["uploads"].append(doc)
#         by_admin[admin_name]["total"] += 1
    
#     return {
#         "date": date,
#         "admins": list(by_admin.values()),
#         "total_uploads": len(documents)
#     }

# @router.get("/admin-list")
# async def get_document_admins(current_user: dict = Depends(require_admin)):
#     """Get list of admins who have uploaded documents"""
#     documents_collection = get_collection("documents")
    
#     pipeline = [
#         {"$group": {
#             "_id": {
#                 "admin_id": "$uploaded_by",
#                 "admin_name": "$uploaded_by_name"
#             },
#             "total_uploads": {"$sum": 1},
#             "last_upload": {"$max": "$uploaded_at"}
#         }},
#         {"$sort": {"total_uploads": -1}}
#     ]
    
#     results = await documents_collection.aggregate(pipeline).to_list(100)
    
#     admins = []
#     for item in results:
#         admins.append({
#             "admin_id": item["_id"]["admin_id"],
#             "admin_name": item["_id"]["admin_name"],
#             "total_uploads": item["total_uploads"],
#             "last_upload": item["last_upload"]
#         })
    
#     return admins









































"""
Documents Router
Handles document management with 5-stage pipeline
Storage: AWS S3
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Form
from datetime import datetime
from bson import ObjectId
from typing import Optional, List

from app.models.schemas import DocumentStage, UserRole
from app.utils.database import get_collection
from app.utils.auth import get_current_user, require_admin
from app.utils.s3_service import upload_document, delete_document, get_presigned_url

router = APIRouter()

STAGES = ["Agreement", "Pitch Deck", "DPR", "Application", "Others"]

@router.get("/bookings")
async def get_bookings_with_documents(
    search: Optional[str] = Query(None, description="Search company name or mobile"),
    service: Optional[str] = Query(None, description="Filter by service"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    # Individual stage filters (completed/pending)
    agreement_status: Optional[str] = Query(None, description="completed or pending"),
    pitchdeck_status: Optional[str] = Query(None, description="completed or pending"),
    dpr_status: Optional[str] = Query(None, description="completed or pending"),
    application_status: Optional[str] = Query(None, description="completed or pending"),
    others_status: Optional[str] = Query(None, description="completed or pending"),
    # Quick filters
    doc_status: Optional[str] = Query(None, description="all_complete, any_pending, any_overdue"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(require_admin)
):
    """Get all bookings with document status - FAST VERSION with overdue tracking"""
    bookings_collection = get_collection("bookings")
    documents_collection = get_collection("documents")
    
    # Build query - hide pending/rejected bookings (they're in verification queue)
    query = {
        "isDeleted": False,
        "verification_status": {"$nin": ["pending", "rejected"]}
    }
    
    # Search by company name OR mobile number
    if search:
        search_term = search.strip()
        # Remove any non-digit characters for phone matching
        search_digits = ''.join(c for c in search_term if c.isdigit())
        
        search_conditions = [
            {"company_name": {"$regex": search_term, "$options": "i"}},
        ]
        
        # Add contact_no search conditions
        # Handle both string and numeric contact_no fields
        if search_digits:
            # For string field - regex match
            search_conditions.append({"contact_no": {"$regex": search_digits, "$options": "i"}})
            # For numeric field - try exact match or convert to regex on string version
            try:
                search_conditions.append({"contact_no": int(search_digits)})
            except:
                pass
            # Also try partial match by converting to string in aggregation
            search_conditions.append({"$expr": {"$regexMatch": {"input": {"$toString": "$contact_no"}, "regex": search_digits, "options": "i"}}})
        
        query["$or"] = search_conditions
    
    if service:
        query["services"] = service
    
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    # Get total count before stage filtering
    total_before_filter = await bookings_collection.count_documents(query)
    
    # Get all bookings (we'll filter by stage status in memory for speed)
    cursor = bookings_collection.find(query).sort("date", -1)
    
    # Get all bookings first
    booking_list = []
    booking_ids = []
    now = datetime.utcnow()
    
    async for booking in cursor:
        booking_id = str(booking["_id"])
        booking_ids.append(booking_id)
        
        term_1 = booking.get("term_1") or 0
        term_2 = booking.get("term_2") or 0
        term_3 = booking.get("term_3") or 0
        received_amount = term_1 + term_2 + term_3
        
        # Calculate days since booking
        booking_date = booking.get("date") or booking.get("createdAt") or now
        if isinstance(booking_date, str):
            try:
                booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
            except:
                booking_date = now
        days_since_booking = (now - booking_date).days
        
        booking_list.append({
            "id": booking_id,
            "company_name": booking.get("company_name", ""),
            "contact_person": booking.get("contact_person", ""),
            "contact_no": str(booking.get("contact_no", "")),
            "email": booking.get("email", ""),
            "services": booking.get("services", []),
            "total_amount": booking.get("total_amount", 0),
            "term_1": term_1,
            "term_2": term_2,
            "term_3": term_3,
            "received_amount": received_amount,
            "status": booking.get("status", "Pending"),
            "bdm": booking.get("bdm", ""),
            "date": booking.get("date"),
            "days_since_booking": days_since_booking,
            "document_stages": {s: 0 for s in STAGES},
            "overdue_stages": {},
            "total_documents": 0,
            "all_complete": False
        })
    
    # Get document counts in ONE aggregation query
    if booking_ids:
        doc_pipeline = [
            {"$match": {"booking_id": {"$in": booking_ids}}},
            {"$group": {
                "_id": {"booking_id": "$booking_id", "stage": "$stage"},
                "count": {"$sum": 1}
            }}
        ]
        doc_counts = await documents_collection.aggregate(doc_pipeline).to_list(None)
        
        # Map counts to bookings
        count_map = {}
        for dc in doc_counts:
            bid = dc["_id"]["booking_id"]
            stage = dc["_id"]["stage"]
            count = dc["count"]
            if bid not in count_map:
                count_map[bid] = {}
            count_map[bid][stage] = count
        
        # Update booking list with document counts and overdue status
        for booking in booking_list:
            if booking["id"] in count_map:
                for stage, count in count_map[booking["id"]].items():
                    if stage in booking["document_stages"]:
                        booking["document_stages"][stage] = count
                booking["total_documents"] = sum(booking["document_stages"].values())
            
            # Calculate overdue status for each stage
            days = booking["days_since_booking"]
            for stage in STAGES:
                has_doc = booking["document_stages"].get(stage, 0) > 0
                if stage == "Agreement":
                    booking["overdue_stages"][stage] = not has_doc and days > 6
                else:
                    booking["overdue_stages"][stage] = not has_doc and days > 25
            
            # Check if all stages are complete
            booking["all_complete"] = all(
                booking["document_stages"].get(s, 0) > 0 for s in STAGES
            )
    
    # Apply individual stage filters (combination filters)
    filtered_list = booking_list
    
    if agreement_status:
        if agreement_status == "completed":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Agreement", 0) > 0]
        elif agreement_status == "pending":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Agreement", 0) == 0]
    
    if pitchdeck_status:
        if pitchdeck_status == "completed":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Pitch Deck", 0) > 0]
        elif pitchdeck_status == "pending":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Pitch Deck", 0) == 0]
    
    if dpr_status:
        if dpr_status == "completed":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("DPR", 0) > 0]
        elif dpr_status == "pending":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("DPR", 0) == 0]
    
    if application_status:
        if application_status == "completed":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Application", 0) > 0]
        elif application_status == "pending":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Application", 0) == 0]
    
    if others_status:
        if others_status == "completed":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Others", 0) > 0]
        elif others_status == "pending":
            filtered_list = [b for b in filtered_list if b["document_stages"].get("Others", 0) == 0]
    
    # Apply quick doc_status filter
    if doc_status:
        if doc_status == "all_complete":
            filtered_list = [b for b in filtered_list if b["all_complete"]]
        elif doc_status == "any_pending":
            filtered_list = [b for b in filtered_list if not b["all_complete"]]
        elif doc_status == "any_overdue":
            filtered_list = [b for b in filtered_list if any(b["overdue_stages"].values())]
    
    # Apply pagination after filtering
    total = len(filtered_list)
    skip = (page - 1) * page_size
    paginated_list = filtered_list[skip:skip + page_size]
    
    return {
        "items": paginated_list,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
    }

@router.get("/booking/{booking_id}")
async def get_booking_documents(
    booking_id: str,
    stage: Optional[str] = Query(None),
    current_user: dict = Depends(require_admin)
):
    """Get all documents for a specific booking"""
    bookings_collection = get_collection("bookings")
    documents_collection = get_collection("documents")
    
    try:
        booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid booking ID")
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    query = {"booking_id": booking_id}
    if stage:
        query["stage"] = stage
    
    cursor = documents_collection.find(query).sort("uploaded_at", -1)
    
    documents = []
    async for doc in cursor:
        # Get presigned URL for secure access
        presigned_url = await get_presigned_url(doc["file_url"])
        
        documents.append({
            "id": str(doc["_id"]),
            "booking_id": doc["booking_id"],
            "stage": doc["stage"],
            "file_name": doc["file_name"],
            "file_url": presigned_url or doc["file_url"],
            "uploaded_by": doc["uploaded_by"],
            "uploaded_by_name": doc["uploaded_by_name"],
            "uploaded_at": doc["uploaded_at"]
        })
    
    # Group by stage
    by_stage = {s: [] for s in STAGES}
    for doc in documents:
        if doc["stage"] in by_stage:
            by_stage[doc["stage"]].append(doc)
    
    return {
        "booking": {
            "id": str(booking["_id"]),
            "company_name": booking.get("company_name", ""),
            "services": booking.get("services", [])
        },
        "documents": documents,
        "by_stage": by_stage
    }

@router.post("/upload")
async def upload_booking_document(
    booking_id: str = Form(...),
    stage: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin)
):
    """Upload document for a booking stage"""
    bookings_collection = get_collection("bookings")
    documents_collection = get_collection("documents")
    
    # Validate stage
    if stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {STAGES}")
    
    # Verify booking exists
    try:
        booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid booking ID")
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Read file content
    file_content = await file.read()
    
    # Upload to S3
    file_url = await upload_document(
        file_content=file_content,
        file_name=file.filename,
        booking_id=booking_id,
        stage=stage,
        content_type=file.content_type
    )
    
    if not file_url:
        raise HTTPException(status_code=500, detail="Failed to upload document")
    
    # Save document record
    document = {
        "booking_id": booking_id,
        "stage": stage,
        "file_name": file.filename,
        "file_url": file_url,
        "file_size": len(file_content),
        "content_type": file.content_type,
        "uploaded_by": current_user["id"],
        "uploaded_by_name": current_user["name"],
        "uploaded_at": datetime.utcnow()
    }
    
    result = await documents_collection.insert_one(document)
    
    return {
        "id": str(result.inserted_id),
        "file_name": file.filename,
        "file_url": file_url,
        "stage": stage,
        "message": "Document uploaded successfully"
    }

@router.delete("/{document_id}")
async def delete_booking_document(document_id: str, current_user: dict = Depends(require_admin)):
    """Delete a document"""
    documents_collection = get_collection("documents")
    
    try:
        document = await documents_collection.find_one({"_id": ObjectId(document_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid document ID")
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from S3
    await delete_document(document["file_url"])
    
    # Delete from database
    await documents_collection.delete_one({"_id": ObjectId(document_id)})
    
    return {"message": "Document deleted successfully"}

@router.get("/analytics")
async def get_document_analytics(current_user: dict = Depends(require_admin)):
    """Get document analytics - count per stage"""
    documents_collection = get_collection("documents")
    bookings_collection = get_collection("bookings")
    
    total_bookings = await bookings_collection.count_documents({
        "isDeleted": False,
        "verification_status": {"$nin": ["pending", "rejected"]}
    })
    
    analytics = []
    for stage in STAGES:
        # Count documents in this stage
        doc_count = await documents_collection.count_documents({"stage": stage})
        
        # Count unique bookings with documents in this stage
        pipeline = [
            {"$match": {"stage": stage}},
            {"$group": {"_id": "$booking_id"}},
            {"$count": "total"}
        ]
        result = await documents_collection.aggregate(pipeline).to_list(1)
        bookings_with_docs = result[0]["total"] if result else 0
        
        analytics.append({
            "stage": stage,
            "total_documents": doc_count,
            "bookings_with_documents": bookings_with_docs,
            "completion_percentage": round((bookings_with_docs / total_bookings) * 100, 1) if total_bookings > 0 else 0
        })
    
    return {
        "total_bookings": total_bookings,
        "stages": analytics
    }

@router.get("/stage/{stage}")
async def get_documents_by_stage(
    stage: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_admin)
):
    """Get all documents for a specific stage"""
    if stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {STAGES}")
    
    documents_collection = get_collection("documents")
    bookings_collection = get_collection("bookings")
    
    total = await documents_collection.count_documents({"stage": stage})
    
    skip = (page - 1) * page_size
    cursor = documents_collection.find({"stage": stage}).skip(skip).limit(page_size).sort("uploaded_at", -1)
    
    documents = []
    async for doc in cursor:
        # Get booking info
        try:
            booking = await bookings_collection.find_one({"_id": ObjectId(doc["booking_id"])})
            company_name = booking.get("company_name", "Unknown") if booking else "Unknown"
        except:
            company_name = "Unknown"
        
        presigned_url = await get_presigned_url(doc["file_url"])
        
        documents.append({
            "id": str(doc["_id"]),
            "booking_id": doc["booking_id"],
            "company_name": company_name,
            "file_name": doc["file_name"],
            "file_url": presigned_url or doc["file_url"],
            "uploaded_by_name": doc["uploaded_by_name"],
            "uploaded_at": doc["uploaded_at"]
        })
    
    return {
        "stage": stage,
        "items": documents,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

# ==================== NOTES ENDPOINTS ====================

@router.get("/notes/{booking_id}")
async def get_booking_notes(
    booking_id: str,
    current_user: dict = Depends(require_admin)
):
    """Get all notes for a booking"""
    notes_collection = get_collection("booking_notes")
    
    cursor = notes_collection.find({"booking_id": booking_id}).sort("created_at", -1)
    
    notes = []
    async for note in cursor:
        notes.append({
            "id": str(note["_id"]),
            "booking_id": note["booking_id"],
            "content": note["content"],
            "created_by": note["created_by"],
            "created_by_name": note["created_by_name"],
            "created_at": note["created_at"],
            "updated_at": note.get("updated_at")
        })
    
    return {"notes": notes}

@router.post("/notes")
async def create_booking_note(
    data: dict,
    current_user: dict = Depends(require_admin)
):
    """Create a new note for a booking"""
    booking_id = data.get("booking_id")
    content = data.get("content", "")
    
    if not booking_id:
        raise HTTPException(status_code=400, detail="booking_id is required")
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Note content cannot be empty")
    
    notes_collection = get_collection("booking_notes")
    bookings_collection = get_collection("bookings")
    
    # Verify booking exists
    try:
        booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
    except:
        raise HTTPException(status_code=400, detail="Invalid booking ID")
    
    note = {
        "booking_id": booking_id,
        "content": content.strip(),
        "created_by": current_user["id"],
        "created_by_name": current_user["name"],
        "created_at": datetime.utcnow(),
    }
    
    result = await notes_collection.insert_one(note)
    
    return {
        "id": str(result.inserted_id),
        "message": "Note created successfully"
    }

@router.put("/notes/{note_id}")
async def update_booking_note(
    note_id: str,
    data: dict,
    current_user: dict = Depends(require_admin)
):
    """Update an existing note"""
    content = data.get("content", "")
    
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Note content cannot be empty")
    
    notes_collection = get_collection("booking_notes")
    
    try:
        result = await notes_collection.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": {
                "content": content.strip(),
                "updated_at": datetime.utcnow()
            }}
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid note ID")
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    
    return {"message": "Note updated successfully"}

@router.delete("/notes/{note_id}")
async def delete_booking_note(
    note_id: str,
    current_user: dict = Depends(require_admin)
):
    """Delete a note"""
    notes_collection = get_collection("booking_notes")
    
    try:
        result = await notes_collection.delete_one({"_id": ObjectId(note_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid note ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    
    return {"message": "Note deleted successfully"}

# ============================================
# ADMIN UPLOAD ACTIVITY TRACKING
# ============================================

@router.get("/admin-activity")
async def get_admin_upload_activity(
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    admin_id: Optional[str] = Query(None, description="Filter by specific admin"),
    current_user: dict = Depends(require_admin)
):
    """
    Get admin document upload activity summary
    Shows how many documents each admin uploaded per day
    """
    documents_collection = get_collection("documents")
    users_collection = get_collection("users")
    
    # Build date filter
    date_filter = {}
    if start_date:
        date_filter["$gte"] = start_date
    if end_date:
        # Set end_date to end of day
        end_of_day = end_date.replace(hour=23, minute=59, second=59)
        date_filter["$lte"] = end_of_day
    
    # Build query
    query = {}
    if date_filter:
        query["uploaded_at"] = date_filter
    if admin_id:
        query["uploaded_by"] = admin_id
    
    # Aggregate by admin and date
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {
                "admin_id": "$uploaded_by",
                "admin_name": "$uploaded_by_name",
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$uploaded_at"}},
                "stage": "$stage"
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.date": -1, "_id.admin_name": 1}}
    ]
    
    results = await documents_collection.aggregate(pipeline).to_list(1000)
    
    # Organize data by date and admin
    activity_by_date = {}
    admin_totals = {}
    
    for item in results:
        date = item["_id"]["date"]
        admin_name = item["_id"]["admin_name"]
        admin_id = item["_id"]["admin_id"]
        stage = item["_id"]["stage"]
        count = item["count"]
        
        # By date
        if date not in activity_by_date:
            activity_by_date[date] = {}
        
        if admin_name not in activity_by_date[date]:
            activity_by_date[date][admin_name] = {
                "admin_id": admin_id,
                "admin_name": admin_name,
                "total": 0,
                "by_stage": {}
            }
        
        activity_by_date[date][admin_name]["total"] += count
        activity_by_date[date][admin_name]["by_stage"][stage] = count
        
        # Admin totals
        if admin_name not in admin_totals:
            admin_totals[admin_name] = {
                "admin_id": admin_id,
                "admin_name": admin_name,
                "total": 0,
                "by_stage": {}
            }
        admin_totals[admin_name]["total"] += count
        if stage not in admin_totals[admin_name]["by_stage"]:
            admin_totals[admin_name]["by_stage"][stage] = 0
        admin_totals[admin_name]["by_stage"][stage] += count
    
    # Convert to list format
    daily_activity = []
    for date, admins in sorted(activity_by_date.items(), reverse=True):
        daily_activity.append({
            "date": date,
            "admins": list(admins.values()),
            "total": sum(a["total"] for a in admins.values())
        })
    
    return {
        "daily_activity": daily_activity,
        "admin_totals": list(admin_totals.values()),
        "stages": STAGES
    }

@router.get("/admin-activity/details")
async def get_admin_upload_details(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    admin_id: Optional[str] = Query(None, description="Filter by specific admin"),
    stage: Optional[str] = Query(None, description="Filter by document stage"),
    current_user: dict = Depends(require_admin)
):
    """
    Get detailed list of documents uploaded by admins on a specific date
    Shows booking details for each upload
    """
    documents_collection = get_collection("documents")
    bookings_collection = get_collection("bookings")
    
    # Parse date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        next_date = target_date.replace(hour=23, minute=59, second=59)
    except:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Build query
    query = {
        "uploaded_at": {"$gte": target_date, "$lte": next_date}
    }
    if admin_id:
        query["uploaded_by"] = admin_id
    if stage:
        query["stage"] = stage
    
    # Get documents
    cursor = documents_collection.find(query).sort("uploaded_at", -1)
    
    documents = []
    booking_ids = set()
    
    async for doc in cursor:
        booking_ids.add(doc["booking_id"])
        documents.append({
            "id": str(doc["_id"]),
            "booking_id": doc["booking_id"],
            "stage": doc["stage"],
            "file_name": doc["file_name"],
            "uploaded_by": doc["uploaded_by"],
            "uploaded_by_name": doc["uploaded_by_name"],
            "uploaded_at": doc["uploaded_at"]
        })
    
    # Get booking details
    bookings_map = {}
    if booking_ids:
        cursor = bookings_collection.find(
            {"_id": {"$in": [ObjectId(bid) for bid in booking_ids]}},
            {"company_name": 1, "contact_person": 1, "services": 1, "bdm": 1, "date": 1, "createdAt": 1}
        )
        async for booking in cursor:
            booking_date = booking.get("date") or booking.get("createdAt")
            bookings_map[str(booking["_id"])] = {
                "company_name": booking.get("company_name", ""),
                "contact_person": booking.get("contact_person", ""),
                "services": booking.get("services", []),
                "bdm": booking.get("bdm", ""),
                "booking_date": booking_date
            }
    
    # Attach booking info to documents
    for doc in documents:
        doc["booking"] = bookings_map.get(doc["booking_id"], {})
    
    # Group by admin
    by_admin = {}
    for doc in documents:
        admin_name = doc["uploaded_by_name"]
        if admin_name not in by_admin:
            by_admin[admin_name] = {
                "admin_name": admin_name,
                "admin_id": doc["uploaded_by"],
                "uploads": [],
                "total": 0
            }
        by_admin[admin_name]["uploads"].append(doc)
        by_admin[admin_name]["total"] += 1
    
    return {
        "date": date,
        "admins": list(by_admin.values()),
        "total_uploads": len(documents)
    }

@router.get("/admin-list")
async def get_document_admins(current_user: dict = Depends(require_admin)):
    """Get list of admins who have uploaded documents"""
    documents_collection = get_collection("documents")
    
    pipeline = [
        {"$group": {
            "_id": {
                "admin_id": "$uploaded_by",
                "admin_name": "$uploaded_by_name"
            },
            "total_uploads": {"$sum": 1},
            "last_upload": {"$max": "$uploaded_at"}
        }},
        {"$sort": {"total_uploads": -1}}
    ]
    
    results = await documents_collection.aggregate(pipeline).to_list(100)
    
    admins = []
    for item in results:
        admins.append({
            "admin_id": item["_id"]["admin_id"],
            "admin_name": item["_id"]["admin_name"],
            "total_uploads": item["total_uploads"],
            "last_upload": item["last_upload"]
        })
    
    return admins
