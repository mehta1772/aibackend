# """
# Dashboard Router
# Handles statistics, analytics, and ML predictions
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from datetime import datetime, timedelta
# from bson import ObjectId
# from typing import Optional
# import calendar

# from app.models.schemas import DashboardStats, DashboardResponse, UserRole
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user

# router = APIRouter()

# @router.get("/stats")
# async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
#     """
#     Get dashboard statistics
#     BDM sees only their stats, Admin/SRDEV sees all
#     """
#     bookings_collection = get_collection("bookings")
#     users_collection = get_collection("users")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     total_bookings = await bookings_collection.count_documents(query)
    
#     if current_user["role"] in [UserRole.SRDEV, UserRole.SENIOR_ADMIN]:
#         total_users = await users_collection.count_documents({"is_active": True})
#     else:
#         total_users = 0
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": None,
#             "total_revenue": {"$sum": "$total_amount"},
#             "total_term1": {"$sum": {"$ifNull": ["$term_1", 0]}},
#             "total_term2": {"$sum": {"$ifNull": ["$term_2", 0]}},
#             "total_term3": {"$sum": {"$ifNull": ["$term_3", 0]}}
#         }}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(1)
    
#     if result:
#         total_revenue = result[0]["total_revenue"]
#         received_amount = result[0]["total_term1"] + result[0]["total_term2"] + result[0]["total_term3"]
#         pending_amount = total_revenue - received_amount
#     else:
#         total_revenue = 0
#         received_amount = 0
#         pending_amount = 0
    
#     now = datetime.utcnow()
#     month_start = datetime(now.year, now.month, 1)
#     month_end = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1], 23, 59, 59)
    
#     monthly_query = {**query, "date": {"$gte": month_start, "$lte": month_end}}
#     monthly_pipeline = [
#         {"$match": monthly_query},
#         {"$group": {
#             "_id": None,
#             "monthly_revenue": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}}
#         }}
#     ]
    
#     monthly_result = await bookings_collection.aggregate(monthly_pipeline).to_list(1)
#     monthly_revenue = monthly_result[0]["monthly_revenue"] if monthly_result else 0
    
#     completed_bookings = await bookings_collection.count_documents({**query, "status": "Completed"})
#     pending_bookings = await bookings_collection.count_documents({**query, "status": "Pending"})
    
#     return {
#         "total_bookings": total_bookings,
#         "total_users": total_users,
#         "total_revenue": total_revenue,
#         "received_amount": received_amount,
#         "pending_amount": pending_amount,
#         "monthly_revenue": monthly_revenue,
#         "completed_bookings": completed_bookings,
#         "pending_bookings": pending_bookings
#     }

# @router.get("/revenue-trends")
# async def get_revenue_trends(
#     months: int = Query(12, ge=1, le=24),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get monthly revenue trends"""
#     bookings_collection = get_collection("bookings")
    
#     now = datetime.utcnow()
#     start_date = datetime(now.year, now.month, 1) - timedelta(days=30 * (months - 1))
    
#     query = {"isDeleted": False, "date": {"$gte": start_date}}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
#             "revenue": {"$sum": "$total_amount"},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}},
#             "bookings": {"$sum": 1}
#         }},
#         {"$sort": {"_id.year": 1, "_id.month": 1}}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(months)
    
#     trends = []
#     for item in result:
#         month_name = datetime(item["_id"]["year"], item["_id"]["month"], 1).strftime("%b %Y")
#         trends.append({
#             "month": month_name,
#             "revenue": item["received"],  # Use received amount as revenue
#             "total_amount": item["revenue"],
#             "bookings": item["bookings"]
#         })
    
#     return trends

# @router.get("/booking-trends")
# async def get_booking_trends(
#     months: int = Query(12, ge=1, le=24),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get monthly booking trends"""
#     bookings_collection = get_collection("bookings")
    
#     now = datetime.utcnow()
#     start_date = datetime(now.year, now.month, 1) - timedelta(days=30 * (months - 1))
    
#     query = {"isDeleted": False, "date": {"$gte": start_date}}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
#             "count": {"$sum": 1},
#             "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}}
#         }},
#         {"$sort": {"_id.year": 1, "_id.month": 1}}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(months)
    
#     trends = []
#     for item in result:
#         month_name = datetime(item["_id"]["year"], item["_id"]["month"], 1).strftime("%b %Y")
#         trends.append({
#             "month": month_name,
#             "total": item["count"],
#             "completed": item["completed"],
#             "pending": item["count"] - item["completed"]
#         })
    
#     return trends

# @router.get("/service-distribution")
# async def get_service_distribution(current_user: dict = Depends(get_current_user)):
#     """Get service-wise distribution"""
#     bookings_collection = get_collection("bookings")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$unwind": "$services"},
#         {"$group": {"_id": "$services", "count": {"$sum": 1}, "revenue": {"$sum": "$total_amount"}}},
#         {"$sort": {"count": -1}},
#         {"$limit": 10}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(10)
    
#     total = sum(item["count"] for item in result)
    
