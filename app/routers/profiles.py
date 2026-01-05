"""
Profiles Router
Handles employee profile management
First login profile completion
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime
from bson import ObjectId
from typing import Optional, List

from app.models.schemas import ProfileCreate, ProfileResponse, UserRole
from app.utils.database import get_collection
from app.utils.auth import get_current_user, require_srdev

router = APIRouter()

@router.post("/complete")
async def complete_profile(
    profile_data: ProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Complete profile on first login
    Required for new users
    """
    profiles_collection = get_collection("profiles")
    users_collection = get_collection("users")
    
    # Check if profile already exists
    existing = await profiles_collection.find_one({"user_id": current_user["id"]})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists"
        )
    
    # Create profile
    profile = {
        "user_id": current_user["id"],
        "name": profile_data.name,
        "email": profile_data.email,
        "phone_number": profile_data.phone_number,
        "aadhaar_number": profile_data.aadhaar_number,
        "pan_number": profile_data.pan_number,
        "role": current_user["role"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await profiles_collection.insert_one(profile)
    
    # Mark user profile as completed
    await users_collection.update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$set": {
            "profile_completed": True,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {
        "message": "Profile completed successfully",
        "profile_completed": True
    }

@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile"""
    profiles_collection = get_collection("profiles")
    
    profile = await profiles_collection.find_one({"user_id": current_user["id"]})
    
    if not profile:
        return {
            "profile_completed": False,
            "message": "Profile not completed"
        }
    
    # Handle aadhaar masking safely
    aadhaar = profile.get("aadhaar_number", "")
    if aadhaar and len(aadhaar) >= 8:
        masked_aadhaar = aadhaar[:4] + "****" + aadhaar[-4:]
    else:
        masked_aadhaar = aadhaar
    
    return {
        "id": str(profile["_id"]),
        "user_id": profile.get("user_id", ""),
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone_number": profile.get("phone_number", ""),
        "aadhaar_number": masked_aadhaar,
        "pan_number": profile.get("pan_number", ""),
        "role": profile.get("role", ""),
        "created_at": profile.get("created_at"),
        "profile_completed": True
    }

@router.put("/me")
async def update_my_profile(
    profile_data: ProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's profile"""
    profiles_collection = get_collection("profiles")
    
    profile = await profiles_collection.find_one({"user_id": current_user["id"]})
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Complete profile first."
        )
    
    await profiles_collection.update_one(
        {"user_id": current_user["id"]},
        {"$set": {
            "name": profile_data.name,
            "email": profile_data.email,
            "phone_number": profile_data.phone_number,
            "aadhaar_number": profile_data.aadhaar_number,
            "pan_number": profile_data.pan_number,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Profile updated successfully"}

@router.get("/all")
async def get_all_profiles(
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_srdev)
):
    """
    Get all employee profiles (SRDEV only)
    """
    profiles_collection = get_collection("profiles")
    
    query = {}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    if role:
        query["role"] = role
    
    total = await profiles_collection.count_documents(query)
    
    skip = (page - 1) * page_size
    cursor = profiles_collection.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    
    profiles = []
    async for profile in cursor:
        # Handle aadhaar masking safely
        aadhaar = profile.get("aadhaar_number", "")
        if aadhaar and len(aadhaar) >= 8:
            masked_aadhaar = aadhaar[:4] + "****" + aadhaar[-4:]
        else:
            masked_aadhaar = aadhaar
            
        profiles.append({
            "id": str(profile["_id"]),
            "user_id": profile.get("user_id", ""),
            "name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "phone_number": profile.get("phone_number", ""),
            "aadhaar_number": masked_aadhaar,
            "pan_number": profile.get("pan_number", ""),
            "role": profile.get("role", ""),
            "created_at": profile.get("created_at")
        })
    
    return {
        "items": profiles,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.get("/{user_id}")
async def get_profile_by_user(user_id: str, current_user: dict = Depends(require_srdev)):
    """Get specific user's profile (SRDEV only)"""
    profiles_collection = get_collection("profiles")
    
    profile = await profiles_collection.find_one({"user_id": user_id})
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    return {
        "id": str(profile["_id"]),
        "user_id": profile["user_id"],
        "name": profile["name"],
        "email": profile["email"],
        "phone_number": profile["phone_number"],
        "aadhaar_number": profile["aadhaar_number"],
        "pan_number": profile["pan_number"],
        "role": profile["role"],
        "created_at": profile["created_at"]
    }

@router.delete("/{user_id}")
async def delete_profile(user_id: str, current_user: dict = Depends(require_srdev)):
    """Delete user profile (SRDEV only)"""
    profiles_collection = get_collection("profiles")
    users_collection = get_collection("users")
    
    profile = await profiles_collection.find_one({"user_id": user_id})
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    await profiles_collection.delete_one({"user_id": user_id})
    
    # Update user profile_completed status
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "profile_completed": False,
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Profile deleted successfully"}

@router.get("/check/{user_id}")
async def check_profile_status(user_id: str, current_user: dict = Depends(get_current_user)):
    """Check if user has completed profile"""
    profiles_collection = get_collection("profiles")
    
    profile = await profiles_collection.find_one({"user_id": user_id})
    
    return {
        "user_id": user_id,
        "profile_completed": profile is not None
    }
