"""
Authentication Router
Handles login, registration, and token management
"""

from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime
from bson import ObjectId

from app.models.schemas import (
    LoginRequest, Token, UserCreate, UserResponse, UserRole
)
from app.utils.database import get_collection
from app.utils.auth import (
    verify_password, get_password_hash, create_access_token, get_current_user
)

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """
    Authenticate user and return JWT token
    Optimized for instant login
    """
    users_collection = get_collection("users")
    
    # Find user by email (indexed for fast lookup)
    user = await users_collection.find_one({"email": login_data.email.lower()})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(login_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact administrator."
        )
    
    # Create access token
    token_data = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user["role"]
    }
    access_token = create_access_token(token_data)
    
    # Update last login
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    return Token(
        access_token=access_token,
        user=UserResponse(
            id=str(user["_id"]),
            name=user["name"],
            email=user["email"],
            role=user["role"],
            is_active=user.get("is_active", True),
            profile_completed=user.get("profile_completed", False)
        )
    )

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, current_user: dict = Depends(get_current_user)):
    """
    Register new user (SRDEV only)
    """
    # Only SRDEV can create users
    if current_user["role"] != UserRole.SRDEV:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SRDEV can create new users"
        )
    
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

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user info"""
    return UserResponse(
        id=current_user["id"],
        name=current_user["name"],
        email=current_user["email"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        profile_completed=current_user["profile_completed"]
    )

@router.post("/verify-token")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Verify if token is valid"""
    return {"valid": True, "user": current_user}

@router.post("/refresh-token", response_model=Token)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh access token"""
    users_collection = get_collection("users")
    user = await users_collection.find_one({"_id": ObjectId(current_user["id"])})
    
    token_data = {
        "sub": current_user["id"],
        "email": current_user["email"],
        "role": current_user["role"]
    }
    access_token = create_access_token(token_data)
    
    return Token(
        access_token=access_token,
        user=UserResponse(
            id=current_user["id"],
            name=current_user["name"],
            email=current_user["email"],
            role=current_user["role"],
            is_active=current_user["is_active"],
            profile_completed=current_user["profile_completed"]
        )
    )
