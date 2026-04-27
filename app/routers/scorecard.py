# """
# Scorecard Router
# Handles BDM scorecard, revenue sharing, and service deductions
# Role-based access:
# - BDM: Can only see their own scorecard
# - SRDEV: Can see all BDM/Admin scorecards with full transaction details
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from datetime import datetime, timedelta
# from bson import ObjectId
# from typing import Optional, List

# from app.models.schemas import UserRole
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user, require_admin

# router = APIRouter()



# async def build_scorecard_for_user(user_id: str, user_name: str, user_role: str, date_filter: dict, filter_by: str = "transaction_date"):
#     """
#     Helper to build scorecard data with summary and bank-style entries (with running balance)
    
#     Args:
#         filter_by: "transaction_date" (scorecard entry date) or "booking_date" (actual booking date)
#     """
#     scorecard_collection = get_collection("scorecard_entries")
#     bookings_collection = get_collection("bookings")
    
#     query = {"user_id": user_id}
    
#     # If filtering by booking_date, we need to find bookings in date range first
#     booking_id_filter = None
#     if filter_by == "booking_date" and date_filter:
#         booking_query = {"isDeleted": False}
#         if "$gte" in date_filter or "$lte" in date_filter:
#             booking_query["date"] = date_filter
        
#         booking_ids = []
#         async for booking in bookings_collection.find(booking_query, {"_id": 1}):
#             booking_ids.append(str(booking["_id"]))
        
#         if booking_ids:
#             query["booking_id"] = {"$in": booking_ids}
#         else:
#             # No bookings in range - return empty
#             return {
#                 "user": {"id": user_id, "name": user_name, "role": user_role},
#                 "summary": {
#                     "total_earned": 0, "total_shared_received": 0,
#                     "total_shared_given": 0, "total_deductions": 0,
#                     "net_total": 0, "total_transactions": 0,
#                     "total_credits": 0, "total_debits": 0
#                 },
#                 "entries": []
#             }
#     elif date_filter:
#         # Filter by transaction (scorecard entry) date
#         query["created_at"] = date_filter
    
#     # Fetch entries in ASCENDING order for running balance calculation
#     # Also enrich with booking date
#     raw_entries = []
#     async for entry in scorecard_collection.find(query).sort("created_at", 1):
#         raw_entries.append(entry)
    
#     # Get booking dates for each entry
#     booking_ids_needed = list(set(e.get("booking_id") for e in raw_entries if e.get("booking_id")))
#     booking_dates = {}
#     if booking_ids_needed:
#         try:
#             object_ids = [ObjectId(bid) for bid in booking_ids_needed]
#             async for b in bookings_collection.find(
#                 {"_id": {"$in": object_ids}},
#                 {"_id": 1, "date": 1, "company_name": 1}
#             ):
#                 booking_dates[str(b["_id"])] = b.get("date")
#         except:
#             pass
    
#     # CRITICAL: Sort entries so that within the same booking, CREDITS come before DEBITS
#     # This ensures correct running balance:
#     # If BDM1 earns 20000 and shares 10000 with BDM2, BDM1's transactions should show:
#     #   +20000 (earned) then -10000 (shared_given) = balance 10000
#     # NOT: -10000 first (which would make balance negative temporarily)
#     # 
#     # Type priority (credits first, then debits):
#     #   earned = 1 (credit)
#     #   shared_received = 2 (credit)
#     #   shared_given = 3 (debit)
#     #   deduction = 4 (debit)
#     TYPE_PRIORITY = {
#         "earned": 1,
#         "shared_received": 2,
#         "shared_given": 3,
#         "deduction": 4
#     }
    
#     def sort_key(entry):
#         # Primary: booking_date (oldest first)
#         booking_id = entry.get("booking_id")
#         b_date = booking_dates.get(booking_id) if booking_id else None
#         created_at = entry.get("created_at")
#         # Use booking date for grouping, fallback to created_at
#         group_date = b_date or created_at
#         # Secondary: booking_id (keep entries of same booking together)
#         # Tertiary: type priority (credits before debits)
#         return (
#             group_date,
#             booking_id or "",
#             TYPE_PRIORITY.get(entry.get("type"), 99)
#         )
    
#     raw_entries.sort(key=sort_key)
    
#     # Build entries with running balance
#     entries = []
#     total_earned = 0
#     total_shared_received = 0
#     total_shared_given = 0
#     total_deductions = 0
#     total_credits = 0
#     total_debits = 0
#     running_balance = 0
    
