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
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(require_admin)
):
    """Get all bookings with document status - FAST VERSION"""
    bookings_collection = get_collection("bookings")
    documents_collection = get_collection("documents")
    
    # Build query
    query = {"isDeleted": False}
    
    if search:
        query["$or"] = [
            {"company_name": {"$regex": search, "$options": "i"}},
            {"contact_no": {"$regex": search, "$options": "i"}}
        ]
    
    if service:
        query["services"] = service
    
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    total = await bookings_collection.count_documents(query)
    
    skip = (page - 1) * page_size
    cursor = bookings_collection.find(query).skip(skip).limit(page_size).sort("date", -1)
    
    # Get all bookings first
    booking_list = []
    booking_ids = []
    async for booking in cursor:
        booking_id = str(booking["_id"])
        booking_ids.append(booking_id)
        
        term_1 = booking.get("term_1") or 0
        term_2 = booking.get("term_2") or 0
        term_3 = booking.get("term_3") or 0
        received_amount = term_1 + term_2 + term_3
        
        booking_list.append({
            "id": booking_id,
            "company_name": booking.get("company_name", ""),
            "contact_person": booking.get("contact_person", ""),
            "contact_no": str(booking.get("contact_no", "")),
            "email": booking.get("email", ""),
            "services": booking.get("services", []),
            "total_amount": booking.get("total_amount", 0),
            "received_amount": received_amount,
            "status": booking.get("status", "Pending"),
            "bdm": booking.get("bdm", ""),
            "date": booking.get("date"),
            "document_stages": {s: 0 for s in STAGES},
            "total_documents": 0
        })
    
    # Get document counts in ONE aggregation query (much faster)
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
        
        # Update booking list with document counts
        for booking in booking_list:
            if booking["id"] in count_map:
                for stage, count in count_map[booking["id"]].items():
                    if stage in booking["document_stages"]:
                        booking["document_stages"][stage] = count
                booking["total_documents"] = sum(booking["document_stages"].values())
    
    return {
        "items": booking_list,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
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
