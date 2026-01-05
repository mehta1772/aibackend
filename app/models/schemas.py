"""
Pydantic Models for Data Validation
Defines all data structures used in the CRM
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
from bson import ObjectId

# Custom ObjectId type for Pydantic
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, handler):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {"type": "string"}

# Enums
class UserRole(str, Enum):
    SRDEV = "SRDEV"
    SENIOR_ADMIN = "Senior Admin"
    BDM = "BDM"

class BranchName(str, Enum):
    BRANCH_108 = "108"
    BRANCH_302 = "302"

class BookingStatus(str, Enum):
    PENDING = "Pending"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class DocumentStage(str, Enum):
    AGREEMENT = "Agreement"
    PITCH_DECK = "Pitch Deck"
    DPR = "DPR"
    APPLICATION = "Application"
    OTHERS = "Others"

# User Models
class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    role: UserRole

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None

class UserInDB(UserBase):
    id: str
    is_active: bool = True
    profile_completed: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserResponse(UserBase):
    id: str
    is_active: bool
    profile_completed: bool

# Authentication Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

# Profile Models
class ProfileCreate(BaseModel):
    name: str
    email: EmailStr
    phone_number: str = Field(..., pattern=r'^\d{10}$')
    aadhaar_number: str = Field(..., pattern=r'^\d{12}$')
    pan_number: str = Field(..., pattern=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')

class ProfileResponse(ProfileCreate):
    id: str
    user_id: str
    role: UserRole
    created_at: datetime

# Service Models
class ServiceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class ServiceResponse(ServiceBase):
    id: str
    is_active: bool
    created_at: datetime

# Booking Models
class BookingBase(BaseModel):
    branch_name: BranchName
    company_name: str = Field(..., min_length=2, max_length=300)
    contact_person: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    contact_no: str
    services: List[str]
    total_amount: float = Field(..., ge=0)
    term_1: Optional[float] = None
    term_2: Optional[float] = None
    term_3: Optional[float] = None
    payment_date: Optional[datetime] = None
    closed_by: str
    pan: Optional[str] = None
    gst: Optional[str] = None
    remark: Optional[str] = None
    after_disbursement: Optional[str] = None
    bank: Optional[str] = None
    state: Optional[str] = None

class BookingCreate(BookingBase):
    pass

class BookingUpdate(BaseModel):
    branch_name: Optional[BranchName] = None
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    contact_no: Optional[str] = None
    services: Optional[List[str]] = None
    total_amount: Optional[float] = None
    term_1: Optional[float] = None
    term_2: Optional[float] = None
    term_3: Optional[float] = None
    payment_date: Optional[datetime] = None
    closed_by: Optional[str] = None
    pan: Optional[str] = None
    gst: Optional[str] = None
    remark: Optional[str] = None
    after_disbursement: Optional[str] = None
    bank: Optional[str] = None
    state: Optional[str] = None
    status: Optional[BookingStatus] = None

class EditHistory(BaseModel):
    edited_by: str
    edited_by_name: str
    edited_at: datetime
    changes: dict

class BookingResponse(BookingBase):
    id: str
    user_id: str
    bdm: str
    date: datetime
    status: BookingStatus
    received_amount: float
    pending_amount: float
    isDeleted: bool
    updatedhistory: List[EditHistory] = []
    created_at: datetime
    updated_at: datetime

# Trash Models
class TrashBookingResponse(BookingResponse):
    deleted_by: Optional[str] = None
    deleted_by_name: Optional[str] = None
    deleted_at: Optional[datetime] = None

# Document Models
class DocumentUpload(BaseModel):
    booking_id: str
    stage: DocumentStage
    file_name: str

class DocumentResponse(BaseModel):
    id: str
    booking_id: str
    stage: DocumentStage
    file_name: str
    file_url: str
    uploaded_by: str
    uploaded_by_name: str
    uploaded_at: datetime

class DocumentStageAnalytics(BaseModel):
    stage: DocumentStage
    total_documents: int
    completed_bookings: int

# Invoice Models
class InvoiceCreate(BaseModel):
    company_name: str
    client_name: str
    email: EmailStr
    street_address: str
    city: str
    gst_pan: str
    service_fee: float = Field(..., ge=0)
    gst_amount: float = Field(..., ge=0)

class InvoiceResponse(InvoiceCreate):
    id: str
    date: datetime
    total_amount: float
    created_by: str
    pdf_url: str

# Dashboard Models
class DashboardStats(BaseModel):
    total_bookings: int
    total_users: int
    total_revenue: float
    monthly_revenue: float
    pending_amount: float
    completed_bookings: int
    pending_bookings: int

class RevenueData(BaseModel):
    month: str
    revenue: float
    bookings: int

class ServiceDistribution(BaseModel):
    service: str
    count: int
    percentage: float

class DashboardResponse(BaseModel):
    stats: DashboardStats
    revenue_trends: List[RevenueData]
    booking_trends: List[RevenueData]
    service_distribution: List[ServiceDistribution]

# ML Models
class RevenuePrediction(BaseModel):
    predicted_revenue: float
    confidence: float
    trend: str  # "up", "down", "stable"

class ServiceRecommendation(BaseModel):
    service: str
    score: float
    reason: str

class MLInsights(BaseModel):
    revenue_prediction: RevenuePrediction
    top_services: List[ServiceRecommendation]
    ad_recommendations: List[str]

# Filter Models
class BookingFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    payment_start_date: Optional[datetime] = None
    payment_end_date: Optional[datetime] = None
    services: Optional[List[str]] = None
    bdm_name: Optional[str] = None
    company_name: Optional[str] = None
    status: Optional[BookingStatus] = None
    branch: Optional[BranchName] = None

# Pagination
class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    page_size: int
    total_pages: int