#     for entry in raw_entries:
#         entry_type = entry.get("type")
#         amount = entry.get("amount", 0)
        
#         # Determine credit/debit
#         # Credits: earned, shared_received
#         # Debits: shared_given, deduction
#         is_credit = entry_type in ["earned", "shared_received"]
#         credit_amount = amount if is_credit else 0
#         debit_amount = amount if not is_credit else 0
        
#         # Update running balance
#         if is_credit:
#             running_balance += amount
#             total_credits += amount
#         else:
#             running_balance -= amount
#             total_debits += amount
        
#         # Build rich description based on type
#         description = entry.get("description", "")
#         company_name = entry.get("company_name", "")
        
#         if entry_type == "earned":
#             full_description = f"Revenue from booking: {company_name}"
#             if entry.get("share_percentage"):
#                 full_description += f" ({entry.get('share_percentage')}% your share)"
#         elif entry_type == "shared_received":
#             shared_by = entry.get("shared_by_name", "Unknown")
#             pct = entry.get("share_percentage", 0)
#             full_description = f"Received share from {shared_by} ({pct}%) - Booking: {company_name}"
#         elif entry_type == "shared_given":
#             shared_to = entry.get("shared_to_name", "Unknown")
#             pct = entry.get("share_percentage", 0)
#             full_description = f"Shared to {shared_to} ({pct}%) - Booking: {company_name}"
#         elif entry_type == "deduction":
#             service = entry.get("service_name", "Service")
#             full_description = f"Service deduction: {service} - Booking: {company_name}"
#         else:
#             full_description = description
        
#         booking_id = entry.get("booking_id")
#         booking_date = booking_dates.get(booking_id) if booking_id else None
        
#         entry_data = {
#             "id": str(entry["_id"]),
#             "booking_id": booking_id,
#             "booking_date": booking_date,
#             "company_name": company_name,
#             "type": entry_type,
#             "amount": amount,
#             "credit": credit_amount,
#             "debit": debit_amount,
#             "balance": running_balance,
#             "is_credit": is_credit,
#             "description": full_description,
#             "short_description": description,
#             "shared_by": entry.get("shared_by_name"),
#             "shared_to": entry.get("shared_to_name"),
#             "share_percentage": entry.get("share_percentage"),
#             "service_name": entry.get("service_name"),
#             "created_at": entry.get("created_at"),
#             "term": entry.get("term"),
#             "verified": entry.get("verified", False),
#             "verified_by": entry.get("verified_by_name")
#         }
#         entries.append(entry_data)
        
#         if entry_type == "earned":
#             total_earned += amount
#         elif entry_type == "shared_received":
#             total_shared_received += amount
#         elif entry_type == "shared_given":
#             total_shared_given += amount
#         elif entry_type == "deduction":
#             total_deductions += amount
    
#     # Reverse to show most recent first in UI
#     entries.reverse()
    
#     net_total = total_earned + total_shared_received - total_shared_given - total_deductions
    
#     return {
#         "user": {
#             "id": user_id,
#             "name": user_name,
#             "role": user_role
#         },
#         "summary": {
#             "total_earned": total_earned,
#             "total_shared_received": total_shared_received,
#             "total_shared_given": total_shared_given,
#             "total_deductions": total_deductions,
#             "net_total": net_total,
#             "total_transactions": len(entries),
#             "total_credits": total_credits,
#             "total_debits": total_debits
#         },
#         "entries": entries
#     }


# @router.get("/")
# async def get_scorecards(
#     start_date: Optional[datetime] = Query(None),
#     end_date: Optional[datetime] = Query(None),
#     bdm_id: Optional[str] = Query(None),
#     filter_by: str = Query("transaction_date", description="Filter by 'transaction_date' or 'booking_date'"),
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Get scorecard data based on user role:
#     - BDM/Senior Admin: Can only see their own scorecard
#     - SRDEV: Can see all BDM and Admin scorecards
    
#     filter_by:
#     - transaction_date: Filter by when scorecard entry was created
#     - booking_date: Filter by the actual booking date
#     """
#     users_collection = get_collection("users")
    
#     # Build date filter
#     date_filter = {}
#     if start_date:
#         date_filter["$gte"] = start_date
#     if end_date:
#         end_of_day = end_date.replace(hour=23, minute=59, second=59)
#         date_filter["$lte"] = end_of_day
    
