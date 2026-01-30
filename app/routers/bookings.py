
# """
# Bookings Router
# Handles all booking operations including CRUD, filters, and copy
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from datetime import datetime, date
# from bson import ObjectId
# from typing import Optional, List
# import json

# from app.models.schemas import (
#     BookingCreate, BookingUpdate, BookingResponse, BookingFilter,
#     BookingStatus, BranchName, UserRole, EditHistory
# )
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user, require_admin
# from app.utils.email_service import send_welcome_email

# router = APIRouter()

# def serialize_booking(booking: dict, include_edit_history: bool = False) -> dict:
#     """Convert MongoDB booking to response format"""
#     # Calculate received and pending amounts
#     term_1 = booking.get("term_1") or 0
#     term_2 = booking.get("term_2") or 0
#     term_3 = booking.get("term_3") or 0
#     received_amount = term_1 + term_2 + term_3
#     total_amount = booking.get("total_amount", 0)
#     pending_amount = total_amount - received_amount
    
#     result = {
#         "id": str(booking["_id"]),
#         "user_id": booking.get("user_id", ""),
#         "bdm": booking.get("bdm", ""),
#         "branch_name": booking.get("branch_name", ""),
#         "company_name": booking.get("company_name", ""),
#         "contact_person": booking.get("contact_person", ""),
#         "email": booking.get("email", ""),
#         "contact_no": str(booking.get("contact_no", "")),
#         "services": booking.get("services", []),
#         "total_amount": total_amount,
#         "term_1": term_1 if term_1 else None,
#         "term_2": term_2 if term_2 else None,
#         "term_3": term_3 if term_3 else None,
#         "payment_date": booking.get("payment_date"),
#         "closed_by": booking.get("closed_by", ""),
#         "pan": booking.get("pan"),
#         "gst": booking.get("gst"),
#         "remark": booking.get("remark"),
#         "after_disbursement": booking.get("after_disbursement"),
#         "bank": booking.get("bank"),
#         "state": booking.get("state"),
#         "status": booking.get("status", BookingStatus.PENDING),
#         "received_amount": received_amount,
#         "pending_amount": max(0, pending_amount),
#         "date": booking.get("date", booking.get("createdAt")),
#         "isDeleted": booking.get("isDeleted", False),
#         "created_at": booking.get("createdAt", datetime.utcnow()),
#         "updated_at": booking.get("updatedAt", datetime.utcnow())
#     }
    
#     if include_edit_history:
#         result["updatedhistory"] = booking.get("updatedhistory", [])
    
#     return result

# @router.get("/")
# async def get_all_bookings(
#     # Date filters
#     start_date: Optional[datetime] = Query(None, description="Filter by booking start date"),
#     end_date: Optional[datetime] = Query(None, description="Filter by booking end date"),
#     payment_start_date: Optional[datetime] = Query(None, description="Filter by payment start date"),
#     payment_end_date: Optional[datetime] = Query(None, description="Filter by payment end date"),
#     # Other filters
#     services: Optional[str] = Query(None, description="Comma-separated service names"),
#     bdm_name: Optional[str] = Query(None, description="Filter by BDM name"),
#     company_name: Optional[str] = Query(None, description="Search company name"),
#     search: Optional[str] = Query(None, description="Search by company name or booking ID"),
#     status: Optional[BookingStatus] = Query(None, description="Filter by status"),
#     branch: Optional[BranchName] = Query(None, description="Filter by branch"),
#     # Pagination
#     page: int = Query(1, ge=1),
#     page_size: int = Query(20, ge=1, le=10000),
#     # Sorting
#     sort_by: str = Query("date", description="Sort field"),
#     sort_order: int = Query(-1, description="-1 for desc, 1 for asc"),
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Get all bookings with advanced filtering
#     BDM can only see their own bookings
#     """
#     bookings_collection = get_collection("bookings")
    
#     # Build query
#     query = {"isDeleted": False}
    
#     # Role-based filtering
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     # Date filters
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     if payment_start_date or payment_end_date:
#         query["payment_date"] = {}
#         if payment_start_date:
#             query["payment_date"]["$gte"] = payment_start_date
#         if payment_end_date:
#             query["payment_date"]["$lte"] = payment_end_date
    
#     # Service filter
#     if services:
#         service_list = [s.strip() for s in services.split(",")]
#         query["services"] = {"$in": service_list}
    
#     # BDM filter
#     if bdm_name:
#         query["bdm"] = {"$regex": bdm_name, "$options": "i"}
    
#     # Search by company name OR booking ID
#     if search:
#         search_conditions = [
#             {"company_name": {"$regex": search, "$options": "i"}}
#         ]
#         # Check if search looks like a MongoDB ObjectId (24 hex chars)
#         if len(search) == 24:
#             try:
#                 search_conditions.append({"_id": ObjectId(search)})
#             except:
#                 pass
#         # Also try partial ID match at the end
#         if len(search) >= 4:
#             search_conditions.append({"_id": {"$regex": search, "$options": "i"}})
#         query["$or"] = search_conditions
#     elif company_name:
#         query["company_name"] = {"$regex": company_name, "$options": "i"}
    
