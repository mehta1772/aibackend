"""
Routers Module
All API route handlers
"""

from . import auth, users, bookings, services, dashboard, trash, documents, invoices, profiles

__all__ = [
    "auth",
    "users",
    "bookings",
    "services",
    "dashboard",
    "trash",
    "documents",
    "invoices",
    "profiles"
]