#     # Role-based access control
#     if current_user["role"] != UserRole.SRDEV:
#         # BDM/Senior Admin: Only their own scorecard
#         scorecard = await build_scorecard_for_user(
#             user_id=current_user["id"],
#             user_name=current_user["name"],
#             user_role=current_user["role"],
#             date_filter=date_filter,
#             filter_by=filter_by
#         )
#         return {
#             "scorecards": [scorecard],
#             "period": {
#                 "start_date": start_date,
#                 "end_date": end_date,
#                 "filter_by": filter_by
#             },
#             "is_restricted": True
#         }
    
#     # SRDEV: Can see all scorecards
#     bdm_query = {
#         "role": {"$in": [UserRole.BDM, UserRole.SENIOR_ADMIN, UserRole.SRDEV]},
#         "is_active": True
#     }
#     if bdm_id:
#         try:
#             bdm_query["_id"] = ObjectId(bdm_id)
#         except:
#             raise HTTPException(status_code=400, detail="Invalid BDM ID")
    
#     scorecards = []
#     async for user in users_collection.find(bdm_query):
#         scorecard = await build_scorecard_for_user(
#             user_id=str(user["_id"]),
#             user_name=user["name"],
#             user_role=user["role"],
#             date_filter=date_filter,
#             filter_by=filter_by
#         )
#         scorecards.append(scorecard)
    
#     # Sort by net total descending
#     scorecards.sort(key=lambda x: x["summary"]["net_total"], reverse=True)
    
#     return {
#         "scorecards": scorecards,
#         "period": {
#             "start_date": start_date,
#             "end_date": end_date,
#             "filter_by": filter_by
#         },
#         "is_restricted": False
#     }


# @router.get("/my")
# async def get_my_scorecard(
#     start_date: Optional[datetime] = Query(None),
#     end_date: Optional[datetime] = Query(None),
#     filter_by: str = Query("transaction_date"),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get current user's scorecard with full transaction history"""
#     date_filter = {}
#     if start_date:
#         date_filter["$gte"] = start_date
#     if end_date:
#         end_of_day = end_date.replace(hour=23, minute=59, second=59)
#         date_filter["$lte"] = end_of_day
    
#     scorecard = await build_scorecard_for_user(
#         user_id=current_user["id"],
#         user_name=current_user["name"],
#         user_role=current_user["role"],
#         date_filter=date_filter,
#         filter_by=filter_by
#     )
    
#     return scorecard


# @router.get("/user/{user_id}")
# async def get_user_scorecard(
#     user_id: str,
#     start_date: Optional[datetime] = Query(None),
#     end_date: Optional[datetime] = Query(None),
#     filter_by: str = Query("transaction_date"),
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Get a specific user's scorecard with full transaction history
#     - BDM/Senior Admin: Can only view their own scorecard
#     - SRDEV: Can view any user's scorecard
#     """
#     # Access control
#     if current_user["role"] != UserRole.SRDEV and current_user["id"] != user_id:
#         raise HTTPException(
#             status_code=403,
#             detail="You can only view your own scorecard"
#         )
    
#     users_collection = get_collection("users")
    
#     try:
#         user = await users_collection.find_one({"_id": ObjectId(user_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid user ID")
    
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
    
#     date_filter = {}
#     if start_date:
#         date_filter["$gte"] = start_date
#     if end_date:
#         end_of_day = end_date.replace(hour=23, minute=59, second=59)
#         date_filter["$lte"] = end_of_day
    
#     scorecard = await build_scorecard_for_user(
#         user_id=str(user["_id"]),
#         user_name=user["name"],
#         user_role=user["role"],
#         date_filter=date_filter,
#         filter_by=filter_by
#     )
    
#     return scorecard


# @router.get("/leaderboard")
# async def get_leaderboard(
#     month: Optional[int] = Query(None),
#     year: Optional[int] = Query(None),
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Get leaderboard
#     - BDM: Only their own rank shown
#     - SRDEV: Full leaderboard
#     """
#     scorecard_collection = get_collection("scorecard_entries")
    
#     # Default to current month
#     now = datetime.utcnow()
#     target_month = month or now.month
#     target_year = year or now.year
    
#     start_date = datetime(target_year, target_month, 1)
#     if target_month == 12:
#         end_date = datetime(target_year + 1, 1, 1) - timedelta(seconds=1)
#     else:
#         end_date = datetime(target_year, target_month + 1, 1) - timedelta(seconds=1)
    