#     distribution = []
#     for item in result:
#         distribution.append({
#             "service": item["_id"],
#             "count": item["count"],
#             "revenue": item["revenue"],
#             "percentage": round((item["count"] / total) * 100, 1) if total > 0 else 0
#         })
    
#     return distribution

# @router.get("/bdm-performance")
# async def get_bdm_performance(current_user: dict = Depends(get_current_user)):
#     """Get BDM-wise performance (Admin/SRDEV only)"""
#     if current_user["role"] == UserRole.BDM:
#         raise HTTPException(status_code=403, detail="Access denied")
    
#     bookings_collection = get_collection("bookings")
    
#     pipeline = [
#         {"$match": {"isDeleted": False}},
#         {"$group": {
#             "_id": "$bdm",
#             "total_bookings": {"$sum": 1},
#             "total_revenue": {"$sum": "$total_amount"},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}},
#             "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}}
#         }},
#         {"$sort": {"total_revenue": -1}}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(100)
    
#     performance = []
#     for item in result:
#         performance.append({
#             "bdm": item["_id"],
#             "total_bookings": item["total_bookings"],
#             "total_revenue": item["total_revenue"],
#             "received": item["received"],
#             "pending": item["total_revenue"] - item["received"],
#             "completed": item["completed"],
#             "conversion_rate": round((item["completed"] / item["total_bookings"]) * 100, 1) if item["total_bookings"] > 0 else 0
#         })
    
#     return performance

# @router.get("/recent-bookings")
# async def get_recent_bookings(
#     limit: int = Query(5, ge=1, le=20),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get recent bookings for dashboard"""
#     bookings_collection = get_collection("bookings")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     cursor = bookings_collection.find(query).sort("createdAt", -1).limit(limit)
    
#     bookings = []
#     async for booking in cursor:
#         bookings.append({
#             "id": str(booking["_id"]),
#             "company_name": booking["company_name"],
#             "services": booking["services"],
#             "total_amount": booking["total_amount"],
#             "status": booking.get("status", "Pending"),
#             "bdm": booking.get("bdm", ""),
#             "date": booking.get("date", booking.get("createdAt"))
#         })
    
#     return bookings

# @router.get("/branch-stats")
# async def get_branch_stats(current_user: dict = Depends(get_current_user)):
#     """Get branch-wise statistics"""
#     bookings_collection = get_collection("bookings")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": "$branch_name",
#             "count": {"$sum": 1},
#             "revenue": {"$sum": "$total_amount"}
#         }}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(10)
    
#     return [{"branch": item["_id"], "count": item["count"], "revenue": item["revenue"]} for item in result]

# @router.get("/ml/predictions")
# async def get_ml_predictions(current_user: dict = Depends(get_current_user)):
#     """Get ML-powered predictions and insights based on RECEIVED amount"""
#     bookings_collection = get_collection("bookings")
    
#     # Get last 6 months data for prediction
#     now = datetime.utcnow()
#     start_date = now - timedelta(days=180)
    
#     query = {"isDeleted": False, "date": {"$gte": start_date}}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     # Monthly RECEIVED revenue for trend analysis
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}},
#             "bookings": {"$sum": 1}
#         }},
#         {"$sort": {"_id.year": 1, "_id.month": 1}}
#     ]
    
#     monthly_data = await bookings_collection.aggregate(pipeline).to_list(12)
    
#     # Simple linear prediction based on RECEIVED amount
#     revenues = [m["received"] for m in monthly_data]
#     if len(revenues) >= 3:
#         avg_growth = sum(revenues[-3:]) / 3
#         trend = "up" if revenues[-1] > revenues[-3] else "down" if revenues[-1] < revenues[-3] else "stable"
#         predicted_revenue = avg_growth * 1.05 if trend == "up" else avg_growth * 0.95
#     else:
#         predicted_revenue = revenues[-1] if revenues else 0
#         trend = "stable"
    
#     # Top services analysis based on received amount
#     service_pipeline = [
#         {"$match": query},
#         {"$unwind": "$services"},
#         {"$group": {
#             "_id": "$services",
#             "count": {"$sum": 1},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}}
#         }},
#         {"$sort": {"received": -1}},
#         {"$limit": 5}
#     ]
    
#     top_services = await bookings_collection.aggregate(service_pipeline).to_list(5)
    
#     service_recommendations = []
#     for svc in top_services:
#         service_recommendations.append({
#             "service": svc["_id"],
#             "score": round(svc["received"] / 10000, 2),
#             "reason": f"High performer with {svc['count']} bookings"
#         })
    
#     # Ad strategy recommendations
#     ad_recommendations = []
#     if trend == "up":
#         ad_recommendations.append("Current momentum is positive. Consider increasing ad spend on top-performing services.")
#     else:
#         ad_recommendations.append("Focus ads on your highest-converting services to stabilize revenue.")
    
#     if top_services:
#         ad_recommendations.append(f"Double down on '{top_services[0]['_id']}' - it's your best performer.")
    
#     ad_recommendations.append("Target existing customers with upsell campaigns for complementary services.")
    
