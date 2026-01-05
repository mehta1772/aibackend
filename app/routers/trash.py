"""
Trash Router
Handles deleted bookings - restore and permanent delete
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional

from app.models.schemas import UserRole
from app.utils.database import get_collection
from app.utils.auth import get_current_user, require_admin

router = APIRouter()

@router.get("/")
async def get_trash_bookings(
    search: Optional[str] = Query(None, description="Search company name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_admin)
):
    """
    Get all deleted bookings (Admin/SRDEV only)
    Shows who deleted and when
    """
    bookings_collection = get_collection("bookings")
    
    query = {"isDeleted": True}
    
    if search:
        query["company_name"] = {"$regex": search, "$options": "i"}
    
    total = await bookings_collection.count_documents(query)
    
    skip = (page - 1) * page_size
    cursor = bookings_collection.find(query).skip(skip).limit(page_size).sort("deletedAt", -1)
    
    bookings = []
    async for booking in cursor:
        term_1 = booking.get("term_1") or 0
        term_2 = booking.get("term_2") or 0
        term_3 = booking.get("term_3") or 0
        received_amount = term_1 + term_2 + term_3
        
        bookings.append({
            "id": str(booking["_id"]),
            "company_name": booking.get("company_name", ""),
            "contact_person": booking.get("contact_person", ""),
            "email": booking.get("email", ""),
            "services": booking.get("services", []),
            "total_amount": booking.get("total_amount", 0),
            "received_amount": received_amount,
            "status": booking.get("status", "Pending"),
            "bdm": booking.get("bdm", ""),
            "date": booking.get("date"),
            "deleted_by": booking.get("deletedBy"),
            "deleted_by_name": booking.get("deletedByName", "Unknown"),
            "deleted_at": booking.get("deletedAt")
        })
    
    return {
        "items": bookings,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.post("/{booking_id}/restore")
async def restore_booking(booking_id: str, current_user: dict = Depends(require_admin)):
    """
    Restore a deleted booking (Admin/SRDEV only)
    """
    bookings_collection = get_collection("bookings")
    
    try:
        booking = await bookings_collection.find_one({
            "_id": ObjectId(booking_id),
            "isDeleted": True
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deleted booking not found"
        )
    
    # Restore booking
    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {
            "isDeleted": False,
            "deletedAt": None,
            "deletedBy": None,
            "deletedByName": None,
            "restoredAt": datetime.utcnow(),
            "restoredBy": current_user["id"],
            "restoredByName": current_user["name"],
            "updatedAt": datetime.utcnow()
        }}
    )
    
    return {"message": "Booking restored successfully"}

@router.delete("/{booking_id}/permanent")
async def permanent_delete(booking_id: str, current_user: dict = Depends(require_admin)):
    """
    Permanently delete a booking (Admin/SRDEV only)
    This cannot be undone!
    """
    bookings_collection = get_collection("bookings")
    
    # Only SRDEV can permanently delete
    if current_user["role"] != UserRole.SRDEV:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SRDEV can permanently delete bookings"
        )
    
    try:
        booking = await bookings_collection.find_one({
            "_id": ObjectId(booking_id),
            "isDeleted": True
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking ID format"
        )
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deleted booking not found"
        )
    
    # Permanently delete
    await bookings_collection.delete_one({"_id": ObjectId(booking_id)})
    
    return {"message": "Booking permanently deleted"}

@router.post("/restore-all")
async def restore_all_bookings(current_user: dict = Depends(require_admin)):
    """Restore all deleted bookings (SRDEV only)"""
    if current_user["role"] != UserRole.SRDEV:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SRDEV can restore all bookings"
        )
    
    bookings_collection = get_collection("bookings")
    
    result = await bookings_collection.update_many(
        {"isDeleted": True},
        {"$set": {
            "isDeleted": False,
            "deletedAt": None,
            "deletedBy": None,
            "deletedByName": None,
            "restoredAt": datetime.utcnow(),
            "restoredBy": current_user["id"],
            "restoredByName": current_user["name"],
            "updatedAt": datetime.utcnow()
        }}
    )
    
    return {"message": f"Restored {result.modified_count} bookings"}

@router.delete("/empty")
async def empty_trash(current_user: dict = Depends(require_admin)):
    """Permanently delete all trashed bookings (SRDEV only)"""
    if current_user["role"] != UserRole.SRDEV:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SRDEV can empty trash"
        )
    
    bookings_collection = get_collection("bookings")
    
    result = await bookings_collection.delete_many({"isDeleted": True})
    
    return {"message": f"Permanently deleted {result.deleted_count} bookings"}

@router.get("/count")
async def get_trash_count(current_user: dict = Depends(require_admin)):
    """Get count of items in trash"""
    bookings_collection = get_collection("bookings")
    count = await bookings_collection.count_documents({"isDeleted": True})
    return {"count": count}