#     # Aggregate scorecard by user
#     pipeline = [
#         {
#             "$match": {
#                 "created_at": {"$gte": start_date, "$lte": end_date},
#                 "verified": True
#             }
#         },
#         {
#             "$group": {
#                 "_id": "$user_id",
#                 "user_name": {"$first": "$user_name"},
#                 "earned": {
#                     "$sum": {
#                         "$cond": [{"$eq": ["$type", "earned"]}, "$amount", 0]
#                     }
#                 },
#                 "shared_received": {
#                     "$sum": {
#                         "$cond": [{"$eq": ["$type", "shared_received"]}, "$amount", 0]
#                     }
#                 },
#                 "shared_given": {
#                     "$sum": {
#                         "$cond": [{"$eq": ["$type", "shared_given"]}, "$amount", 0]
#                     }
#                 },
#                 "deductions": {
#                     "$sum": {
#                         "$cond": [{"$eq": ["$type", "deduction"]}, "$amount", 0]
#                     }
#                 },
#                 "booking_count": {
#                     "$sum": {
#                         "$cond": [{"$eq": ["$type", "earned"]}, 1, 0]
#                     }
#                 }
#             }
#         },
#         {"$sort": {"earned": -1}}
#     ]
    
#     results = await scorecard_collection.aggregate(pipeline).to_list(100)
    
#     leaderboard = []
#     for i, item in enumerate(results):
#         net_total = item["earned"] + item["shared_received"] - item["shared_given"] - item["deductions"]
#         leaderboard.append({
#             "rank": i + 1,
#             "user_id": item["_id"],
#             "user_name": item["user_name"],
#             "earned": item["earned"],
#             "shared_received": item["shared_received"],
#             "shared_given": item["shared_given"],
#             "deductions": item["deductions"],
#             "net_total": net_total,
#             "booking_count": item["booking_count"]
#         })
    
#     # BDM/Senior Admin can only see their own entry
#     if current_user["role"] != UserRole.SRDEV:
#         leaderboard = [entry for entry in leaderboard if entry["user_id"] == current_user["id"]]
    
#     return {
#         "month": target_month,
#         "year": target_year,
#         "leaderboard": leaderboard,
#         "is_restricted": current_user["role"] != UserRole.SRDEV
#     }


# async def create_scorecard_entry(
#     user_id: str,
#     user_name: str,
#     booking_id: str,
#     company_name: str,
#     entry_type: str,  # earned, shared_received, shared_given, deduction
#     amount: float,
#     description: str,
#     term: str = None,
#     shared_by_id: str = None,
#     shared_by_name: str = None,
#     shared_to_id: str = None,
#     shared_to_name: str = None,
#     share_percentage: float = None,
#     service_name: str = None,
#     verified: bool = False,
#     verified_by: str = None,
#     verified_by_name: str = None
# ):
#     """Helper function to create scorecard entry"""
#     scorecard_collection = get_collection("scorecard_entries")
    
#     entry = {
#         "user_id": user_id,
#         "user_name": user_name,
#         "booking_id": booking_id,
#         "company_name": company_name,
#         "type": entry_type,
#         "amount": amount,
#         "description": description,
#         "term": term,
#         "shared_by_id": shared_by_id,
#         "shared_by_name": shared_by_name,
#         "shared_to_id": shared_to_id,
#         "shared_to_name": shared_to_name,
#         "share_percentage": share_percentage,
#         "service_name": service_name,
#         "verified": verified,
#         "verified_by": verified_by,
#         "verified_by_name": verified_by_name,
#         "created_at": datetime.utcnow()
#     }
    
#     result = await scorecard_collection.insert_one(entry)
#     return str(result.inserted_id)



















