#     return {
#         "revenue_prediction": {
#             "predicted_revenue": round(predicted_revenue, 2),
#             "confidence": 0.75,
#             "trend": trend
#         },
#         "top_services": service_recommendations,
#         "ad_recommendations": ad_recommendations
#     }












# """
# Dashboard Router
# Handles statistics, analytics, and ML predictions
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from datetime import datetime, timedelta
# from bson import ObjectId
# from typing import Optional
# import calendar

# from app.models.schemas import DashboardStats, DashboardResponse, UserRole
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user

# router = APIRouter()

# @router.get("/stats")
# async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
#     """
#     Get dashboard statistics
#     BDM sees only their stats, Admin/SRDEV sees all
#     """
#     bookings_collection = get_collection("bookings")
#     users_collection = get_collection("users")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     total_bookings = await bookings_collection.count_documents(query)
    
#     if current_user["role"] in [UserRole.SRDEV, UserRole.SENIOR_ADMIN]:
#         total_users = await users_collection.count_documents({"is_active": True})
#     else:
#         total_users = 0
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": None,
#             "total_revenue": {"$sum": "$total_amount"},
#             "total_term1": {"$sum": {"$ifNull": ["$term_1", 0]}},
#             "total_term2": {"$sum": {"$ifNull": ["$term_2", 0]}},
#             "total_term3": {"$sum": {"$ifNull": ["$term_3", 0]}}
#         }}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(1)
    
#     if result:
#         total_revenue = result[0]["total_revenue"]
#         received_amount = result[0]["total_term1"] + result[0]["total_term2"] + result[0]["total_term3"]
#         pending_amount = total_revenue - received_amount
#     else:
#         total_revenue = 0
#         received_amount = 0
#         pending_amount = 0
    
#     now = datetime.utcnow()
#     month_start = datetime(now.year, now.month, 1)
#     month_end = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1], 23, 59, 59)
    
#     monthly_query = {**query, "date": {"$gte": month_start, "$lte": month_end}}
#     monthly_pipeline = [
#         {"$match": monthly_query},
#         {"$group": {
#             "_id": None,
#             "monthly_revenue": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}}
#         }}
#     ]
    
#     monthly_result = await bookings_collection.aggregate(monthly_pipeline).to_list(1)
#     monthly_revenue = monthly_result[0]["monthly_revenue"] if monthly_result else 0
    
#     completed_bookings = await bookings_collection.count_documents({**query, "status": "Completed"})
#     pending_bookings = await bookings_collection.count_documents({**query, "status": "Pending"})
    
#     return {
#         "total_bookings": total_bookings,
#         "total_users": total_users,
#         "total_revenue": total_revenue,
#         "received_amount": received_amount,
#         "pending_amount": pending_amount,
#         "monthly_revenue": monthly_revenue,
#         "completed_bookings": completed_bookings,
#         "pending_bookings": pending_bookings
#     }

# @router.get("/revenue-trends")
# async def get_revenue_trends(
#     months: int = Query(12, ge=1, le=24),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get monthly revenue trends"""
#     bookings_collection = get_collection("bookings")
    
#     now = datetime.utcnow()
#     start_date = datetime(now.year, now.month, 1) - timedelta(days=30 * (months - 1))
    
#     query = {"isDeleted": False, "date": {"$gte": start_date}}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
#             "revenue": {"$sum": "$total_amount"},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}},
#             "bookings": {"$sum": 1}
#         }},
#         {"$sort": {"_id.year": 1, "_id.month": 1}}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(months)
    
#     trends = []
#     for item in result:
#         month_name = datetime(item["_id"]["year"], item["_id"]["month"], 1).strftime("%b %Y")
#         trends.append({
#             "month": month_name,
#             "revenue": item["received"],  # Use received amount as revenue
#             "total_amount": item["revenue"],
#             "bookings": item["bookings"]
#         })
    
#     return trends

# @router.get("/booking-trends")
# async def get_booking_trends(
#     months: int = Query(12, ge=1, le=24),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get monthly booking trends"""
#     bookings_collection = get_collection("bookings")
    
#     now = datetime.utcnow()
#     start_date = datetime(now.year, now.month, 1) - timedelta(days=30 * (months - 1))
    
#     query = {"isDeleted": False, "date": {"$gte": start_date}}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
#             "count": {"$sum": 1},
#             "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}}
#         }},
#         {"$sort": {"_id.year": 1, "_id.month": 1}}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(months)
    
#     trends = []
#     for item in result:
#         month_name = datetime(item["_id"]["year"], item["_id"]["month"], 1).strftime("%b %Y")
#         trends.append({
#             "month": month_name,
#             "total": item["count"],
#             "completed": item["completed"],
#             "pending": item["count"] - item["completed"]
#         })
    
#     return trends

# @router.get("/service-distribution")
# async def get_service_distribution(current_user: dict = Depends(get_current_user)):
#     """Get service-wise distribution"""
#     bookings_collection = get_collection("bookings")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$unwind": "$services"},
#         {"$group": {"_id": "$services", "count": {"$sum": 1}, "revenue": {"$sum": "$total_amount"}}},
#         {"$sort": {"count": -1}},
#         {"$limit": 10}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(10)
    