#     # Status filter
#     if status:
#         query["status"] = status
    
#     # Branch filter
#     if branch:
#         query["branch_name"] = branch
    
#     # Get total count
#     total = await bookings_collection.count_documents(query)
    
#     # Get paginated results
#     skip = (page - 1) * page_size
#     cursor = bookings_collection.find(query).skip(skip).limit(page_size).sort(sort_by, sort_order)
    
#     bookings = []
#     async for booking in cursor:
#         bookings.append(serialize_booking(booking))
    
#     return {
#         "items": bookings,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
#     }

# @router.get("/search")
# async def search_bookings(
#     q: str = Query(..., min_length=1, description="Search query"),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Quick search across multiple fields"""
#     bookings_collection = get_collection("bookings")
    
#     query = {
#         "isDeleted": False,
#         "$or": [
#             {"company_name": {"$regex": q, "$options": "i"}},
#             {"contact_person": {"$regex": q, "$options": "i"}},
#             {"email": {"$regex": q, "$options": "i"}},
#             {"bdm": {"$regex": q, "$options": "i"}}
#         ]
#     }
    
#     # Role-based filtering
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     cursor = bookings_collection.find(query).limit(20).sort("date", -1)
    
#     bookings = []
#     async for booking in cursor:
#         bookings.append(serialize_booking(booking))
    
#     return bookings

# @router.get("/{booking_id}")
# async def get_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
#     """Get single booking with edit history"""
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Role-based access check
#     if current_user["role"] == UserRole.BDM and booking.get("user_id") != current_user["id"]:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="You can only view your own bookings"
#         )
    
#     return serialize_booking(booking, include_edit_history=True)

# @router.post("/")
# async def create_booking(
#     booking_data: BookingCreate,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Create new booking
#     Sends welcome email after creation
#     """
#     bookings_collection = get_collection("bookings")
    
#     # Create booking document
#     now = datetime.utcnow()
#     new_booking = {
#         "user_id": current_user["id"],
#         "bdm": current_user["name"],
#         "branch_name": booking_data.branch_name,
#         "company_name": booking_data.company_name,
#         "contact_person": booking_data.contact_person,
#         "email": booking_data.email,
#         "contact_no": booking_data.contact_no,
#         "services": booking_data.services,
#         "total_amount": booking_data.total_amount,
#         "term_1": booking_data.term_1,
#         "term_2": booking_data.term_2,
#         "term_3": booking_data.term_3,
#         "payment_date": booking_data.payment_date,
#         "closed_by": booking_data.closed_by,
#         "pan": booking_data.pan,
#         "gst": booking_data.gst,
#         "remark": booking_data.remark,
#         "after_disbursement": booking_data.after_disbursement,
#         "bank": booking_data.bank,
#         "state": booking_data.state,
#         "status": BookingStatus.PENDING,
#         "date": now,  # Auto-set to today
#         "isDeleted": False,
#         "deletedAt": None,
#         "deletedBy": None,
#         "updatedhistory": [],
#         "createdAt": now,
#         "updatedAt": now
#     }
    
#     result = await bookings_collection.insert_one(new_booking)
#     new_booking["_id"] = result.inserted_id
    
#     return serialize_booking(new_booking)

# @router.post("/{booking_id}/copy")
# async def copy_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
#     """
#     Copy/duplicate a booking
#     Creates a new booking with same details
#     """
#     bookings_collection = get_collection("bookings")
    
#     try:
#         original = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not original:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Create copy
#     now = datetime.utcnow()
#     copy_booking = {
#         "user_id": current_user["id"],
#         "bdm": current_user["name"],
#         "branch_name": original["branch_name"],
#         "company_name": f"{original['company_name']} (Copy)",
#         "contact_person": original["contact_person"],
#         "email": original["email"],
#         "contact_no": original["contact_no"],
#         "services": original["services"],
#         "total_amount": original["total_amount"],
#         "term_1": None,  # Reset payments
#         "term_2": None,
#         "term_3": None,
#         "payment_date": None,
#         "closed_by": original.get("closed_by", ""),
#         "pan": original.get("pan"),
#         "gst": original.get("gst"),
#         "remark": original.get("remark"),
#         "after_disbursement": original.get("after_disbursement"),
#         "bank": original.get("bank"),
#         "state": original.get("state"),
#         "status": BookingStatus.PENDING,
#         "date": now,
#         "isDeleted": False,
#         "deletedAt": None,
#         "deletedBy": None,
#         "updatedhistory": [],
#         "createdAt": now,
#         "updatedAt": now
#     }
    
#     result = await bookings_collection.insert_one(copy_booking)
#     copy_booking["_id"] = result.inserted_id
    
#     return serialize_booking(copy_booking)