"""
Scorecard Router
Handles BDM scorecard, revenue sharing, and service deductions
Role-based access:
- BDM: Can only see their own scorecard
- SRDEV: Can see all BDM/Admin scorecards with full transaction details
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional, List

from app.models.schemas import UserRole
from app.utils.database import get_collection
from app.utils.auth import get_current_user, require_admin

router = APIRouter()


async def build_scorecard_for_user(user_id: str, user_name: str, user_role: str, date_filter: dict, filter_by: str = "transaction_date"):
    """
    Helper to build scorecard data with summary and bank-style entries (with running balance)
    
    Args:
        filter_by: "transaction_date" (scorecard entry date) or "booking_date" (actual booking date)
    """
    scorecard_collection = get_collection("scorecard_entries")
    bookings_collection = get_collection("bookings")
    
    query = {"user_id": user_id}
    
    # If filtering by booking_date, we need to find bookings in date range first
    booking_id_filter = None
    if filter_by == "booking_date" and date_filter:
        booking_query = {"isDeleted": False}
        if "$gte" in date_filter or "$lte" in date_filter:
            booking_query["date"] = date_filter
        
        booking_ids = []
        async for booking in bookings_collection.find(booking_query, {"_id": 1}):
            booking_ids.append(str(booking["_id"]))
        
        if booking_ids:
            query["booking_id"] = {"$in": booking_ids}
        else:
            # No bookings in range - return empty
            return {
                "user": {"id": user_id, "name": user_name, "role": user_role},
                "summary": {
                    "total_earned": 0, "total_shared_received": 0,
                    "total_shared_given": 0, "total_deductions": 0,
                    "net_total": 0, "total_transactions": 0,
                    "total_credits": 0, "total_debits": 0
                },
                "entries": []
            }
    elif date_filter:
        # Filter by transaction (scorecard entry) date
        query["created_at"] = date_filter
    
    # Fetch entries in ASCENDING order for running balance calculation
    # Also enrich with booking date
    raw_entries = []
    async for entry in scorecard_collection.find(query).sort("created_at", 1):
        raw_entries.append(entry)
    
    # Get booking dates for each entry
    booking_ids_needed = list(set(e.get("booking_id") for e in raw_entries if e.get("booking_id")))
    booking_dates = {}
    if booking_ids_needed:
        try:
            object_ids = [ObjectId(bid) for bid in booking_ids_needed]
            async for b in bookings_collection.find(
                {"_id": {"$in": object_ids}},
                {"_id": 1, "date": 1, "company_name": 1}
            ):
                booking_dates[str(b["_id"])] = b.get("date")
        except:
            pass
    
    # CRITICAL: Sort entries so that within the same booking, CREDITS come before DEBITS
    # This ensures correct running balance:
    # If BDM1 earns 20000 and shares 10000 with BDM2, BDM1's transactions should show:
    #   +20000 (earned) then -10000 (shared_given) = balance 10000
    # NOT: -10000 first (which would make balance negative temporarily)
    # 
    # Type priority (credits first, then debits):
    #   earned = 1 (credit)
    #   shared_received = 2 (credit)
    #   shared_given = 3 (debit)
    #   deduction = 4 (debit)
    TYPE_PRIORITY = {
        "earned": 1,
        "shared_received": 2,
        "shared_given": 3,
        "deduction": 4
    }
    
    def sort_key(entry):
        # Primary: booking_date (oldest first)
        booking_id = entry.get("booking_id")
        b_date = booking_dates.get(booking_id) if booking_id else None
        created_at = entry.get("created_at")
        # Use booking date for grouping, fallback to created_at
        group_date = b_date or created_at
        # Secondary: booking_id (keep entries of same booking together)
        # Tertiary: type priority (credits before debits)
        return (
            group_date,
            booking_id or "",
            TYPE_PRIORITY.get(entry.get("type"), 99)
        )
    
    raw_entries.sort(key=sort_key)
    
    # Build entries with running balance
    entries = []
    total_earned = 0
    total_shared_received = 0
    total_shared_given = 0
    total_deductions = 0
    total_credits = 0
    total_debits = 0
    running_balance = 0
    
    for entry in raw_entries:
        entry_type = entry.get("type")
        amount = entry.get("amount", 0)
        
        # Determine credit/debit
        # Credits: earned, shared_received
        # Debits: shared_given, deduction
        is_credit = entry_type in ["earned", "shared_received"]
        credit_amount = amount if is_credit else 0
        debit_amount = amount if not is_credit else 0
        
        # Update running balance
        if is_credit:
            running_balance += amount
            total_credits += amount
        else:
            running_balance -= amount
            total_debits += amount
        
        # Build rich description based on type
        description = entry.get("description", "")
        company_name = entry.get("company_name", "")
        
        if entry_type == "earned":
            full_description = f"Revenue from booking: {company_name}"
            if entry.get("share_percentage"):
                full_description += f" ({entry.get('share_percentage')}% your share)"
        elif entry_type == "shared_received":
            shared_by = entry.get("shared_by_name", "Unknown")
            pct = entry.get("share_percentage", 0)
            full_description = f"Received share from {shared_by} ({pct}%) - Booking: {company_name}"
        elif entry_type == "shared_given":
            shared_to = entry.get("shared_to_name", "Unknown")
            pct = entry.get("share_percentage", 0)
            full_description = f"Shared to {shared_to} ({pct}%) - Booking: {company_name}"
        elif entry_type == "deduction":
            service = entry.get("service_name", "Service")
            full_description = f"Service deduction: {service} - Booking: {company_name}"
        else:
            full_description = description
        
        booking_id = entry.get("booking_id")
        booking_date = booking_dates.get(booking_id) if booking_id else None
        
        entry_data = {
            "id": str(entry["_id"]),
            "booking_id": booking_id,
            "booking_date": booking_date,
            "company_name": company_name,
            "type": entry_type,
            "amount": amount,
            "credit": credit_amount,
            "debit": debit_amount,
            "balance": running_balance,
            "is_credit": is_credit,
            "description": full_description,
            "short_description": description,
            "shared_by": entry.get("shared_by_name"),
            "shared_to": entry.get("shared_to_name"),
            "share_percentage": entry.get("share_percentage"),
            "service_name": entry.get("service_name"),
            "created_at": entry.get("created_at"),
            "term": entry.get("term"),
            "verified": entry.get("verified", False),
            "verified_by": entry.get("verified_by_name")
        }
        entries.append(entry_data)
        
        if entry_type == "earned":
            total_earned += amount
        elif entry_type == "shared_received":
            total_shared_received += amount
        elif entry_type == "shared_given":
            total_shared_given += amount
        elif entry_type == "deduction":
            total_deductions += amount
    
    # Reverse to show most recent first in UI
    entries.reverse()
    
    net_total = total_earned + total_shared_received - total_shared_given - total_deductions
    
    return {
        "user": {
            "id": user_id,
            "name": user_name,
            "role": user_role
        },
        "summary": {
            "total_earned": total_earned,
            "total_shared_received": total_shared_received,
            "total_shared_given": total_shared_given,
            "total_deductions": total_deductions,
            "net_total": net_total,
            "total_transactions": len(entries),
            "total_credits": total_credits,
            "total_debits": total_debits
        },
        "entries": entries
    }


@router.get("/")
async def get_scorecards(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    bdm_id: Optional[str] = Query(None),
    filter_by: str = Query("transaction_date", description="Filter by 'transaction_date' or 'booking_date'"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get scorecard data based on user role:
    - BDM/Senior Admin: Can only see their own scorecard
    - SRDEV: Can see all BDM and Admin scorecards
    
    filter_by:
    - transaction_date: Filter by when scorecard entry was created
    - booking_date: Filter by the actual booking date
    """
    users_collection = get_collection("users")
    
    # Build date filter
    date_filter = {}
    if start_date:
        date_filter["$gte"] = start_date
    if end_date:
        end_of_day = end_date.replace(hour=23, minute=59, second=59)
        date_filter["$lte"] = end_of_day
    
    # Role-based access control
    if current_user["role"] != UserRole.SRDEV:
        # BDM/Senior Admin: Only their own scorecard
        scorecard = await build_scorecard_for_user(
            user_id=current_user["id"],
            user_name=current_user["name"],
            user_role=current_user["role"],
            date_filter=date_filter,
            filter_by=filter_by
        )
        return {
            "scorecards": [scorecard],
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "filter_by": filter_by
            },
            "is_restricted": True
        }
    
    # SRDEV: Can see all scorecards
    bdm_query = {
        "role": {"$in": [UserRole.BDM, UserRole.SENIOR_ADMIN, UserRole.SRDEV]},
        "is_active": True
    }
    if bdm_id:
        try:
            bdm_query["_id"] = ObjectId(bdm_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid BDM ID")
    
    # PERFORMANCE OPTIMIZATION: Use a single aggregation query instead of looping per user
    # The list view only needs summary numbers - full entries load when "View" is clicked
    scorecard_collection = get_collection("scorecard_entries")
    bookings_collection = get_collection("bookings")
    
    # If filtering by booking_date, we need booking IDs first
    booking_id_filter = None
    if filter_by == "booking_date" and date_filter:
        booking_query = {"isDeleted": False}
        if "$gte" in date_filter or "$lte" in date_filter:
            booking_query["date"] = date_filter
        
        booking_ids = []
        async for b in bookings_collection.find(booking_query, {"_id": 1}):
            booking_ids.append(str(b["_id"]))
        booking_id_filter = booking_ids
    
    # Get all eligible users
    users_list = []
    user_id_to_info = {}
    if bdm_id:
        # Single user requested
        async for user in users_collection.find(bdm_query):
            users_list.append(str(user["_id"]))
            user_id_to_info[str(user["_id"])] = {
                "id": str(user["_id"]),
                "name": user["name"],
                "role": user["role"]
            }
    else:
        async for user in users_collection.find(bdm_query):
            users_list.append(str(user["_id"]))
            user_id_to_info[str(user["_id"])] = {
                "id": str(user["_id"]),
                "name": user["name"],
                "role": user["role"]
            }
    
    # Build aggregation match stage
    match_stage = {"user_id": {"$in": users_list}}
    
    if filter_by == "booking_date":
        if booking_id_filter is not None:
            if booking_id_filter:
                match_stage["booking_id"] = {"$in": booking_id_filter}
            else:
                # No bookings in date range
                scorecards = [
                    {
                        "user": user_id_to_info[uid],
                        "summary": {
                            "total_earned": 0, "total_shared_received": 0,
                            "total_shared_given": 0, "total_deductions": 0,
                            "net_total": 0, "total_transactions": 0,
                            "total_credits": 0, "total_debits": 0
                        },
                        "entries": []
                    }
                    for uid in users_list
                ]
                scorecards.sort(key=lambda x: x["summary"]["net_total"], reverse=True)
                return {
                    "scorecards": scorecards,
                    "period": {"start_date": start_date, "end_date": end_date, "filter_by": filter_by},
                    "is_restricted": False
                }
    elif date_filter:
        match_stage["created_at"] = date_filter
    
    # Single aggregation: group by user_id, sum each entry type
    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": "$user_id",
                "total_earned": {
                    "$sum": {"$cond": [{"$eq": ["$type", "earned"]}, "$amount", 0]}
                },
                "total_shared_received": {
                    "$sum": {"$cond": [{"$eq": ["$type", "shared_received"]}, "$amount", 0]}
                },
                "total_shared_given": {
                    "$sum": {"$cond": [{"$eq": ["$type", "shared_given"]}, "$amount", 0]}
                },
                "total_deductions": {
                    "$sum": {"$cond": [{"$eq": ["$type", "deduction"]}, "$amount", 0]}
                },
                "total_transactions": {"$sum": 1}
            }
        }
    ]
    
    aggregation_results = {}
    async for result in scorecard_collection.aggregate(pipeline):
        aggregation_results[result["_id"]] = result
    
    # Build scorecard list (summary only - no entries for list view)
    scorecards = []
    for user_id_str in users_list:
        agg = aggregation_results.get(user_id_str, {})
        total_earned = agg.get("total_earned", 0)
        total_shared_received = agg.get("total_shared_received", 0)
        total_shared_given = agg.get("total_shared_given", 0)
        total_deductions = agg.get("total_deductions", 0)
        total_credits = total_earned + total_shared_received
        total_debits = total_shared_given + total_deductions
        net_total = total_credits - total_debits
        
        scorecards.append({
            "user": user_id_to_info[user_id_str],
            "summary": {
                "total_earned": total_earned,
                "total_shared_received": total_shared_received,
                "total_shared_given": total_shared_given,
                "total_deductions": total_deductions,
                "net_total": net_total,
                "total_transactions": agg.get("total_transactions", 0),
                "total_credits": total_credits,
                "total_debits": total_debits
            },
            "entries": []  # Empty - loaded on demand via /user/{id} when View clicked
        })
    
    # Sort by net total descending
    scorecards.sort(key=lambda x: x["summary"]["net_total"], reverse=True)
    
    return {
        "scorecards": scorecards,
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "filter_by": filter_by
        },
        "is_restricted": False
    }


