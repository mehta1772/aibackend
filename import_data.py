"""
Data Import Script
Import your existing 813 bookings into MongoDB
"""

import json
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "crm_db")

async def import_bookings(json_file_path: str):
    """Import bookings from JSON file"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    bookings_collection = db["bookings"]
    
    # Read JSON file
    with open(json_file_path, 'r', encoding='utf-8') as f:
        bookings = json.load(f)
    
    print(f"📁 Found {len(bookings)} bookings to import")
    
    # Process and insert bookings
    imported = 0
    errors = []
    
    for booking in bookings:
        try:
            # Remove MongoDB's _id if present (let MongoDB generate new one)
            if "_id" in booking:
                del booking["_id"]
            
            # Convert date fields
            if "$date" in str(booking.get("date", {})):
                booking["date"] = datetime.fromisoformat(booking["date"]["$date"].replace("Z", "+00:00"))
            elif isinstance(booking.get("date"), str):
                booking["date"] = datetime.fromisoformat(booking["date"].replace("Z", "+00:00"))
            
            if "$date" in str(booking.get("payment_date", {})):
                booking["payment_date"] = datetime.fromisoformat(booking["payment_date"]["$date"].replace("Z", "+00:00"))
            elif isinstance(booking.get("payment_date"), str) and booking["payment_date"]:
                booking["payment_date"] = datetime.fromisoformat(booking["payment_date"].replace("Z", "+00:00"))
            
            if "$date" in str(booking.get("createdAt", {})):
                booking["createdAt"] = datetime.fromisoformat(booking["createdAt"]["$date"].replace("Z", "+00:00"))
            elif isinstance(booking.get("createdAt"), str):
                booking["createdAt"] = datetime.fromisoformat(booking["createdAt"].replace("Z", "+00:00"))
            else:
                booking["createdAt"] = datetime.utcnow()
            
            if "$date" in str(booking.get("updatedAt", {})):
                booking["updatedAt"] = datetime.fromisoformat(booking["updatedAt"]["$date"].replace("Z", "+00:00"))
            elif isinstance(booking.get("updatedAt"), str):
                booking["updatedAt"] = datetime.fromisoformat(booking["updatedAt"].replace("Z", "+00:00"))
            else:
                booking["updatedAt"] = datetime.utcnow()
            
            # Ensure required fields
            if "isDeleted" not in booking:
                booking["isDeleted"] = False
            if "status" not in booking:
                booking["status"] = "Pending"
            if "updatedhistory" not in booking:
                booking["updatedhistory"] = []
            
            # Insert booking
            await bookings_collection.insert_one(booking)
            imported += 1
            
            if imported % 100 == 0:
                print(f"  ✅ Imported {imported} bookings...")
                
        except Exception as e:
            errors.append(f"Error at booking {imported + 1}: {str(e)}")
    
    # Print results
    print(f"\n📊 Import Complete!")
    print(f"  ✅ Successfully imported: {imported}")
    print(f"  ❌ Errors: {len(errors)}")
    
    if errors:
        print("\n⚠️ Errors:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
    
    client.close()

async def create_admin_user():
    """Create initial admin user"""
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    users_collection = db["users"]
    
    # Check if admin exists
    existing = await users_collection.find_one({"email": "admin@example.com"})
    if existing:
        print("⚠️ Admin user already exists")
        client.close()
        return
    
    # Create admin user
    admin = {
        "name": "Admin",
        "email": "admin@example.com",
        "password": pwd_context.hash("admin123"),
        "role": "SRDEV",
        "is_active": True,
        "profile_completed": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await users_collection.insert_one(admin)
    print("✅ Admin user created!")
    print("  Email: admin@example.com")
    print("  Password: admin123")
    
    client.close()

async def create_sample_services():
    """Create sample services"""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    services_collection = db["services"]
    
    sample_services = [
        "PMEGP",
        "MSME Certificate",
        "GST Registration",
        "Company Registration",
        "Trademark Registration",
        "ISO Certification",
        "FSSAI License",
        "Import Export Code",
        "Digital Marketing",
        "Website Development",
    ]
    
    for service_name in sample_services:
        existing = await services_collection.find_one({"name": service_name})
        if not existing:
            await services_collection.insert_one({
                "name": service_name,
                "is_active": True,
                "created_at": datetime.utcnow()
            })
            print(f"  ✅ Created service: {service_name}")
    
    print("✅ Sample services created!")
    client.close()

if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("CRM Data Import Script")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # Import bookings from file
        json_file = sys.argv[1]
        print(f"\n📂 Importing from: {json_file}")
        asyncio.run(import_bookings(json_file))
    else:
        print("\nUsage:")
        print("  python import_data.py bookings.json  - Import bookings")
        print("\nRunning setup tasks...")
        
        # Create admin and services
        print("\n1️⃣ Creating admin user...")
        asyncio.run(create_admin_user())
        
        print("\n2️⃣ Creating sample services...")
        asyncio.run(create_sample_services())
        
        print("\n✅ Setup complete!")
        print("\nTo import your 813 bookings, run:")
        print("  python import_data.py your_bookings.json")