# @router.put("/{booking_id}")
# async def update_booking(
#     booking_id: str,
#     booking_data: BookingUpdate,
#     current_user: dict = Depends(require_admin)
# ):
#     """
#     Update booking (SRDEV and Senior Admin only)
#     Tracks all changes in edit history
#     """
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Build update dict and track changes
#     update_dict = {"updatedAt": datetime.utcnow()}
#     changes = {}
    
#     update_fields = booking_data.model_dump(exclude_unset=True)
    
#     for field, new_value in update_fields.items():
#         if new_value is not None:
#             old_value = booking.get(field)
#             if old_value != new_value:
#                 changes[field] = {
#                     "old": str(old_value) if old_value else None,
#                     "new": str(new_value)
#                 }
#                 update_dict[field] = new_value
    
#     if changes:
#         # Add edit history entry
#         edit_entry = {
#             "edited_by": current_user["id"],
#             "edited_by_name": current_user["name"],
#             "edited_at": datetime.utcnow().isoformat(),
#             "changes": changes
#         }
        
#         await bookings_collection.update_one(
#             {"_id": ObjectId(booking_id)},
#             {
#                 "$set": update_dict,
#                 "$push": {"updatedhistory": edit_entry}
#             }
#         )
    
#     # Get updated booking
#     updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     return serialize_booking(updated, include_edit_history=True)

# @router.delete("/{booking_id}")
# async def delete_booking(booking_id: str, current_user: dict = Depends(require_admin)):
#     """
#     Soft delete booking (SRDEV and Senior Admin only)
#     Moves to trash
#     """
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Soft delete
#     await bookings_collection.update_one(
#         {"_id": ObjectId(booking_id)},
#         {"$set": {
#             "isDeleted": True,
#             "deletedAt": datetime.utcnow(),
#             "deletedBy": current_user["id"],
#             "deletedByName": current_user["name"],
#             "updatedAt": datetime.utcnow()
#         }}
#     )
    
#     return {"message": "Booking moved to trash"}