@router.get("/my")
async def get_my_scorecard(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    filter_by: str = Query("transaction_date"),
    current_user: dict = Depends(get_current_user)
):
    """Get current user's scorecard with full transaction history"""
    date_filter = {}
    if start_date:
        date_filter["$gte"] = start_date
    if end_date:
        end_of_day = end_date.replace(hour=23, minute=59, second=59)
        date_filter["$lte"] = end_of_day
    
    scorecard = await build_scorecard_for_user(
        user_id=current_user["id"],
        user_name=current_user["name"],
        user_role=current_user["role"],
        date_filter=date_filter,
        filter_by=filter_by
    )
    
    return scorecard


@router.get("/user/{user_id}")
async def get_user_scorecard(
    user_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    filter_by: str = Query("transaction_date"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific user's scorecard with full transaction history
    - BDM/Senior Admin: Can only view their own scorecard
    - SRDEV: Can view any user's scorecard
    """
    # Access control
    if current_user["role"] != UserRole.SRDEV and current_user["id"] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only view your own scorecard"
        )
    
    users_collection = get_collection("users")
    
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    date_filter = {}
    if start_date:
        date_filter["$gte"] = start_date
    if end_date:
        end_of_day = end_date.replace(hour=23, minute=59, second=59)
        date_filter["$lte"] = end_of_day
    
    scorecard = await build_scorecard_for_user(
        user_id=str(user["_id"]),
        user_name=user["name"],
        user_role=user["role"],
        date_filter=date_filter,
        filter_by=filter_by
    )
    
    return scorecard


@router.get("/leaderboard")
async def get_leaderboard(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Get leaderboard
    - BDM: Only their own rank shown
    - SRDEV: Full leaderboard
    """
    scorecard_collection = get_collection("scorecard_entries")
    
    # Default to current month
    now = datetime.utcnow()
    target_month = month or now.month
    target_year = year or now.year
    
    start_date = datetime(target_year, target_month, 1)
    if target_month == 12:
        end_date = datetime(target_year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(target_year, target_month + 1, 1) - timedelta(seconds=1)
    
    # Aggregate scorecard by user
    pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start_date, "$lte": end_date},
                "verified": True
            }
        },
        {
            "$group": {
                "_id": "$user_id",
                "user_name": {"$first": "$user_name"},
                "earned": {
                    "$sum": {
                        "$cond": [{"$eq": ["$type", "earned"]}, "$amount", 0]
                    }
                },
                "shared_received": {
                    "$sum": {
                        "$cond": [{"$eq": ["$type", "shared_received"]}, "$amount", 0]
                    }
                },
                "shared_given": {
                    "$sum": {
                        "$cond": [{"$eq": ["$type", "shared_given"]}, "$amount", 0]
                    }
                },
                "deductions": {
                    "$sum": {
                        "$cond": [{"$eq": ["$type", "deduction"]}, "$amount", 0]
                    }
                },
                "booking_count": {
                    "$sum": {
                        "$cond": [{"$eq": ["$type", "earned"]}, 1, 0]
                    }
                }
            }
        },
        {"$sort": {"earned": -1}}
    ]
    
    results = await scorecard_collection.aggregate(pipeline).to_list(100)
    
    leaderboard = []
    for i, item in enumerate(results):
        net_total = item["earned"] + item["shared_received"] - item["shared_given"] - item["deductions"]
        leaderboard.append({
            "rank": i + 1,
            "user_id": item["_id"],
            "user_name": item["user_name"],
            "earned": item["earned"],
            "shared_received": item["shared_received"],
            "shared_given": item["shared_given"],
            "deductions": item["deductions"],
            "net_total": net_total,
            "booking_count": item["booking_count"]
        })
    
    # BDM/Senior Admin can only see their own entry
    if current_user["role"] != UserRole.SRDEV:
        leaderboard = [entry for entry in leaderboard if entry["user_id"] == current_user["id"]]
    
    return {
        "month": target_month,
        "year": target_year,
        "leaderboard": leaderboard,
        "is_restricted": current_user["role"] != UserRole.SRDEV
    }


