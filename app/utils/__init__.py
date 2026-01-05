"""
Utils Module
Common utilities for the CRM application
"""

from .database import get_database, get_collection
from .auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    require_roles,
    require_srdev,
    require_admin,
    require_all
)
from .email_service import send_welcome_email, send_invoice_email
from .s3_service import upload_document, delete_document, get_presigned_url

__all__ = [
    "get_database",
    "get_collection",
    "get_password_hash",
    "verify_password",
    "create_access_token",
    "get_current_user",
    "require_roles",
    "require_srdev",
    "require_admin",
    "require_all",
    "send_welcome_email",
    "send_invoice_email",
    "upload_document",
    "delete_document",
    "get_presigned_url"
]
