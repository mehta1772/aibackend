"""
CRM Application - FastAPI Backend
Enterprise-grade Customer Relationship Management System
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from app.routers import auth, users, bookings, services, dashboard, trash, documents, invoices, profiles

# Import database
from app.utils.database import connect_to_mongo, close_mongo_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - connect/disconnect from MongoDB"""
    await connect_to_mongo()
    yield
    await close_mongo_connection()

# Initialize FastAPI app
app = FastAPI(
    title="CRM Application API",
    description="Enterprise CRM System with ML-powered insights",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://crm.enigoal.in",  # Update with your Hostinger domain
    "https://www.enigoal.in",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["Bookings"])
app.include_router(services.router, prefix="/api/services", tags=["Services"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(trash.router, prefix="/api/trash", tags=["Trash"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["Profiles"])

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "message": "CRM API is running"}

@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "database": "connected",
            "storage": "ready"
        }
    }