async def create_scorecard_entry(
    user_id: str,
    user_name: str,
    booking_id: str,
    company_name: str,
    entry_type: str,  # earned, shared_received, shared_given, deduction
    amount: float,
    description: str,
    term: str = None,
    shared_by_id: str = None,
    shared_by_name: str = None,
    shared_to_id: str = None,
    shared_to_name: str = None,
    share_percentage: float = None,
    service_name: str = None,
    verified: bool = False,
    verified_by: str = None,
    verified_by_name: str = None
):
    """Helper function to create scorecard entry"""
    scorecard_collection = get_collection("scorecard_entries")
    
    entry = {
        "user_id": user_id,
        "user_name": user_name,
        "booking_id": booking_id,
        "company_name": company_name,
        "type": entry_type,
        "amount": amount,
        "description": description,
        "term": term,
        "shared_by_id": shared_by_id,
        "shared_by_name": shared_by_name,
        "shared_to_id": shared_to_id,
        "shared_to_name": shared_to_name,
        "share_percentage": share_percentage,
        "service_name": service_name,
        "verified": verified,
        "verified_by": verified_by,
        "verified_by_name": verified_by_name,
        "created_at": datetime.utcnow()
    }
    
    result = await scorecard_collection.insert_one(entry)
    return str(result.inserted_id)
