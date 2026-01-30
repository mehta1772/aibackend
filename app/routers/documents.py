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
#     page: int = Query(1, ge=1),
#     page_size: int = Query(100, ge=1, le=1000),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all bookings with document status - FAST VERSION"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     # Build query
#     query = {"isDeleted": False}
    
#     if search:
#         query["$or"] = [
#             {"company_name": {"$regex": search, "$options": "i"}},
#             {"contact_no": {"$regex": search, "$options": "i"}}
#         ]
    
#     if service:
#         query["services"] = service
    
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     total = await bookings_collection.count_documents(query)
    
#     skip = (page - 1) * page_size
#     cursor = bookings_collection.find(query).skip(skip).limit(page_size).sort("date", -1)
    
#     # Get all bookings first
#     booking_list = []
#     booking_ids = []
#     async for booking in cursor:
#         booking_id = str(booking["_id"])
#         booking_ids.append(booking_id)
        
#         term_1 = booking.get("term_1") or 0
#         term_2 = booking.get("term_2") or 0
#         term_3 = booking.get("term_3") or 0
#         received_amount = term_1 + term_2 + term_3
        
#         booking_list.append({
#             "id": booking_id,
#             "company_name": booking.get("company_name", ""),
#             "contact_person": booking.get("contact_person", ""),
#             "contact_no": str(booking.get("contact_no", "")),
#             "email": booking.get("email", ""),
#             "services": booking.get("services", []),
#             "total_amount": booking.get("total_amount", 0),
#             "received_amount": received_amount,
#             "status": booking.get("status", "Pending"),
#             "bdm": booking.get("bdm", ""),
#             "date": booking.get("date"),
#             "document_stages": {s: 0 for s in STAGES},
#             "total_documents": 0
#         })
    
#     # Get document counts in ONE aggregation query (much faster)
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
        
#         # Update booking list with document counts
#         for booking in booking_list:
#             if booking["id"] in count_map:
#                 for stage, count in count_map[booking["id"]].items():
#                     if stage in booking["document_stages"]:
#                         booking["document_stages"][stage] = count
#                 booking["total_documents"] = sum(booking["document_stages"].values())
    
#     return {
#         "items": booking_list,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
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
#     doc_status: Optional[str] = Query(None, description="Filter: all, completed, pending, agreement_pending, pitchdeck_pending, dpr_pending, application_pending, others_pending"),
#     page: int = Query(1, ge=1),
#     page_size: int = Query(100, ge=1, le=1000),
#     current_user: dict = Depends(require_admin)
# ):
#     """Get all bookings with document status - FAST VERSION with overdue tracking"""
#     bookings_collection = get_collection("bookings")
#     documents_collection = get_collection("documents")
    
#     # Build query
#     query = {"isDeleted": False}
    
#     if search:
#         query["$or"] = [
#             {"company_name": {"$regex": search, "$options": "i"}},
#             {"contact_no": {"$regex": search, "$options": "i"}}
#         ]
    
#     if service:
#         query["services"] = service
    
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     total = await bookings_collection.count_documents(query)
    
#     skip = (page - 1) * page_size
#     cursor = bookings_collection.find(query).skip(skip).limit(page_size).sort("date", -1)
    
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
#             "overdue_stages": {},  # Will be populated
#             "total_documents": 0,
#             "all_complete": False
#         })
    
#     # Get document counts in ONE aggregation query (much faster)
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
#                     # Agreement: 6 days deadline
#                     booking["overdue_stages"][stage] = not has_doc and days > 6
#                 else:
#                     # Others: 25 days deadline
#                     booking["overdue_stages"][stage] = not has_doc and days > 25
            
#             # Check if all stages are complete
#             booking["all_complete"] = all(
#                 booking["document_stages"].get(s, 0) > 0 for s in STAGES
#             )
    
#     # Apply doc_status filter after processing
#     if doc_status:
#         if doc_status == "completed":
#             booking_list = [b for b in booking_list if b["all_complete"]]
#         elif doc_status == "pending":
#             booking_list = [b for b in booking_list if not b["all_complete"]]
#         elif doc_status == "agreement_pending":
#             booking_list = [b for b in booking_list if b["document_stages"].get("Agreement", 0) == 0]
#         elif doc_status == "pitchdeck_pending":
#             booking_list = [b for b in booking_list if b["document_stages"].get("Pitch Deck", 0) == 0]
#         elif doc_status == "dpr_pending":
#             booking_list = [b for b in booking_list if b["document_stages"].get("DPR", 0) == 0]
#         elif doc_status == "application_pending":
#             booking_list = [b for b in booking_list if b["document_stages"].get("Application", 0) == 0]
#         elif doc_status == "others_pending":
#             booking_list = [b for b in booking_list if b["document_stages"].get("Others", 0) == 0]
#         elif doc_status == "agreement_overdue":
#             booking_list = [b for b in booking_list if b["overdue_stages"].get("Agreement", False)]
#         elif doc_status == "other_overdue":
#             booking_list = [b for b in booking_list if any(b["overdue_stages"].get(s, False) for s in STAGES if s != "Agreement")]
    
#     return {
#         "items": booking_list,
#         "total": len(booking_list) if doc_status else total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
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
#     booking_id: str = Form(...),
#     content: str = Form(...),
#     current_user: dict = Depends(require_admin)
# ):
#     """Create a new note for a booking"""
#     if not content.strip():
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
#     content: str = Form(...),
#     current_user: dict = Depends(require_admin)
# ):
#     """Update an existing note"""
#     if not content.strip():
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
    
    # Build query
    query = {"isDeleted": False}
    
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
    
    total_bookings = await bookings_collection.count_documents({"isDeleted": False})
    
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



