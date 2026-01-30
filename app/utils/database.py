"""
MongoDB Database Connection and Utilities
Optimized for fast connections and scalability
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import os
from typing import Optional
from bson.codec_options import DatetimeConversion


# Global database client
class Database:
    client: Optional[AsyncIOMotorClient] = None
    db = None

db = Database()

async def connect_to_mongo():
    """Connect to MongoDB with connection pooling for performance"""
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "crm_db")
    
    # Connection with optimized settings for speed
    db.client = AsyncIOMotorClient(
        MONGO_URI,
        maxPoolSize=50,
        minPoolSize=10,
        maxIdleTimeMS=50000,
        waitQueueTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        retryWrites=True,
        datetime_conversion=DatetimeConversion.DATETIME_AUTO,  # 🔥 THIS FIX
    )
    db.db = db.client[DB_NAME]
    
    # Create indexes for fast queries
    await create_indexes()
    
    print(f"✅ Connected to MongoDB: {DB_NAME}")

async def close_mongo_connection():
    """Close MongoDB connection"""
    if db.client:
        db.client.close()
        print("❌ MongoDB connection closed")

async def create_indexes():
    """Create database indexes for optimized queries"""
    # Bookings indexes
    await db.db.bookings.create_index([("user_id", ASCENDING)])
    await db.db.bookings.create_index([("date", DESCENDING)])
    await db.db.bookings.create_index([("payment_date", DESCENDING)])
    await db.db.bookings.create_index([("company_name", ASCENDING)])
    await db.db.bookings.create_index([("services", ASCENDING)])
    await db.db.bookings.create_index([("bdm", ASCENDING)])
    await db.db.bookings.create_index([("isDeleted", ASCENDING)])
    await db.db.bookings.create_index([("status", ASCENDING)])
    
    # Users indexes
    await db.db.users.create_index([("email", ASCENDING)], unique=True)
    await db.db.users.create_index([("role", ASCENDING)])
    
    # Services indexes
    await db.db.services.create_index([("name", ASCENDING)], unique=True)
    await db.db.services.create_index([("is_active", ASCENDING)])
    
    # Documents indexes
    await db.db.documents.create_index([("booking_id", ASCENDING)])
    await db.db.documents.create_index([("stage", ASCENDING)])
    
    # Profiles indexes
    await db.db.profiles.create_index([("user_id", ASCENDING)], unique=True)
    await db.db.profiles.create_index([("email", ASCENDING)])
    
    print("✅ Database indexes created")

def get_database():
    """Get database instance"""
    return db.db

def get_collection(collection_name: str):
    """Get specific collection"""
    return db.db[collection_name]