#     total = sum(item["count"] for item in result)
    
#     distribution = []
#     for item in result:
#         distribution.append({
#             "service": item["_id"],
#             "count": item["count"],
#             "revenue": item["revenue"],
#             "percentage": round((item["count"] / total) * 100, 1) if total > 0 else 0
#         })
    
#     return distribution

# @router.get("/bdm-performance")
# async def get_bdm_performance(current_user: dict = Depends(get_current_user)):
#     """Get BDM-wise performance (Admin/SRDEV only)"""
#     if current_user["role"] == UserRole.BDM:
#         raise HTTPException(status_code=403, detail="Access denied")
    
#     bookings_collection = get_collection("bookings")
    
#     pipeline = [
#         {"$match": {"isDeleted": False}},
#         {"$group": {
#             "_id": "$bdm",
#             "total_bookings": {"$sum": 1},
#             "total_revenue": {"$sum": "$total_amount"},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}},
#             "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}}
#         }},
#         {"$sort": {"total_revenue": -1}}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(100)
    
#     performance = []
#     for item in result:
#         performance.append({
#             "bdm": item["_id"],
#             "total_bookings": item["total_bookings"],
#             "total_revenue": item["total_revenue"],
#             "received": item["received"],
#             "pending": item["total_revenue"] - item["received"],
#             "completed": item["completed"],
#             "conversion_rate": round((item["completed"] / item["total_bookings"]) * 100, 1) if item["total_bookings"] > 0 else 0
#         })
    
#     return performance

# @router.get("/recent-bookings")
# async def get_recent_bookings(
#     limit: int = Query(5, ge=1, le=20),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get recent bookings for dashboard"""
#     bookings_collection = get_collection("bookings")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     cursor = bookings_collection.find(query).sort("createdAt", -1).limit(limit)
    
#     bookings = []
#     async for booking in cursor:
#         bookings.append({
#             "id": str(booking["_id"]),
#             "company_name": booking["company_name"],
#             "services": booking["services"],
#             "total_amount": booking["total_amount"],
#             "status": booking.get("status", "Pending"),
#             "bdm": booking.get("bdm", ""),
#             "date": booking.get("date", booking.get("createdAt"))
#         })
    
#     return bookings

# @router.get("/branch-stats")
# async def get_branch_stats(current_user: dict = Depends(get_current_user)):
#     """Get branch-wise statistics"""
#     bookings_collection = get_collection("bookings")
    
#     query = {"isDeleted": False}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": "$branch_name",
#             "count": {"$sum": 1},
#             "revenue": {"$sum": "$total_amount"}
#         }}
#     ]
    
#     result = await bookings_collection.aggregate(pipeline).to_list(10)
    
#     return [{"branch": item["_id"], "count": item["count"], "revenue": item["revenue"]} for item in result]

# @router.get("/ml/predictions")
# async def get_ml_predictions(current_user: dict = Depends(get_current_user)):
#     """Get ML-powered predictions and insights based on RECEIVED amount"""
#     bookings_collection = get_collection("bookings")
    
#     # Get last 6 months data for prediction
#     now = datetime.utcnow()
#     start_date = now - timedelta(days=180)
    
#     query = {"isDeleted": False, "date": {"$gte": start_date}}
    
#     if current_user["role"] == UserRole.BDM:
#         query["user_id"] = current_user["id"]
    
#     # Monthly RECEIVED revenue for trend analysis
#     pipeline = [
#         {"$match": query},
#         {"$group": {
#             "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}},
#             "bookings": {"$sum": 1}
#         }},
#         {"$sort": {"_id.year": 1, "_id.month": 1}}
#     ]
    
#     monthly_data = await bookings_collection.aggregate(pipeline).to_list(12)
    
#     # Simple linear prediction based on RECEIVED amount
#     revenues = [m["received"] for m in monthly_data]
#     if len(revenues) >= 3:
#         avg_growth = sum(revenues[-3:]) / 3
#         trend = "up" if revenues[-1] > revenues[-3] else "down" if revenues[-1] < revenues[-3] else "stable"
#         predicted_revenue = avg_growth * 1.05 if trend == "up" else avg_growth * 0.95
#     else:
#         predicted_revenue = revenues[-1] if revenues else 0
#         trend = "stable"
    
#     # Top services analysis based on received amount
#     service_pipeline = [
#         {"$match": query},
#         {"$unwind": "$services"},
#         {"$group": {
#             "_id": "$services",
#             "count": {"$sum": 1},
#             "received": {"$sum": {"$add": [
#                 {"$ifNull": ["$term_1", 0]},
#                 {"$ifNull": ["$term_2", 0]},
#                 {"$ifNull": ["$term_3", 0]}
#             ]}}
#         }},
#         {"$sort": {"received": -1}},
#         {"$limit": 5}
#     ]
    
#     top_services = await bookings_collection.aggregate(service_pipeline).to_list(5)
    
#     service_recommendations = []
#     for svc in top_services:
#         service_recommendations.append({
#             "service": svc["_id"],
#             "score": round(svc["received"] / 10000, 2),
#             "reason": f"High performer with {svc['count']} bookings"
#         })
    
