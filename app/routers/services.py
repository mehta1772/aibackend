"""
Services Router
Handles service management
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional, List

from app.models.schemas import ServiceCreate, ServiceUpdate, ServiceResponse, UserRole
from app.utils.database import get_collection
from app.utils.auth import get_current_user, require_srdev

router = APIRouter()

@router.get("/", response_model=List[ServiceResponse])
async def get_all_services(
    search: Optional[str] = Query(None, description="Search by name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all services
    All users can view services
    """
    services_collection = get_collection("services")
    
    query = {}
    
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    if is_active is not None:
        query["is_active"] = is_active
    
    cursor = services_collection.find(query).sort("name", 1)
    
    services = []
    async for service in cursor:
        services.append(ServiceResponse(
            id=str(service["_id"]),
            name=service["name"],
            is_active=service.get("is_active", True),
            created_at=service.get("created_at", datetime.utcnow())
        ))
    
    return services

@router.get("/active")
async def get_active_services(current_user: dict = Depends(get_current_user)):
    """Get only active services for booking form"""
    services_collection = get_collection("services")
    
    cursor = services_collection.find({"is_active": True}).sort("name", 1)
    
    services = []
    async for service in cursor:
        services.append({
            "id": str(service["_id"]),
            "name": service["name"]
        })
    
    return services

@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(service_id: str, current_user: dict = Depends(get_current_user)):
    """Get single service"""
    services_collection = get_collection("services")
    
    try:
        service = await services_collection.find_one({"_id": ObjectId(service_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid service ID format"
        )
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    return ServiceResponse(
        id=str(service["_id"]),
        name=service["name"],
        is_active=service.get("is_active", True),
        created_at=service.get("created_at", datetime.utcnow())
    )

@router.post("/", response_model=ServiceResponse)
async def create_service(
    service_data: ServiceCreate,
    current_user: dict = Depends(require_srdev)
):
    """Create new service (SRDEV only)"""
    services_collection = get_collection("services")
    
    # Check if service already exists
    existing = await services_collection.find_one({"name": {"$regex": f"^{service_data.name}$", "$options": "i"}})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service with this name already exists"
        )
    
    new_service = {
        "name": service_data.name,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "created_by": current_user["id"]
    }
    
    result = await services_collection.insert_one(new_service)
    
    return ServiceResponse(
        id=str(result.inserted_id),
        name=new_service["name"],
        is_active=new_service["is_active"],
        created_at=new_service["created_at"]
    )

@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    service_data: ServiceUpdate,
    current_user: dict = Depends(require_srdev)
):
    """Update service (SRDEV only)"""
    services_collection = get_collection("services")
    
    try:
        service = await services_collection.find_one({"_id": ObjectId(service_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid service ID format"
        )
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    update_dict = {"updated_at": datetime.utcnow()}
    
    if service_data.name:
        # Check if new name already exists
        existing = await services_collection.find_one({
            "name": {"$regex": f"^{service_data.name}$", "$options": "i"},
            "_id": {"$ne": ObjectId(service_id)}
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service with this name already exists"
            )
        update_dict["name"] = service_data.name
    
    if service_data.is_active is not None:
        update_dict["is_active"] = service_data.is_active
    
    await services_collection.update_one(
        {"_id": ObjectId(service_id)},
        {"$set": update_dict}
    )
    
    updated = await services_collection.find_one({"_id": ObjectId(service_id)})
    
    return ServiceResponse(
        id=str(updated["_id"]),
        name=updated["name"],
        is_active=updated.get("is_active", True),
        created_at=updated.get("created_at", datetime.utcnow())
    )

@router.delete("/{service_id}")
async def delete_service(service_id: str, current_user: dict = Depends(require_srdev)):
    """Delete service (SRDEV only)"""
    services_collection = get_collection("services")
    bookings_collection = get_collection("bookings")
    
    try:
        service = await services_collection.find_one({"_id": ObjectId(service_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid service ID format"
        )
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Check if service is used in any bookings
    booking_count = await bookings_collection.count_documents({"services": service["name"]})
    if booking_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete service. It is used in {booking_count} bookings. Disable it instead."
        )
    
    await services_collection.delete_one({"_id": ObjectId(service_id)})
    
    return {"message": "Service deleted successfully"}

@router.post("/{service_id}/toggle")
async def toggle_service(service_id: str, current_user: dict = Depends(require_srdev)):
    """Toggle service active status (SRDEV only)"""
    services_collection = get_collection("services")
    
    try:
        service = await services_collection.find_one({"_id": ObjectId(service_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid service ID format"
        )
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    new_status = not service.get("is_active", True)
    
    await services_collection.update_one(
        {"_id": ObjectId(service_id)},
        {"$set": {
            "is_active": new_status,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": f"Service {'enabled' if new_status else 'disabled'} successfully", "is_active": new_status}