# @router.get("/{booking_id}/edit-history")
# async def get_edit_history(booking_id: str, current_user: dict = Depends(require_admin)):
#     """Get edit history for a booking"""
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one(
#             {"_id": ObjectId(booking_id)},
#             {"updatedhistory": 1}
#         )
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     return booking.get("updatedhistory", [])

# @router.post("/import")
# async def import_bookings(bookings: List[dict], current_user: dict = Depends(require_admin)):
#     """
#     Import bookings from JSON
#     Used for initial data migration
#     """
#     bookings_collection = get_collection("bookings")
    
#     imported_count = 0
#     errors = []
    
#     for booking in bookings:
#         try:
#             # Remove _id if present (MongoDB will generate new one)
#             if "_id" in booking:
#                 del booking["_id"]
            
#             # Ensure required fields
#             if "createdAt" not in booking:
#                 booking["createdAt"] = datetime.utcnow()
#             if "updatedAt" not in booking:
#                 booking["updatedAt"] = datetime.utcnow()
#             if "isDeleted" not in booking:
#                 booking["isDeleted"] = False
#             if "status" not in booking:
#                 booking["status"] = BookingStatus.PENDING
            
#             await bookings_collection.insert_one(booking)
#             imported_count += 1
#         except Exception as e:
#             errors.append(str(e))
    
#     return {
#         "imported": imported_count,
#         "errors": errors,
#         "total": len(bookings)
#     }











# """
# Bookings Router
# Handles all booking operations including CRUD, filters, and copy
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from datetime import datetime, date
# from bson import ObjectId
# from typing import Optional, List
# import json

# from app.models.schemas import (
#     BookingCreate, BookingUpdate, BookingResponse, BookingFilter,
#     BookingStatus, BranchName, UserRole, EditHistory
# )
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user, require_admin
# from app.utils.email_service import send_welcome_email

# router = APIRouter()

# def serialize_booking(booking: dict, include_edit_history: bool = False) -> dict:
#     """Convert MongoDB booking to response format"""
#     # Calculate received and pending amounts
#     term_1 = booking.get("term_1") or 0
#     term_2 = booking.get("term_2") or 0
#     term_3 = booking.get("term_3") or 0
#     received_amount = term_1 + term_2 + term_3
#     total_amount = booking.get("total_amount", 0)
#     pending_amount = total_amount - received_amount
    
#     result = {
#         "id": str(booking["_id"]),
#         "user_id": booking.get("user_id", ""),
#         "bdm": booking.get("bdm", ""),
#         "branch_name": booking.get("branch_name", ""),
#         "company_name": booking.get("company_name", ""),
#         "contact_person": booking.get("contact_person", ""),
#         "email": booking.get("email", ""),
#         "contact_no": str(booking.get("contact_no", "")),
#         "services": booking.get("services", []),
#         "total_amount": total_amount,
#         "term_1": term_1 if term_1 else None,
#         "term_2": term_2 if term_2 else None,
#         "term_3": term_3 if term_3 else None,
#         "payment_date": booking.get("payment_date"),
#         "closed_by": booking.get("closed_by", ""),
#         "pan": booking.get("pan"),
#         "gst": booking.get("gst"),
#         "remark": booking.get("remark"),
#         "after_disbursement": booking.get("after_disbursement"),
#         "bank": booking.get("bank"),
#         "state": booking.get("state"),
#         "status": booking.get("status", BookingStatus.PENDING),
#         "received_amount": received_amount,
#         "pending_amount": max(0, pending_amount),
#         "date": booking.get("date", booking.get("createdAt")),
#         "isDeleted": booking.get("isDeleted", False),
#         "created_at": booking.get("createdAt", datetime.utcnow()),
#         "updated_at": booking.get("updatedAt", datetime.utcnow())
#     }
    
#     if include_edit_history:
#         result["updatedhistory"] = booking.get("updatedhistory", [])
    
#     return result

# @router.get("/")
# async def get_all_bookings(
#     # Date filters
#     start_date: Optional[datetime] = Query(None, description="Filter by booking start date"),
#     end_date: Optional[datetime] = Query(None, description="Filter by booking end date"),
#     payment_start_date: Optional[datetime] = Query(None, description="Filter by payment start date"),
#     payment_end_date: Optional[datetime] = Query(None, description="Filter by payment end date"),
#     # Other filters
#     services: Optional[str] = Query(None, description="Comma-separated service names"),
#     bdm_name: Optional[str] = Query(None, description="Filter by BDM name"),
#     company_name: Optional[str] = Query(None, description="Search company name"),
#     search: Optional[str] = Query(None, description="Search by company name or booking ID"),
#     status: Optional[BookingStatus] = Query(None, description="Filter by status"),
#     branch: Optional[BranchName] = Query(None, description="Filter by branch"),
#     # Pagination
#     page: int = Query(1, ge=1),
#     page_size: int = Query(20, ge=1, le=10000),
#     # Sorting
#     sort_by: str = Query("date", description="Sort field"),
#     sort_order: int = Query(-1, description="-1 for desc, 1 for asc"),
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Get all bookings with advanced filtering
#     BDM can only see their own bookings
#     """
#     bookings_collection = get_collection("bookings")
    
#     # Build query
#     query = {"isDeleted": False}
    
#     # Role-based filtering - BDM sees bookings by user_id OR by bdm name
#     if current_user["role"] == UserRole.BDM:
#         query["$or"] = [
#             {"user_id": current_user["id"]},
#             {"bdm": {"$regex": f"^{current_user['name']}$", "$options": "i"}}
#         ]
    
#     # Date filters
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     if payment_start_date or payment_end_date:
#         query["payment_date"] = {}
#         if payment_start_date:
#             query["payment_date"]["$gte"] = payment_start_date
#         if payment_end_date:
#             query["payment_date"]["$lte"] = payment_end_date
    
#     # Service filter
#     if services:
#         service_list = [s.strip() for s in services.split(",")]
#         query["services"] = {"$in": service_list}
    
#     # BDM filter
#     if bdm_name:
#         query["bdm"] = {"$regex": bdm_name, "$options": "i"}
    
#     # Search by company name OR booking ID
#     if search:
#         search_conditions = [
#             {"company_name": {"$regex": search, "$options": "i"}}
#         ]
#         # Check if search looks like a MongoDB ObjectId (24 hex chars)
#         if len(search) == 24:
#             try:
#                 search_conditions.append({"_id": ObjectId(search)})
#             except:
#                 pass
#         query["$or"] = search_conditions
#     elif company_name:
#         query["company_name"] = {"$regex": company_name, "$options": "i"}
    
#     # Status filter
#     if status:
#         query["status"] = status
    
#     # Branch filter
#     if branch:
#         query["branch_name"] = branch
    
#     # Get total count
#     total = await bookings_collection.count_documents(query)
    
#     # Get paginated results
#     skip = (page - 1) * page_size
#     cursor = bookings_collection.find(query).skip(skip).limit(page_size).sort(sort_by, sort_order)
    
#     bookings = []
#     async for booking in cursor:
#         bookings.append(serialize_booking(booking))
    
#     return {
#         "items": bookings,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
#     }

# @router.get("/search")
# async def search_bookings(
#     q: str = Query(..., min_length=1, description="Search query"),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Quick search across multiple fields"""
#     bookings_collection = get_collection("bookings")
    
#     query = {
#         "isDeleted": False,
#         "$or": [
#             {"company_name": {"$regex": q, "$options": "i"}},
#             {"contact_person": {"$regex": q, "$options": "i"}},
#             {"email": {"$regex": q, "$options": "i"}},
#             {"bdm": {"$regex": q, "$options": "i"}}
#         ]
#     }
    
#     # Role-based filtering
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     cursor = bookings_collection.find(query).limit(20).sort("date", -1)
    
#     bookings = []
#     async for booking in cursor:
#         bookings.append(serialize_booking(booking))
    
#     return bookings

# @router.get("/{booking_id}")
# async def get_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
#     """Get single booking with edit history"""
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Role-based access check
#     if current_user["role"] == UserRole.BDM and booking.get("user_id") != current_user["id"]:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="You can only view your own bookings"
#         )
    
#     return serialize_booking(booking, include_edit_history=True)

# @router.post("/")
# async def create_booking(
#     booking_data: BookingCreate,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Create new booking
#     Sends welcome email after creation
#     """
#     bookings_collection = get_collection("bookings")
    
#     # Create booking document
#     now = datetime.utcnow()
#     new_booking = {
#         "user_id": current_user["id"],
#         "bdm": current_user["name"],
#         "branch_name": booking_data.branch_name,
#         "company_name": booking_data.company_name,
#         "contact_person": booking_data.contact_person,
#         "email": booking_data.email,
#         "contact_no": booking_data.contact_no,
#         "services": booking_data.services,
#         "total_amount": booking_data.total_amount,
#         "term_1": booking_data.term_1,
#         "term_2": booking_data.term_2,
#         "term_3": booking_data.term_3,
#         "payment_date": booking_data.payment_date,
#         "closed_by": booking_data.closed_by,
#         "pan": booking_data.pan,
#         "gst": booking_data.gst,
#         "remark": booking_data.remark,
#         "after_disbursement": booking_data.after_disbursement,
#         "bank": booking_data.bank,
#         "state": booking_data.state,
#         "status": BookingStatus.PENDING,
#         "date": now,  # Auto-set to today
#         "isDeleted": False,
#         "deletedAt": None,
#         "deletedBy": None,
#         "updatedhistory": [],
#         "createdAt": now,
#         "updatedAt": now
#     }
    
#     result = await bookings_collection.insert_one(new_booking)
#     new_booking["_id"] = result.inserted_id
    
#     return serialize_booking(new_booking)

# @router.post("/{booking_id}/copy")
# async def copy_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
#     """
#     Copy/duplicate a booking
#     Creates a new booking with same details
#     """
#     bookings_collection = get_collection("bookings")
    
#     try:
#         original = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not original:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Create copy
#     now = datetime.utcnow()
#     copy_booking = {
#         "user_id": current_user["id"],
#         "bdm": current_user["name"],
#         "branch_name": original["branch_name"],
#         "company_name": f"{original['company_name']} (Copy)",
#         "contact_person": original["contact_person"],
#         "email": original["email"],
#         "contact_no": original["contact_no"],
#         "services": original["services"],
#         "total_amount": original["total_amount"],
#         "term_1": None,  # Reset payments
#         "term_2": None,
#         "term_3": None,
#         "payment_date": None,
#         "closed_by": original.get("closed_by", ""),
#         "pan": original.get("pan"),
#         "gst": original.get("gst"),
#         "remark": original.get("remark"),
#         "after_disbursement": original.get("after_disbursement"),
#         "bank": original.get("bank"),
#         "state": original.get("state"),
#         "status": BookingStatus.PENDING,
#         "date": now,
#         "isDeleted": False,
#         "deletedAt": None,
#         "deletedBy": None,
#         "updatedhistory": [],
#         "createdAt": now,
#         "updatedAt": now
#     }
    
#     result = await bookings_collection.insert_one(copy_booking)
#     copy_booking["_id"] = result.inserted_id
    
#     return serialize_booking(copy_booking)

# @router.put("/{booking_id}")
# async def update_booking(
#     booking_id: str,
#     booking_data: BookingUpdate,
#     current_user: dict = Depends(require_admin)
# ):
#     """
#     Update booking (SRDEV and Senior Admin only)
#     Tracks all changes in edit history
#     """
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Build update dict and track changes
#     update_dict = {"updatedAt": datetime.utcnow()}
#     changes = {}
    
#     update_fields = booking_data.model_dump(exclude_unset=True)
    
#     for field, new_value in update_fields.items():
#         if new_value is not None:
#             old_value = booking.get(field)
#             if old_value != new_value:
#                 changes[field] = {
#                     "old": str(old_value) if old_value else None,
#                     "new": str(new_value)
#                 }
#                 update_dict[field] = new_value
    
#     if changes:
#         # Add edit history entry
#         edit_entry = {
#             "edited_by": current_user["id"],
#             "edited_by_name": current_user["name"],
#             "edited_at": datetime.utcnow().isoformat(),
#             "changes": changes
#         }
        
#         await bookings_collection.update_one(
#             {"_id": ObjectId(booking_id)},
#             {
#                 "$set": update_dict,
#                 "$push": {"updatedhistory": edit_entry}
#             }
#         )
    
#     # Get updated booking
#     updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     return serialize_booking(updated, include_edit_history=True)

# @router.delete("/{booking_id}")
# async def delete_booking(booking_id: str, current_user: dict = Depends(require_admin)):
#     """
#     Soft delete booking (SRDEV and Senior Admin only)
#     Moves to trash
#     """
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     # Soft delete
#     await bookings_collection.update_one(
#         {"_id": ObjectId(booking_id)},
#         {"$set": {
#             "isDeleted": True,
#             "deletedAt": datetime.utcnow(),
#             "deletedBy": current_user["id"],
#             "deletedByName": current_user["name"],
#             "updatedAt": datetime.utcnow()
#         }}
#     )
    
#     return {"message": "Booking moved to trash"}

# @router.get("/{booking_id}/edit-history")
# async def get_edit_history(booking_id: str, current_user: dict = Depends(require_admin)):
#     """Get edit history for a booking"""
#     bookings_collection = get_collection("bookings")
    
#     try:
#         booking = await bookings_collection.find_one(
#             {"_id": ObjectId(booking_id)},
#             {"updatedhistory": 1}
#         )
#     except:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid booking ID format"
#         )
    
#     if not booking:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Booking not found"
#         )
    
#     return booking.get("updatedhistory", [])

# @router.post("/import")
# async def import_bookings(bookings: List[dict], current_user: dict = Depends(require_admin)):
#     """
#     Import bookings from JSON
#     Used for initial data migration
#     """
#     bookings_collection = get_collection("bookings")
    
#     imported_count = 0
#     errors = []
    
#     for booking in bookings:
#         try:
#             # Remove _id if present (MongoDB will generate new one)
#             if "_id" in booking:
#                 del booking["_id"]
            
#             # Ensure required fields
#             if "createdAt" not in booking:
#                 booking["createdAt"] = datetime.utcnow()
#             if "updatedAt" not in booking:
#                 booking["updatedAt"] = datetime.utcnow()
#             if "isDeleted" not in booking:
#                 booking["isDeleted"] = False
#             if "status" not in booking:
#                 booking["status"] = BookingStatus.PENDING
            
#             await bookings_collection.insert_one(booking)
#             imported_count += 1
#         except Exception as e:
#             errors.append(str(e))
    
#     return {
#         "imported": imported_count,
#         "errors": errors,
#         "total": len(bookings)
#     }

















"""
Bookings Router
Handles all booking operations including CRUD, filters, and copy
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, date
from bson import ObjectId
from typing import Optional, List
import json

from app.models.schemas import (
    BookingCreate, BookingUpdate, BookingResponse, BookingFilter,
    BookingStatus, BranchName, UserRole, EditHistory
)
from app.utils.database import get_collection
from app.utils.auth import get_current_user, require_admin
from app.utils.email_service import send_welcome_email

router = APIRouter()

def serialize_booking(booking: dict, include_edit_history: bool = False) -> dict:
    """Convert MongoDB booking to response format"""
    # Calculate received and pending amounts
    term_1 = booking.get("term_1") or 0
    term_2 = booking.get("term_2") or 0
    term_3 = booking.get("term_3") or 0
    received_amount = term_1 + term_2 + term_3
    total_amount = booking.get("total_amount", 0)
    pending_amount = total_amount - received_amount
    
    result = {
        "id": str(booking["_id"]),
        "user_id": booking.get("user_id", ""),
        "bdm": booking.get("bdm", ""),
        "branch_name": booking.get("branch_name", ""),
        "company_name": booking.get("company_name", ""),
        "contact_person": booking.get("contact_person", ""),
        "email": booking.get("email", ""),
        "contact_no": str(booking.get("contact_no", "")),
        "services": booking.get("services", []),
        "total_amount": total_amount,
        "term_1": term_1 if term_1 else None,
        "term_2": term_2 if term_2 else None,
        "term_3": term_3 if term_3 else None,
        "payment_date": booking.get("payment_date"),
        "closed_by": booking.get("closed_by", ""),
        "pan": booking.get("pan"),
        "gst": booking.get("gst"),
        "remark": booking.get("remark"),
        "after_disbursement": booking.get("after_disbursement"),
        "bank": booking.get("bank"),
        "state": booking.get("state"),
        "status": booking.get("status", BookingStatus.PENDING),
        "received_amount": received_amount,
        "pending_amount": max(0, pending_amount),
        "date": booking.get("date", booking.get("createdAt")),
        "isDeleted": booking.get("isDeleted", False),
        "created_at": booking.get("createdAt", datetime.utcnow()),
        "updated_at": booking.get("updatedAt", datetime.utcnow())
    }
    
    if include_edit_history:
        result["updatedhistory"] = booking.get("updatedhistory", [])
    
    return result

@router.get("/")
async def get_all_bookings(
    # Date filters
    start_date: Optional[datetime] = Query(None, description="Filter by booking start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by booking end date"),
    payment_start_date: Optional[datetime] = Query(None, description="Filter by payment start date"),
    payment_end_date: Optional[datetime] = Query(None, description="Filter by payment end date"),
    # Other filters
    services: Optional[str] = Query(None, description="Comma-separated service names"),
    bdm_name: Optional[str] = Query(None, description="Filter by BDM name"),
    company_name: Optional[str] = Query(None, description="Search company name"),
    search: Optional[str] = Query(None, description="Search by company name or booking ID"),
    status: Optional[BookingStatus] = Query(None, description="Filter by status"),
    branch: Optional[BranchName] = Query(None, description="Filter by branch"),
    # Pagination
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=10000),
    # Sorting
    sort_by: str = Query("date", description="Sort field"),
    sort_order: int = Query(-1, description="-1 for desc, 1 for asc"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all bookings with advanced filtering
    BDM can only see their own bookings
    """
    bookings_collection = get_collection("bookings")
    
    # Build query
    query = {"isDeleted": False}
    
    # Role-based filtering - BDM sees bookings by user_id OR by bdm name
    if current_user["role"] == UserRole.BDM:
        query["$or"] = [
            {"user_id": current_user["id"]},
            {"bdm": {"$regex": f"^{current_user['name']}$", "$options": "i"}}
        ]
    
    # Date filters
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    if payment_start_date or payment_end_date:
        query["payment_date"] = {}
        if payment_start_date:
            query["payment_date"]["$gte"] = payment_start_date
        if payment_end_date:
            query["payment_date"]["$lte"] = payment_end_date
    
    # Service filter
    if services:
        service_list = [s.strip() for s in services.split(",")]
        query["services"] = {"$in": service_list}
    
    # BDM filter
    if bdm_name:
        query["bdm"] = {"$regex": bdm_name, "$options": "i"}
    
    # Search by company name OR booking ID
    if search:
        search_conditions = [
            {"company_name": {"$regex": search, "$options": "i"}}
        ]
        # Check if search looks like a MongoDB ObjectId (24 hex chars)
        if len(search) == 24:
            try:
                search_conditions.append({"_id": ObjectId(search)})
            except:
                pass
        query["$or"] = search_conditions
    elif company_name:
        query["company_name"] = {"$regex": company_name, "$options": "i"}
    
    # Status filter
    if status:
        query["status"] = status
    
    # Branch filter
    if branch:
        query["branch_name"] = branch
    
    # Get total count
    total = await bookings_collection.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    cursor = bookings_collection.find(query).skip(skip).limit(page_size).sort(sort_by, sort_order)
    
    bookings = []
    async for booking in cursor:
        bookings.append(serialize_booking(booking))
    
    return {
        "items": bookings,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.get("/search")
async def search_bookings(
    q: str = Query(..., min_length=1, description="Search query"),
    current_user: dict = Depends(get_current_user)
):
    """Quick search across multiple fields"""
    bookings_collection = get_collection("bookings")
    
    query = {
        "isDeleted": False,
        "$or": [
            {"company_name": {"$regex": q, "$options": "i"}},
            {"contact_person": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"bdm": {"$regex": q, "$options": "i"}}
        ]
    }
    
    # Role-based filtering - BDM sees bookings by user_id OR by bdm name
    if current_user["role"] == UserRole.BDM:
        query["$and"] = [
            {"$or": query.pop("$or")},
            {"$or": [
                {"user_id": current_user["id"]},
                {"bdm": {"$regex": f"^{current_user['name']}$", "$options": "i"}}
            ]}
        ]
    
    cursor = bookings_collection.find(query).limit(20).sort("date", -1)
    
    bookings = []
    async for booking in cursor:
        bookings.append(serialize_booking(booking))
    
    return bookings

@router.get("/{booking_id}")
async def get_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    """Get single booking with edit history"""
    bookings_collection = get_collection("bookings")
    
    try:
        booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Role-based access check - BDM can view by user_id OR by bdm name match
    if current_user["role"] == UserRole.BDM:
        is_owner_by_id = booking.get("user_id") == current_user["id"]
        is_owner_by_name = booking.get("bdm", "").lower() == current_user["name"].lower()
        if not is_owner_by_id and not is_owner_by_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own bookings"
            )
    
    return serialize_booking(booking, include_edit_history=True)

@router.post("/")
async def create_booking(
    booking_data: BookingCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create new booking
    Sends welcome email after creation
    """
    bookings_collection = get_collection("bookings")
    
    # Create booking document
    now = datetime.utcnow()
    new_booking = {
        "user_id": current_user["id"],
        "bdm": current_user["name"],
        "branch_name": booking_data.branch_name,
        "company_name": booking_data.company_name,
        "contact_person": booking_data.contact_person,
        "email": booking_data.email,
        "contact_no": booking_data.contact_no,
        "services": booking_data.services,
        "total_amount": booking_data.total_amount,
        "term_1": booking_data.term_1,
        "term_2": booking_data.term_2,
        "term_3": booking_data.term_3,
        "payment_date": booking_data.payment_date,
        "closed_by": booking_data.closed_by,
        "pan": booking_data.pan,
        "gst": booking_data.gst,
        "remark": booking_data.remark,
        "after_disbursement": booking_data.after_disbursement,
        "bank": booking_data.bank,
        "state": booking_data.state,
        "status": BookingStatus.PENDING,
        "date": now,  # Auto-set to today
        "isDeleted": False,
        "deletedAt": None,
        "deletedBy": None,
        "updatedhistory": [],
        "createdAt": now,
        "updatedAt": now
    }
    
    result = await bookings_collection.insert_one(new_booking)
    new_booking["_id"] = result.inserted_id
    
    return serialize_booking(new_booking)

@router.post("/{booking_id}/copy")
async def copy_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
    """
    Copy/duplicate a booking
    Creates a new booking with same details
    """
    bookings_collection = get_collection("bookings")
    
    try:
        original = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Create copy
    now = datetime.utcnow()
    copy_booking = {
        "user_id": current_user["id"],
        "bdm": current_user["name"],
        "branch_name": original["branch_name"],
        "company_name": f"{original['company_name']} (Copy)",
        "contact_person": original["contact_person"],
        "email": original["email"],
        "contact_no": original["contact_no"],
        "services": original["services"],
        "total_amount": original["total_amount"],
        "term_1": None,  # Reset payments
        "term_2": None,
        "term_3": None,
        "payment_date": None,
        "closed_by": original.get("closed_by", ""),
        "pan": original.get("pan"),
        "gst": original.get("gst"),
        "remark": original.get("remark"),
        "after_disbursement": original.get("after_disbursement"),
        "bank": original.get("bank"),
        "state": original.get("state"),
        "status": BookingStatus.PENDING,
        "date": now,
        "isDeleted": False,
        "deletedAt": None,
        "deletedBy": None,
        "updatedhistory": [],
        "createdAt": now,
        "updatedAt": now
    }
    
    result = await bookings_collection.insert_one(copy_booking)
    copy_booking["_id"] = result.inserted_id
    
    return serialize_booking(copy_booking)

@router.put("/{booking_id}")
async def update_booking(
    booking_id: str,
    booking_data: BookingUpdate,
    current_user: dict = Depends(require_admin)
):
    """
    Update booking (SRDEV and Senior Admin only)
    Tracks all changes in edit history
    """
    bookings_collection = get_collection("bookings")
    
    try:
        booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Build update dict and track changes
    update_dict = {"updatedAt": datetime.utcnow()}
    changes = {}
    
    update_fields = booking_data.model_dump(exclude_unset=True)
    
    for field, new_value in update_fields.items():
        if new_value is not None:
            old_value = booking.get(field)
            if old_value != new_value:
                changes[field] = {
                    "old": str(old_value) if old_value else None,
                    "new": str(new_value)
                }
                update_dict[field] = new_value
    
    if changes:
        # Add edit history entry
        edit_entry = {
            "edited_by": current_user["id"],
            "edited_by_name": current_user["name"],
            "edited_at": datetime.utcnow().isoformat(),
            "changes": changes
        }
        
        await bookings_collection.update_one(
            {"_id": ObjectId(booking_id)},
            {
                "$set": update_dict,
                "$push": {"updatedhistory": edit_entry}
            }
        )
    
    # Get updated booking
    updated = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    return serialize_booking(updated, include_edit_history=True)

@router.delete("/{booking_id}")
async def delete_booking(booking_id: str, current_user: dict = Depends(require_admin)):
    """
    Soft delete booking (SRDEV and Senior Admin only)
    Moves to trash
    """
    bookings_collection = get_collection("bookings")
    
    try:
        booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Soft delete
    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {
            "isDeleted": True,
            "deletedAt": datetime.utcnow(),
            "deletedBy": current_user["id"],
            "deletedByName": current_user["name"],
            "updatedAt": datetime.utcnow()
        }}
    )
    
    return {"message": "Booking moved to trash"}

@router.get("/{booking_id}/edit-history")
async def get_edit_history(booking_id: str, current_user: dict = Depends(require_admin)):
    """Get edit history for a booking"""
    bookings_collection = get_collection("bookings")
    
    try:
        booking = await bookings_collection.find_one(
            {"_id": ObjectId(booking_id)},
            {"updatedhistory": 1}
        )
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking.get("updatedhistory", [])

@router.post("/import")
async def import_bookings(bookings: List[dict], current_user: dict = Depends(require_admin)):
    """
    Import bookings from JSON
    Used for initial data migration
    """
    bookings_collection = get_collection("bookings")
    
    imported_count = 0
    errors = []
    
    for booking in bookings:
        try:
            # Remove _id if present (MongoDB will generate new one)
            if "_id" in booking:
                del booking["_id"]
            
            # Ensure required fields
            if "createdAt" not in booking:
                booking["createdAt"] = datetime.utcnow()
            if "updatedAt" not in booking:
                booking["updatedAt"] = datetime.utcnow()
            if "isDeleted" not in booking:
                booking["isDeleted"] = False
            if "status" not in booking:
                booking["status"] = BookingStatus.PENDING
            
            await bookings_collection.insert_one(booking)
            imported_count += 1
        except Exception as e:
            errors.append(str(e))
    
    return {
        "imported": imported_count,
        "errors": errors,
        "total": len(bookings)
    }