#     # Ad strategy recommendations
#     ad_recommendations = []
#     if trend == "up":
#         ad_recommendations.append("Current momentum is positive. Consider increasing ad spend on top-performing services.")
#     else:
#         ad_recommendations.append("Focus ads on your highest-converting services to stabilize revenue.")
    
#     if top_services:
#         ad_recommendations.append(f"Double down on '{top_services[0]['_id']}' - it's your best performer.")
    
#     ad_recommendations.append("Target existing customers with upsell campaigns for complementary services.")
    
#     return {
#         "revenue_prediction": {
#             "predicted_revenue": round(predicted_revenue, 2),
#             "confidence": 0.75,
#             "trend": trend
#         },
#         "top_services": service_recommendations,
#         "ad_recommendations": ad_recommendations
#     }

# @router.get("/payment-reminders")
# async def get_payment_reminders(current_user: dict = Depends(get_current_user)):
#     """
#     Get payment reminders for bookings with pending amounts
#     Shows bookings older than 10 days with pending payments
#     BDM sees only their reminders, Admin sees all
#     """
#     bookings_collection = get_collection("bookings")
    
#     # Calculate date 10 days ago
#     ten_days_ago = datetime.utcnow() - timedelta(days=10)
    
#     # Build query for bookings with pending payments
#     query = {
#         "isDeleted": False,
#         "date": {"$lte": ten_days_ago},  # Booking older than 10 days
#     }
    
#     # Role-based filtering
#     if current_user["role"] == UserRole.BDM:
#         query["$or"] = [
#             {"user_id": current_user["id"]},
#             {"bdm": {"$regex": f"^{current_user['name']}$", "$options": "i"}}
#         ]
    
#     cursor = bookings_collection.find(query).sort("date", 1)
    
#     reminders = []
#     async for booking in cursor:
#         # Calculate amounts
#         term_1 = booking.get("term_1") or 0
#         term_2 = booking.get("term_2") or 0
#         term_3 = booking.get("term_3") or 0
#         total_amount = booking.get("total_amount") or 0
#         received_amount = term_1 + term_2 + term_3
#         pending_amount = total_amount - received_amount
        
#         # Only include if there's pending amount
#         if pending_amount > 0:
#             # Calculate days since booking
#             booking_date = booking.get("date") or booking.get("createdAt")
#             if isinstance(booking_date, str):
#                 try:
#                     booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
#                 except:
#                     booking_date = datetime.utcnow()
            
#             days_since = (datetime.utcnow() - booking_date).days
            
#             # Determine urgency
#             if days_since > 30:
#                 urgency = "high"
#                 message = f"🔴 Urgent! {days_since} days overdue. Please collect pending amount immediately."
#             elif days_since > 20:
#                 urgency = "medium"
#                 message = f"🟠 Follow up needed! {days_since} days since booking. Time to collect remaining payment."
#             else:
#                 urgency = "low"
#                 message = f"🟡 Gentle reminder: {days_since} days since booking. Please follow up for pending amount."
            
#             reminders.append({
#                 "id": str(booking["_id"]),
#                 "company_name": booking.get("company_name", ""),
#                 "contact_person": booking.get("contact_person", ""),
#                 "contact_no": str(booking.get("contact_no", "")),
#                 "email": booking.get("email", ""),
#                 "total_amount": total_amount,
#                 "received_amount": received_amount,
#                 "pending_amount": pending_amount,
#                 "booking_date": booking_date,
#                 "days_since": days_since,
#                 "urgency": urgency,
#                 "message": message,
#                 "bdm": booking.get("bdm", ""),
#                 "services": booking.get("services", [])
#             })
    
#     # Sort by urgency (high first) and then by days
#     urgency_order = {"high": 0, "medium": 1, "low": 2}
#     reminders.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), -x["days_since"]))
    
#     return {
#         "reminders": reminders,
#         "total_count": len(reminders),
#         "high_priority": len([r for r in reminders if r["urgency"] == "high"]),
#         "medium_priority": len([r for r in reminders if r["urgency"] == "medium"]),
#         "low_priority": len([r for r in reminders if r["urgency"] == "low"])
#     }












