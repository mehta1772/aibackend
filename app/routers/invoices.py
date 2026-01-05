"""
Invoices Router
Handles Performa Invoice generation with PDF download
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse
from datetime import datetime
from bson import ObjectId
from typing import Optional
from io import BytesIO
import os

from app.models.schemas import InvoiceCreate, UserRole
from app.utils.database import get_collection
from app.utils.auth import get_current_user
from app.utils.email_service import send_invoice_email

router = APIRouter()

# Company details for invoice
COMPANY_NAME = os.getenv("COMPANY_NAME", "Your Company Name")
COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "123 Business Street, City, State - 123456")
COMPANY_GST = os.getenv("COMPANY_GST", "GSTIN123456789")
COMPANY_PAN = os.getenv("COMPANY_PAN", "ABCDE1234F")
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "accounts@company.com")
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "+91 9999999999")

def generate_invoice_number():
    """Generate unique invoice number"""
    now = datetime.utcnow()
    return f"PI-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

async def generate_pdf(invoice_data: dict) -> bytes:
    """Generate PDF for invoice using reportlab"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    except ImportError:
        # Return simple text if reportlab not available
        return f"Invoice #{invoice_data['invoice_number']}\nTotal: {invoice_data['total_amount']}".encode()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6
    )
    
    # Title
    elements.append(Paragraph("PERFORMA INVOICE", title_style))
    elements.append(Spacer(1, 20))
    
    # Company Header
    company_info = f"""
    <b>{COMPANY_NAME}</b><br/>
    {COMPANY_ADDRESS}<br/>
    GST: {COMPANY_GST} | PAN: {COMPANY_PAN}<br/>
    Email: {COMPANY_EMAIL} | Phone: {COMPANY_PHONE}
    """
    elements.append(Paragraph(company_info, header_style))
    elements.append(Spacer(1, 30))
    
    # Invoice details
    invoice_info = [
        ['Invoice Number:', invoice_data['invoice_number']],
        ['Date:', invoice_data['date'].strftime('%d-%m-%Y')],
    ]
    
    t = Table(invoice_info, colWidths=[120, 200])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Bill To
    elements.append(Paragraph("<b>BILL TO:</b>", header_style))
    bill_to = f"""
    <b>{invoice_data['company_name']}</b><br/>
    {invoice_data['client_name']}<br/>
    {invoice_data['street_address']}, {invoice_data['city']}<br/>
    GST/PAN: {invoice_data['gst_pan']}<br/>
    Email: {invoice_data['email']}
    """
    elements.append(Paragraph(bill_to, header_style))
    elements.append(Spacer(1, 30))
    
    # Invoice items table
    table_data = [
        ['Description', 'Amount (₹)'],
        ['Service Fee', f"₹{invoice_data['service_fee']:,.2f}"],
        ['GST (18%)', f"₹{invoice_data['gst_amount']:,.2f}"],
        ['', ''],
        ['TOTAL', f"₹{invoice_data['total_amount']:,.2f}"],
    ]
    
    t = Table(table_data, colWidths=[350, 150])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#dddddd')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#667eea')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 40))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER
    )
    
    elements.append(Paragraph("This is a computer-generated invoice and does not require a signature.", footer_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Thank you for your business with {COMPANY_NAME}!", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

@router.post("/create")
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create new Performa Invoice
    Accessible to BDM, Senior Admin, SRDEV
    """
    invoices_collection = get_collection("invoices")
    
    # Generate invoice number
    invoice_number = generate_invoice_number()
    
    # Calculate total
    total_amount = invoice_data.service_fee + invoice_data.gst_amount
    
    # Create invoice record
    invoice = {
        "invoice_number": invoice_number,
        "company_name": invoice_data.company_name,
        "client_name": invoice_data.client_name,
        "email": invoice_data.email,
        "street_address": invoice_data.street_address,
        "city": invoice_data.city,
        "gst_pan": invoice_data.gst_pan,
        "service_fee": invoice_data.service_fee,
        "gst_amount": invoice_data.gst_amount,
        "total_amount": total_amount,
        "date": datetime.utcnow(),
        "created_by": current_user["id"],
        "created_by_name": current_user["name"],
        "created_at": datetime.utcnow()
    }
    
    result = await invoices_collection.insert_one(invoice)
    
    # Generate PDF
    pdf_bytes = await generate_pdf(invoice)
    
    return {
        "id": str(result.inserted_id),
        "invoice_number": invoice_number,
        "total_amount": total_amount,
        "message": "Invoice created successfully",
        "pdf_ready": True
    }

@router.get("/{invoice_id}/download")
async def download_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Download invoice as PDF"""
    invoices_collection = get_collection("invoices")
    
    try:
        invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Generate PDF
    pdf_bytes = await generate_pdf(invoice)
    
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Invoice_{invoice['invoice_number']}.pdf"
        }
    )

@router.get("/")
async def get_all_invoices(
    search: Optional[str] = Query(None, description="Search company or client name"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get all invoices"""
    invoices_collection = get_collection("invoices")
    
    query = {}
    
    # BDM can only see their invoices
    if current_user["role"] == UserRole.BDM:
        query["created_by"] = current_user["id"]
    
    if search:
        query["$or"] = [
            {"company_name": {"$regex": search, "$options": "i"}},
            {"client_name": {"$regex": search, "$options": "i"}},
            {"invoice_number": {"$regex": search, "$options": "i"}}
        ]
    
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    total = await invoices_collection.count_documents(query)
    
    skip = (page - 1) * page_size
    cursor = invoices_collection.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    
    invoices = []
    async for invoice in cursor:
        invoices.append({
            "id": str(invoice["_id"]),
            "invoice_number": invoice["invoice_number"],
            "company_name": invoice["company_name"],
            "client_name": invoice["client_name"],
            "email": invoice["email"],
            "total_amount": invoice["total_amount"],
            "date": invoice["date"],
            "created_by_name": invoice.get("created_by_name", "Unknown")
        })
    
    return {
        "items": invoices,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Get single invoice details"""
    invoices_collection = get_collection("invoices")
    
    try:
        invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # BDM can only see their invoices
    if current_user["role"] == UserRole.BDM and invoice.get("created_by") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": str(invoice["_id"]),
        "invoice_number": invoice["invoice_number"],
        "company_name": invoice["company_name"],
        "client_name": invoice["client_name"],
        "email": invoice["email"],
        "street_address": invoice["street_address"],
        "city": invoice["city"],
        "gst_pan": invoice["gst_pan"],
        "service_fee": invoice["service_fee"],
        "gst_amount": invoice["gst_amount"],
        "total_amount": invoice["total_amount"],
        "date": invoice["date"],
        "created_by_name": invoice.get("created_by_name", "Unknown")
    }

@router.post("/{invoice_id}/send-email")
async def send_invoice_via_email(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Send invoice to client via email"""
    invoices_collection = get_collection("invoices")
    
    try:
        invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Generate PDF
    pdf_bytes = await generate_pdf(invoice)
    
    # Send email
    success = await send_invoice_email(
        to_email=invoice["email"],
        client_name=invoice["client_name"],
        invoice_number=invoice["invoice_number"],
        total_amount=invoice["total_amount"],
        pdf_attachment=pdf_bytes
    )
    
    if success:
        return {"message": "Invoice sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")
