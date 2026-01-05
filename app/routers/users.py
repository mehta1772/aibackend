"""
Users Router
Handles user management (SRDEV only)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional, List

from app.models.schemas import (
    UserCreate, UserUpdate, UserResponse, UserRole
)
from app.utils.database import get_collection
from app.utils.auth import get_password_hash, get_current_user, require_srdev

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_srdev)
):
    """
    Get all users (SRDEV only)
    Supports search and filtering
    """
    users_collection = get_collection("users")
    
    # Build query
    query = {}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    if role:
        query["role"] = role
    
    if is_active is not None:
        query["is_active"] = is_active
    
    # Get total count
    total = await users_collection.count_documents(query)
    
    # Get paginated users
    skip = (page - 1) * page_size
    cursor = users_collection.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    
    users = []
    async for user in cursor:
        users.append(UserResponse(
            id=str(user["_id"]),
            name=user["name"],
            email=user["email"],
            role=user["role"],
            is_active=user.get("is_active", True),
            profile_completed=user.get("profile_completed", False)
        ))
    
    return users

@router.get("/count")
async def get_user_count(current_user: dict = Depends(require_srdev)):
    """Get total user count"""
    users_collection = get_collection("users")
    total = await users_collection.count_documents({"is_active": True})
    return {"total": total}

@router.get("/by-role")
async def get_users_by_role(current_user: dict = Depends(require_srdev)):
    """Get user count by role"""
    users_collection = get_collection("users")
    
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$role", "count": {"$sum": 1}}}
    ]
    
    result = {}
    async for doc in users_collection.aggregate(pipeline):
        result[doc["_id"]] = doc["count"]
    
    return result

@router.get("/bdm-list")
async def get_bdm_list(current_user: dict = Depends(get_current_user)):
    """Get list of all BDM users for filters"""
    users_collection = get_collection("users")
    
    cursor = users_collection.find(
        {"role": {"$in": [UserRole.BDM, UserRole.SENIOR_ADMIN, UserRole.SRDEV]}, "is_active": True},
        {"_id": 1, "name": 1}
    )
    
    bdm_list = []
    async for user in cursor:
        bdm_list.append({
            "id": str(user["_id"]),
            "name": user["name"]
        })
    
    return bdm_list

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user: dict = Depends(require_srdev)):
    """Get specific user by ID"""
    users_collection = get_collection("users")
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        role=user["role"],
        is_active=user.get("is_active", True),
        profile_completed=user.get("profile_completed", False)
    )

@router.post("/", response_model=UserResponse)
async def create_user(user_data: UserCreate, current_user: dict = Depends(require_srdev)):
    """
    Create new user (SRDEV only)
    """
    users_collection = get_collection("users")
    
    # Check if email already exists
    existing_user = await users_collection.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    new_user = {
        "name": user_data.name,
        "email": user_data.email.lower(),
        "password": get_password_hash(user_data.password),
        "role": user_data.role,
        "is_active": True,
        "profile_completed": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "created_by": current_user["id"]
    }
    
    result = await users_collection.insert_one(new_user)
    
    return UserResponse(
        id=str(result.inserted_id),
        name=new_user["name"],
        email=new_user["email"],
        role=new_user["role"],
        is_active=new_user["is_active"],
        profile_completed=new_user["profile_completed"]
    )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: dict = Depends(require_srdev)
):
    """
    Update user (SRDEV only)
    """
    users_collection = get_collection("users")
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Build update dict
    update_dict = {"updated_at": datetime.utcnow()}
    
    if user_data.name:
        update_dict["name"] = user_data.name
    
    if user_data.email:
        # Check if new email is already taken
        existing = await users_collection.find_one({
            "email": user_data.email.lower(),
            "_id": {"$ne": ObjectId(user_id)}
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        update_dict["email"] = user_data.email.lower()
    
    if user_data.password:
        update_dict["password"] = get_password_hash(user_data.password)
    
    if user_data.role:
        update_dict["role"] = user_data.role
    
    # Update user
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    # Get updated user
    updated_user = await users_collection.find_one({"_id": ObjectId(user_id)})
    
    return UserResponse(
        id=str(updated_user["_id"]),
        name=updated_user["name"],
        email=updated_user["email"],
        role=updated_user["role"],
        is_active=updated_user.get("is_active", True),
        profile_completed=updated_user.get("profile_completed", False)
    )

@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(require_srdev)):
    """
    Delete user (SRDEV only)
    Soft delete - sets is_active to False
    """
    users_collection = get_collection("users")
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_active": False,
            "deleted_at": datetime.utcnow(),
            "deleted_by": current_user["id"]
        }}
    )
    
    return {"message": "User deleted successfully"}

@router.post("/{user_id}/toggle-status")
async def toggle_user_status(user_id: str, current_user: dict = Depends(require_srdev)):
    """Toggle user active status"""
    users_collection = get_collection("users")
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    new_status = not user.get("is_active", True)
    
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_active": new_status,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": f"User {'activated' if new_status else 'deactivated'} successfully", "is_active": new_status}