"""
Dashboard Router
Handles statistics, analytics, and ML predictions
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
import calendar

from app.models.schemas import DashboardStats, DashboardResponse, UserRole
from app.utils.database import get_collection
from app.utils.auth import get_current_user

router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """
    Get dashboard statistics
    BDM sees only their stats, Admin/SRDEV sees all
    """
    bookings_collection = get_collection("bookings")
    users_collection = get_collection("users")
    
    query = {"isDeleted": False}
    
    if current_user["role"] == UserRole.BDM:
        query["user_id"] = current_user["id"]
    
    total_bookings = await bookings_collection.count_documents(query)
    
    if current_user["role"] in [UserRole.SRDEV, UserRole.SENIOR_ADMIN]:
        total_users = await users_collection.count_documents({"is_active": True})
    else:
        total_users = 0
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": None,
            "total_revenue": {"$sum": "$total_amount"},
            "total_term1": {"$sum": {"$ifNull": ["$term_1", 0]}},
            "total_term2": {"$sum": {"$ifNull": ["$term_2", 0]}},
            "total_term3": {"$sum": {"$ifNull": ["$term_3", 0]}}
        }}
    ]
    
    result = await bookings_collection.aggregate(pipeline).to_list(1)
    
    if result:
        total_revenue = result[0]["total_revenue"]
        received_amount = result[0]["total_term1"] + result[0]["total_term2"] + result[0]["total_term3"]
        pending_amount = total_revenue - received_amount
    else:
        total_revenue = 0
        received_amount = 0
        pending_amount = 0
    
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    month_end = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1], 23, 59, 59)
    
    monthly_query = {**query, "date": {"$gte": month_start, "$lte": month_end}}
    monthly_pipeline = [
        {"$match": monthly_query},
        {"$group": {
            "_id": None,
            "monthly_revenue": {"$sum": {"$add": [
                {"$ifNull": ["$term_1", 0]},
                {"$ifNull": ["$term_2", 0]},
                {"$ifNull": ["$term_3", 0]}
            ]}}
        }}
    ]
    
    monthly_result = await bookings_collection.aggregate(monthly_pipeline).to_list(1)
    monthly_revenue = monthly_result[0]["monthly_revenue"] if monthly_result else 0
    
    completed_bookings = await bookings_collection.count_documents({**query, "status": "Completed"})
    pending_bookings = await bookings_collection.count_documents({**query, "status": "Pending"})
    
    return {
        "total_bookings": total_bookings,
        "total_users": total_users,
        "total_revenue": total_revenue,
        "received_amount": received_amount,
        "pending_amount": pending_amount,
        "monthly_revenue": monthly_revenue,
        "completed_bookings": completed_bookings,
        "pending_bookings": pending_bookings
    }

@router.get("/revenue-trends")
async def get_revenue_trends(
    months: int = Query(12, ge=1, le=24),
    current_user: dict = Depends(get_current_user)
):
    """Get monthly revenue trends"""
    bookings_collection = get_collection("bookings")
    
    now = datetime.utcnow()
    start_date = datetime(now.year, now.month, 1) - timedelta(days=30 * (months - 1))
    
    query = {"isDeleted": False, "date": {"$gte": start_date}}
    
    if current_user["role"] == UserRole.BDM:
        query["user_id"] = current_user["id"]
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
            "revenue": {"$sum": "$total_amount"},
            "received": {"$sum": {"$add": [
                {"$ifNull": ["$term_1", 0]},
                {"$ifNull": ["$term_2", 0]},
                {"$ifNull": ["$term_3", 0]}
            ]}},
            "bookings": {"$sum": 1}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}}
    ]
    
    result = await bookings_collection.aggregate(pipeline).to_list(months)
    
    trends = []
    for item in result:
        month_name = datetime(item["_id"]["year"], item["_id"]["month"], 1).strftime("%b %Y")
        trends.append({
            "month": month_name,
            "revenue": item["received"],  # Use received amount as revenue
            "total_amount": item["revenue"],
            "bookings": item["bookings"]
        })
    
    return trends

@router.get("/booking-trends")
async def get_booking_trends(
    months: int = Query(12, ge=1, le=24),
    current_user: dict = Depends(get_current_user)
):
    """Get monthly booking trends"""
    bookings_collection = get_collection("bookings")
    
    now = datetime.utcnow()
    start_date = datetime(now.year, now.month, 1) - timedelta(days=30 * (months - 1))
    
    query = {"isDeleted": False, "date": {"$gte": start_date}}
    
    if current_user["role"] == UserRole.BDM:
        query["user_id"] = current_user["id"]
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
            "count": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}}
    ]
    
    result = await bookings_collection.aggregate(pipeline).to_list(months)
    
    trends = []
    for item in result:
        month_name = datetime(item["_id"]["year"], item["_id"]["month"], 1).strftime("%b %Y")
        trends.append({
            "month": month_name,
            "total": item["count"],
            "completed": item["completed"],
            "pending": item["count"] - item["completed"]
        })
    
    return trends

@router.get("/service-distribution")
async def get_service_distribution(current_user: dict = Depends(get_current_user)):
    """Get service-wise distribution"""
    bookings_collection = get_collection("bookings")
    
    query = {"isDeleted": False}
    
    if current_user["role"] == UserRole.BDM:
        query["user_id"] = current_user["id"]
    
    pipeline = [
        {"$match": query},
        {"$unwind": "$services"},
        {"$group": {"_id": "$services", "count": {"$sum": 1}, "revenue": {"$sum": "$total_amount"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    
    result = await bookings_collection.aggregate(pipeline).to_list(10)
    
    total = sum(item["count"] for item in result)
    
    distribution = []
    for item in result:
        distribution.append({
            "service": item["_id"],
            "count": item["count"],
            "revenue": item["revenue"],
            "percentage": round((item["count"] / total) * 100, 1) if total > 0 else 0
        })
    
    return distribution

@router.get("/bdm-performance")
async def get_bdm_performance(current_user: dict = Depends(get_current_user)):
    """Get BDM-wise performance (Admin/SRDEV only)"""
    if current_user["role"] == UserRole.BDM:
        raise HTTPException(status_code=403, detail="Access denied")
    
    bookings_collection = get_collection("bookings")
    
    pipeline = [
        {"$match": {"isDeleted": False}},
        {"$group": {
            "_id": "$bdm",
            "total_bookings": {"$sum": 1},
            "total_revenue": {"$sum": "$total_amount"},
            "received": {"$sum": {"$add": [
                {"$ifNull": ["$term_1", 0]},
                {"$ifNull": ["$term_2", 0]},
                {"$ifNull": ["$term_3", 0]}
            ]}},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}}
        }},
        {"$sort": {"total_revenue": -1}}
    ]
    
    result = await bookings_collection.aggregate(pipeline).to_list(100)
    
    performance = []
    for item in result:
        performance.append({
            "bdm": item["_id"],
            "total_bookings": item["total_bookings"],
            "total_revenue": item["total_revenue"],
            "received": item["received"],
            "pending": item["total_revenue"] - item["received"],
            "completed": item["completed"],
            "conversion_rate": round((item["completed"] / item["total_bookings"]) * 100, 1) if item["total_bookings"] > 0 else 0
        })
    
    return performance

@router.get("/recent-bookings")
async def get_recent_bookings(
    limit: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user)
):
    """Get recent bookings for dashboard"""
    bookings_collection = get_collection("bookings")
    
    query = {"isDeleted": False}
    
    if current_user["role"] == UserRole.BDM:
        query["user_id"] = current_user["id"]
    
    cursor = bookings_collection.find(query).sort("createdAt", -1).limit(limit)
    
    bookings = []
    async for booking in cursor:
        bookings.append({
            "id": str(booking["_id"]),
            "company_name": booking["company_name"],
            "services": booking["services"],
            "total_amount": booking["total_amount"],
            "status": booking.get("status", "Pending"),
            "bdm": booking.get("bdm", ""),
            "date": booking.get("date", booking.get("createdAt"))
        })
    
    return bookings

@router.get("/branch-stats")
async def get_branch_stats(current_user: dict = Depends(get_current_user)):
    """Get branch-wise statistics"""
    bookings_collection = get_collection("bookings")
    
    query = {"isDeleted": False}
    
    if current_user["role"] == UserRole.BDM:
        query["user_id"] = current_user["id"]
    
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$branch_name",
            "count": {"$sum": 1},
            "revenue": {"$sum": "$total_amount"}
        }}
    ]
    
    result = await bookings_collection.aggregate(pipeline).to_list(10)
    
    return [{"branch": item["_id"], "count": item["count"], "revenue": item["revenue"]} for item in result]

@router.get("/ml/predictions")
async def get_ml_predictions(current_user: dict = Depends(get_current_user)):
    """Get ML-powered predictions and insights based on RECEIVED amount"""
    bookings_collection = get_collection("bookings")
    
    # Get last 6 months data for prediction
    now = datetime.utcnow()
    start_date = now - timedelta(days=180)
    
    query = {"isDeleted": False, "date": {"$gte": start_date}}
    
    if current_user["role"] == UserRole.BDM:
        query["user_id"] = current_user["id"]
    
    # Monthly RECEIVED revenue for trend analysis
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {"year": {"$year": "$date"}, "month": {"$month": "$date"}},
            "received": {"$sum": {"$add": [
                {"$ifNull": ["$term_1", 0]},
                {"$ifNull": ["$term_2", 0]},
                {"$ifNull": ["$term_3", 0]}
            ]}},
            "bookings": {"$sum": 1}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}}
    ]
    
    monthly_data = await bookings_collection.aggregate(pipeline).to_list(12)
    
    # Simple linear prediction based on RECEIVED amount
    revenues = [m["received"] for m in monthly_data]
    if len(revenues) >= 3:
        avg_growth = sum(revenues[-3:]) / 3
        trend = "up" if revenues[-1] > revenues[-3] else "down" if revenues[-1] < revenues[-3] else "stable"
        predicted_revenue = avg_growth * 1.05 if trend == "up" else avg_growth * 0.95
    else:
        predicted_revenue = revenues[-1] if revenues else 0
        trend = "stable"
    
    # Top services analysis based on received amount
    service_pipeline = [
        {"$match": query},
        {"$unwind": "$services"},
        {"$group": {
            "_id": "$services",
            "count": {"$sum": 1},
            "received": {"$sum": {"$add": [
                {"$ifNull": ["$term_1", 0]},
                {"$ifNull": ["$term_2", 0]},
                {"$ifNull": ["$term_3", 0]}
            ]}}
        }},
        {"$sort": {"received": -1}},
        {"$limit": 5}
    ]
    
    top_services = await bookings_collection.aggregate(service_pipeline).to_list(5)
    
    service_recommendations = []
    for svc in top_services:
        service_recommendations.append({
            "service": svc["_id"],
            "score": round(svc["received"] / 10000, 2),
            "reason": f"High performer with {svc['count']} bookings"
        })
    
    # Ad strategy recommendations
    ad_recommendations = []
    if trend == "up":
        ad_recommendations.append("Current momentum is positive. Consider increasing ad spend on top-performing services.")
    else:
        ad_recommendations.append("Focus ads on your highest-converting services to stabilize revenue.")
    
    if top_services:
        ad_recommendations.append(f"Double down on '{top_services[0]['_id']}' - it's your best performer.")
    
    ad_recommendations.append("Target existing customers with upsell campaigns for complementary services.")
    
    return {
        "revenue_prediction": {
            "predicted_revenue": round(predicted_revenue, 2),
            "confidence": 0.75,
            "trend": trend
        },
        "top_services": service_recommendations,
        "ad_recommendations": ad_recommendations
    }

@router.get("/payment-reminders")
async def get_payment_reminders(current_user: dict = Depends(get_current_user)):
    """
    Get payment reminders for bookings with pending amounts
    Shows bookings older than 10 days with pending payments
    BDM sees only their reminders, Admin sees all
    """
    bookings_collection = get_collection("bookings")
    
    # Calculate date 10 days ago
    ten_days_ago = datetime.utcnow() - timedelta(days=10)
    
    # Build query for bookings with pending payments
    query = {
        "isDeleted": False,
        "date": {"$lte": ten_days_ago},  # Booking older than 10 days
    }
    
    # Role-based filtering
    if current_user["role"] == UserRole.BDM:
        query["$or"] = [
            {"user_id": current_user["id"]},
            {"bdm": {"$regex": f"^{current_user['name']}$", "$options": "i"}}
        ]
    
    cursor = bookings_collection.find(query).sort("date", 1)
    
    reminders = []
    async for booking in cursor:
        # Calculate amounts
        term_1 = booking.get("term_1") or 0
        term_2 = booking.get("term_2") or 0
        term_3 = booking.get("term_3") or 0
        total_amount = booking.get("total_amount") or 0
        received_amount = term_1 + term_2 + term_3
        pending_amount = total_amount - received_amount
        
        # Only include if there's pending amount
        if pending_amount > 0:
            # Calculate days since booking
            booking_date = booking.get("date") or booking.get("createdAt")
            if isinstance(booking_date, str):
                try:
                    booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
                except:
                    booking_date = datetime.utcnow()
            
            days_since = (datetime.utcnow() - booking_date).days
            
            # Determine urgency and funky message
            if days_since > 30:
                urgency = "high"
                message = f"🔴 Urgent! {days_since} days overdue. Please collect pending amount immediately."
                funky_messages = [
                    f"Yo! {days_since} days gone! Time to get that 💰 rolling in!",
                    f"Alert! 🚨 {days_since} days waiting. Money doesn't grow on trees!",
                    f"Holy smokes! {days_since} days! Chase that payment NOW! 🏃‍♂️",
                    f"Red alert! 🔴 {days_since} days overdue. Let's close this deal!",
                ]
            elif days_since > 20:
                urgency = "medium"
                message = f"🟠 Follow up needed! {days_since} days since booking. Time to collect remaining payment."
                funky_messages = [
                    f"Hey there! {days_since} days passed. Time for a friendly nudge! 👋",
                    f"Tick tock! ⏰ {days_since} days. Let's wrap up this payment!",
                    f"Gentle push! {days_since} days in. Get that pending amount! 💪",
                    f"Follow-up time! {days_since} days. Make that call today! 📞",
                ]
            else:
                urgency = "low"
                message = f"🟡 Gentle reminder: {days_since} days since booking. Please follow up for pending amount."
                funky_messages = [
                    f"Quick check-in! {days_since} days. Maybe drop a hello? 😊",
                    f"Just saying hi! {days_since} days passed. Pending payment awaits! ✨",
                    f"Friendly reminder! {days_since} days. Good time to follow up! 🌟",
                    f"Heads up! {days_since} days in. A quick call could seal the deal! 🎯",
                ]
            
            import random
            funky_message = random.choice(funky_messages)
            
            reminders.append({
                "id": str(booking["_id"]),
                "company_name": booking.get("company_name", ""),
                "contact_person": booking.get("contact_person", ""),
                "contact_no": str(booking.get("contact_no", "")),
                "email": booking.get("email", ""),
                "total_amount": total_amount,
                "received_amount": received_amount,
                "pending_amount": pending_amount,
                "booking_date": booking_date,
                "days_since": days_since,
                "urgency": urgency,
                "message": message,
                "funky_message": funky_message,
                "bdm": booking.get("bdm", ""),
                "services": booking.get("services", [])
            })
    
    # Sort by urgency (high first) and then by days
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    reminders.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), -x["days_since"]))
    
    return {
        "reminders": reminders,
        "total_count": len(reminders),
        "high_priority": len([r for r in reminders if r["urgency"] == "high"]),
        "medium_priority": len([r for r in reminders if r["urgency"] == "medium"]),
        "low_priority": len([r for r in reminders if r["urgency"] == "low"])
    }
