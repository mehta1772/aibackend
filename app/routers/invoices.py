# """
# Invoices Router
# Handles Performa Invoice generation with PDF download
# """

# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from fastapi.responses import StreamingResponse
# from datetime import datetime
# from bson import ObjectId
# from typing import Optional
# from io import BytesIO
# import os

# from app.models.schemas import InvoiceCreate, UserRole
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user
# from app.utils.email_service import send_invoice_email

# router = APIRouter()

# # Company details for invoice
# COMPANY_NAME = os.getenv("COMPANY_NAME", "Your Company Name")
# COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "123 Business Street, City, State - 123456")
# COMPANY_GST = os.getenv("COMPANY_GST", "GSTIN123456789")
# COMPANY_PAN = os.getenv("COMPANY_PAN", "ABCDE1234F")
# COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "accounts@company.com")
# COMPANY_PHONE = os.getenv("COMPANY_PHONE", "+91 9999999999")
# BANK_NAME = os.getenv("BANK_NAME", "State Bank of India")
# BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "XXXXXXXXXXXX")
# BANK_IFSC = os.getenv("BANK_IFSC", "SBIN0XXXXXX")
# BANK_BRANCH = os.getenv("BANK_BRANCH", "Main Branch")

# def generate_invoice_number():
#     """Generate unique invoice number"""
#     now = datetime.utcnow()
#     return f"PI-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

# def number_to_words(num):
#     """Convert number to words (Indian format)"""
#     ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
#             'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
#             'Seventeen', 'Eighteen', 'Nineteen']
#     tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
    
#     if num == 0:
#         return 'Zero'
#     if num < 0:
#         return 'Negative ' + number_to_words(-num)
#     if num < 20:
#         return ones[int(num)]
#     if num < 100:
#         return tens[int(num) // 10] + ('' if num % 10 == 0 else ' ' + ones[int(num) % 10])
#     if num < 1000:
#         return ones[int(num) // 100] + ' Hundred' + ('' if num % 100 == 0 else ' and ' + number_to_words(num % 100))
#     if num < 100000:
#         return number_to_words(num // 1000) + ' Thousand' + ('' if num % 1000 == 0 else ' ' + number_to_words(num % 1000))
#     if num < 10000000:
#         return number_to_words(num // 100000) + ' Lakh' + ('' if num % 100000 == 0 else ' ' + number_to_words(num % 100000))
#     return number_to_words(num // 10000000) + ' Crore' + ('' if num % 10000000 == 0 else ' ' + number_to_words(num % 10000000))

# def format_inr(amount):
#     """Format amount in Indian Rupee format"""
#     if amount is None:
#         return "Rs. 0.00"
#     return f"Rs. {amount:,.2f}"

# async def generate_pdf(invoice_data: dict) -> bytes:
#     """Generate professional single-page Proforma Invoice PDF"""
#     try:
#         from reportlab.lib import colors
#         from reportlab.lib.pagesizes import A4
#         from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
#         from reportlab.lib.units import mm
#         from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
#         from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
#         from reportlab.pdfbase import pdfmetrics
#         from reportlab.pdfbase.ttfonts import TTFont
#     except ImportError:
#         return f"Invoice #{invoice_data['invoice_number']}\nTotal: Rs. {invoice_data['total_amount']}".encode()
    
#     buffer = BytesIO()
    
#     # Create document with minimal margins for single page
#     def add_pdf_metadata(canvas, doc):
#         canvas.setAuthor(COMPANY_NAME)
#         canvas.setTitle(f"Invoice {invoice_data['invoice_number']}")
#         canvas.setSubject("Proforma Invoice")
#         canvas.setCreator(COMPANY_NAME)

#     doc = SimpleDocTemplate(
#         buffer, 
#         pagesize=A4, 
#         rightMargin=25*mm, 
#         leftMargin=25*mm, 
#         topMargin=15*mm, 
#         bottomMargin=15*mm
#     )
    
#     elements = []
#     styles = getSampleStyleSheet()
#     width = A4[0] - 50*mm  # Available width
    
#     # Colors
#     primary = colors.HexColor('#1a365d')  # Dark blue
#     accent = colors.HexColor('#2563eb')   # Blue
#     light_bg = colors.HexColor('#f8fafc')
#     border_color = colors.HexColor('#e2e8f0')
    
#     # Styles
#     title_style = ParagraphStyle('Title', fontSize=18, fontName='Helvetica-Bold', textColor=primary, alignment=TA_CENTER)
#     heading_style = ParagraphStyle('Heading', fontSize=9, fontName='Helvetica-Bold', textColor=primary)
#     normal_style = ParagraphStyle('Normal', fontSize=9, fontName='Helvetica', textColor=colors.black, leading=12)
#     small_style = ParagraphStyle('Small', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#64748b'), leading=10)
#     right_style = ParagraphStyle('Right', fontSize=9, fontName='Helvetica', textColor=colors.black, alignment=TA_RIGHT)
#     center_style = ParagraphStyle('Center', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#64748b'), alignment=TA_CENTER)
    
#     # Parse date
#     invoice_date = invoice_data.get('date', datetime.utcnow())
#     if isinstance(invoice_date, str):
#         try:
#             invoice_date = datetime.fromisoformat(invoice_date.replace('Z', '+00:00'))
#         except:
#             invoice_date = datetime.utcnow()
    
#     # ===== HEADER =====
#     elements.append(Paragraph("PROFORMA INVOICE", title_style))
#     elements.append(Spacer(1, 10*mm))
    
#     # Company and Invoice Info side by side
#     header_data = [
#         [
#             # Left: Company Info
#             Paragraph(f"<b>{COMPANY_NAME}</b><br/>"
#                      f"<font size='8'>{COMPANY_ADDRESS}<br/>"
#                      f"GSTIN: {COMPANY_GST} | PAN: {COMPANY_PAN}<br/>"
#                      f"Email: {COMPANY_EMAIL} | Phone: {COMPANY_PHONE}</font>", normal_style),
#             # Right: Invoice Details
#             Paragraph(f"<b>Invoice No:</b> {invoice_data['invoice_number']}<br/>"
#                      f"<b>Date:</b> {invoice_date.strftime('%d %b %Y')}<br/>"
#                      f"<b>Due Date:</b> On Receipt", right_style)
#         ]
#     ]
#     header_table = Table(header_data, colWidths=[width*0.65, width*0.35])
#     header_table.setStyle(TableStyle([
#         ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#         ('LEFTPADDING', (0, 0), (-1, -1), 0),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 0),
#     ]))
#     elements.append(header_table)
#     elements.append(Spacer(1, 5*mm))
    
#     # ===== BILL TO =====
#     bill_to_data = [
#         [Paragraph("<b>BILL TO</b>", heading_style)],
#         [Paragraph(f"<b>{invoice_data['company_name']}</b><br/>"
#                   f"{invoice_data['client_name']}<br/>"
#                   f"{invoice_data['street_address']}, {invoice_data['city']}<br/>"
#                   f"GSTIN/PAN: {invoice_data['gst_pan']}<br/>"
#                   f"Email: {invoice_data['email']}", normal_style)]
#     ]
#     bill_table = Table(bill_to_data, colWidths=[width])
#     bill_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, -1), light_bg),
#         ('BOX', (0, 0), (-1, -1), 0.5, border_color),
#         ('LEFTPADDING', (0, 0), (-1, -1), 8),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 8),
#         ('TOPPADDING', (0, 0), (-1, -1), 6),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
#     ]))
#     elements.append(bill_table)
#     elements.append(Spacer(1, 5*mm))
    
#     # ===== ITEMS TABLE =====
#     service_fee = invoice_data.get('service_fee', 0)
#     gst_amount = invoice_data.get('gst_amount', 0)
#     total_amount = invoice_data.get('total_amount', 0)
#     cgst = gst_amount / 2
#     sgst = gst_amount / 2
    
#     items_data = [
#         ['S.No', 'Description', 'HSN/SAC', 'Qty', 'Rate', 'Amount'],
#         ['1', 'Professional Services / Consulting Fee', '998311', '1', format_inr(service_fee), format_inr(service_fee)],
#         ['', '', '', '', '', ''],
#         ['', '', '', '', Paragraph('<b>Subtotal</b>', right_style), format_inr(service_fee)],
#         ['', '', '', '', Paragraph('<b>CGST (9%)</b>', right_style), format_inr(cgst)],
#         ['', '', '', '', Paragraph('<b>SGST (9%)</b>', right_style), format_inr(sgst)],
#     ]
    
#     col_widths = [25, width*0.40, 50, 30, 70, 70]
#     items_table = Table(items_data, colWidths=col_widths)
#     items_table.setStyle(TableStyle([
#         # Header
#         ('BACKGROUND', (0, 0), (-1, 0), primary),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('FONTSIZE', (0, 0), (-1, 0), 9),
#         ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
#         # Body
#         ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
#         ('FONTSIZE', (0, 1), (-1, -1), 9),
#         ('ALIGN', (0, 1), (0, -1), 'CENTER'),
#         ('ALIGN', (2, 1), (3, -1), 'CENTER'),
#         ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        
#         # Padding
#         ('TOPPADDING', (0, 0), (-1, -1), 6),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
#         ('LEFTPADDING', (0, 0), (-1, -1), 4),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        
#         # Grid
#         ('GRID', (0, 0), (-1, 1), 0.5, border_color),
#         ('LINEBELOW', (4, 2), (-1, -1), 0.5, border_color),
        
#         # Box
#         ('BOX', (0, 0), (-1, -1), 1, primary),
#     ]))
#     elements.append(items_table)
    
#     # ===== TOTAL BOX =====
#     total_data = [
#         [Paragraph(f"<b>GRAND TOTAL</b>", ParagraphStyle('', fontSize=11, fontName='Helvetica-Bold', textColor=colors.white)),
#          Paragraph(f"<b>{format_inr(total_amount)}</b>", ParagraphStyle('', fontSize=11, fontName='Helvetica-Bold', textColor=colors.white, alignment=TA_RIGHT))]
#     ]
#     total_table = Table(total_data, colWidths=[width*0.7, width*0.3])
#     total_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, -1), accent),
#         ('TOPPADDING', (0, 0), (-1, -1), 8),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
#         ('LEFTPADDING', (0, 0), (-1, -1), 10),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 10),
#     ]))
#     elements.append(total_table)
#     elements.append(Spacer(1, 3*mm))
    
#     # ===== AMOUNT IN WORDS =====
#     rupees = int(total_amount)
#     paise = int((total_amount - rupees) * 100)
#     words = f"Rupees {number_to_words(rupees)}"
#     if paise > 0:
#         words += f" and {number_to_words(paise)} Paise"
#     words += " Only"
    
#     words_data = [[Paragraph(f"<b>Amount in Words:</b> {words}", normal_style)]]
#     words_table = Table(words_data, colWidths=[width])
#     words_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, -1), light_bg),
#         ('BOX', (0, 0), (-1, -1), 0.5, border_color),
#         ('TOPPADDING', (0, 0), (-1, -1), 5),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
#         ('LEFTPADDING', (0, 0), (-1, -1), 8),
#     ]))
#     elements.append(words_table)
#     elements.append(Spacer(1, 5*mm))
    
#     # ===== BANK DETAILS & TERMS =====
#     bank_terms_data = [
#         [
#             Paragraph(f"<b>BANK DETAILS</b><br/><br/>"
#                      f"Bank: {BANK_NAME}<br/>"
#                      f"A/C No: {BANK_ACCOUNT}<br/>"
#                      f"IFSC: {BANK_IFSC}<br/>"
#                      f"Branch: {BANK_BRANCH}", normal_style),
#             Paragraph(f"<b>TERMS & CONDITIONS</b><br/><br/>"
#                      f"1. Payment due upon receipt.<br/>"
#                      f"2. Quote invoice number when remitting.<br/>"
#                      f"3. This is a Proforma Invoice.", normal_style),
#             Paragraph(f"<b>For {COMPANY_NAME}</b><br/><br/><br/><br/>"
#                      f"________________________<br/>"
#                      f"Authorized Signatory", ParagraphStyle('', fontSize=9, fontName='Helvetica', alignment=TA_CENTER))
#         ]
#     ]
#     bank_table = Table(bank_terms_data, colWidths=[width*0.35, width*0.35, width*0.30])
#     bank_table.setStyle(TableStyle([
#         ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#         ('BOX', (0, 0), (-1, -1), 0.5, border_color),
#         ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
#         ('TOPPADDING', (0, 0), (-1, -1), 8),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
#         ('LEFTPADDING', (0, 0), (-1, -1), 8),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 8),
#     ]))
#     elements.append(bank_table)
#     elements.append(Spacer(1, 5*mm))
    
#     # ===== FOOTER =====
#     elements.append(Paragraph("This is a computer-generated Proforma Invoice.", center_style))
#     elements.append(Paragraph(f"Thank you for your business!", center_style))
    
#     doc.build(elements, onFirstPage=add_pdf_metadata)
#     buffer.seek(0)
#     return buffer.getvalue()

# @router.post("/create")
# async def create_invoice(
#     invoice_data: InvoiceCreate,
#     current_user: dict = Depends(get_current_user)
# ):
#     """Create new Performa Invoice"""
#     invoices_collection = get_collection("invoices")
    
#     invoice_number = generate_invoice_number()
#     total_amount = invoice_data.service_fee + invoice_data.gst_amount
    
#     invoice = {
#         "invoice_number": invoice_number,
#         "company_name": invoice_data.company_name,
#         "client_name": invoice_data.client_name,
#         "email": invoice_data.email,
#         "street_address": invoice_data.street_address,
#         "city": invoice_data.city,
#         "gst_pan": invoice_data.gst_pan,
#         "service_fee": invoice_data.service_fee,
#         "gst_amount": invoice_data.gst_amount,
#         "total_amount": total_amount,
#         "date": datetime.utcnow(),
#         "created_by": current_user["id"],
#         "created_by_name": current_user["name"],
#         "created_at": datetime.utcnow()
#     }
    
#     result = await invoices_collection.insert_one(invoice)
    
#     return {
#         "id": str(result.inserted_id),
#         "invoice_number": invoice_number,
#         "total_amount": total_amount,
#         "message": "Invoice created successfully",
#         "pdf_ready": True
#     }

# @router.get("/{invoice_id}/download")
# async def download_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
#     """Download invoice as PDF"""
#     invoices_collection = get_collection("invoices")
    
#     try:
#         invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
#     if not invoice:
#         raise HTTPException(status_code=404, detail="Invoice not found")
    
#     pdf_bytes = await generate_pdf(invoice)
    
#     return StreamingResponse(
#         BytesIO(pdf_bytes),
#         media_type="application/pdf",
#         headers={
#             "Content-Disposition": f"attachment; filename=Invoice_{invoice['invoice_number']}.pdf"
#         }
#     )

# @router.get("/")
# async def get_all_invoices(
#     search: Optional[str] = Query(None),
#     start_date: Optional[datetime] = Query(None),
#     end_date: Optional[datetime] = Query(None),
#     page: int = Query(1, ge=1),
#     page_size: int = Query(20, ge=1, le=100),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get all invoices"""
#     invoices_collection = get_collection("invoices")
    
#     query = {}
    
#     if current_user["role"] == UserRole.BDM:
#         query["created_by"] = current_user["id"]
    
#     if search:
#         query["$or"] = [
#             {"company_name": {"$regex": search, "$options": "i"}},
#             {"client_name": {"$regex": search, "$options": "i"}},
#             {"invoice_number": {"$regex": search, "$options": "i"}}
#         ]
    
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     total = await invoices_collection.count_documents(query)
    
#     skip = (page - 1) * page_size
#     cursor = invoices_collection.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    
#     invoices = []
#     async for invoice in cursor:
#         invoices.append({
#             "id": str(invoice["_id"]),
#             "invoice_number": invoice["invoice_number"],
#             "company_name": invoice["company_name"],
#             "client_name": invoice["client_name"],
#             "email": invoice["email"],
#             "total_amount": invoice["total_amount"],
#             "date": invoice["date"],
#             "created_by_name": invoice.get("created_by_name", "Unknown")
#         })
    
#     return {
#         "items": invoices,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
#     }

# @router.get("/{invoice_id}")
# async def get_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
#     """Get single invoice details"""
#     invoices_collection = get_collection("invoices")
    
#     try:
#         invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
#     if not invoice:
#         raise HTTPException(status_code=404, detail="Invoice not found")
    
#     if current_user["role"] == UserRole.BDM and invoice.get("created_by") != current_user["id"]:
#         raise HTTPException(status_code=403, detail="Access denied")
    
#     return {
#         "id": str(invoice["_id"]),
#         "invoice_number": invoice["invoice_number"],
#         "company_name": invoice["company_name"],
#         "client_name": invoice["client_name"],
#         "email": invoice["email"],
#         "street_address": invoice["street_address"],
#         "city": invoice["city"],
#         "gst_pan": invoice["gst_pan"],
#         "service_fee": invoice["service_fee"],
#         "gst_amount": invoice["gst_amount"],
#         "total_amount": invoice["total_amount"],
#         "date": invoice["date"],
#         "created_by_name": invoice.get("created_by_name", "Unknown")
#     }

# @router.post("/{invoice_id}/send-email")
# async def send_invoice_via_email(invoice_id: str, current_user: dict = Depends(get_current_user)):
#     """Send invoice to client via email"""
#     invoices_collection = get_collection("invoices")
    
#     try:
#         invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
#     if not invoice:
#         raise HTTPException(status_code=404, detail="Invoice not found")
    
#     pdf_bytes = await generate_pdf(invoice)
    
#     success = await send_invoice_email(
#         to_email=invoice["email"],
#         client_name=invoice["client_name"],
#         invoice_number=invoice["invoice_number"],
#         total_amount=invoice["total_amount"],
#         pdf_attachment=pdf_bytes
#     )
    
#     if success:
#         return {"message": "Invoice sent successfully"}
#     else:
#         raise HTTPException(status_code=500, detail="Failed to send email")










# """
# Invoices Router
# Handles Performa Invoice generation with PDF download
# """

# from tkinter import Image
# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from fastapi.responses import StreamingResponse
# from datetime import datetime
# from bson import ObjectId
# from typing import Optional
# from io import BytesIO
# import os

# from app.models.schemas import InvoiceCreate, UserRole
# from app.utils.database import get_collection
# from app.utils.auth import get_current_user
# from app.utils.email_service import send_invoice_email

# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# STAMP_PATH = os.path.join(BASE_DIR, "assets", "stamp.png")


# router = APIRouter()

# # Company details for invoice
# COMPANY_NAME = os.getenv("COMPANY_NAME", "Your Company Name")
# COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "123 Business Street, City, State - 123456")
# COMPANY_GST = os.getenv("COMPANY_GST", "GSTIN123456789")
# COMPANY_PAN = os.getenv("COMPANY_PAN", "ABCDE1234F")
# COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "accounts@company.com")
# COMPANY_PHONE = os.getenv("COMPANY_PHONE", "+91 9999999999")
# BANK_NAME = os.getenv("BANK_NAME", "State Bank of India")
# BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "XXXXXXXXXXXX")
# BANK_IFSC = os.getenv("BANK_IFSC", "SBIN0XXXXXX")
# BANK_BRANCH = os.getenv("BANK_BRANCH", "Main Branch")

# def generate_invoice_number():
#     """Generate unique invoice number"""
#     now = datetime.utcnow()
#     return f"PI-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

# def number_to_words(num):
#     """Convert number to words (Indian format)"""
#     ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
#             'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
#             'Seventeen', 'Eighteen', 'Nineteen']
#     tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
    
#     if num == 0:
#         return 'Zero'
#     if num < 0:
#         return 'Negative ' + number_to_words(-num)
#     if num < 20:
#         return ones[int(num)]
#     if num < 100:
#         return tens[int(num) // 10] + ('' if num % 10 == 0 else ' ' + ones[int(num) % 10])
#     if num < 1000:
#         return ones[int(num) // 100] + ' Hundred' + ('' if num % 100 == 0 else ' and ' + number_to_words(num % 100))
#     if num < 100000:
#         return number_to_words(num // 1000) + ' Thousand' + ('' if num % 1000 == 0 else ' ' + number_to_words(num % 1000))
#     if num < 10000000:
#         return number_to_words(num // 100000) + ' Lakh' + ('' if num % 100000 == 0 else ' ' + number_to_words(num % 100000))
#     return number_to_words(num // 10000000) + ' Crore' + ('' if num % 10000000 == 0 else ' ' + number_to_words(num % 10000000))

# def format_inr(amount):
#     """Format amount in Indian Rupee format"""
#     if amount is None:
#         return "Rs. 0.00"
#     return f"Rs. {amount:,.2f}"

# async def generate_pdf(invoice_data: dict) -> bytes:
#     """Generate professional single-page Proforma Invoice PDF"""
#     try:
#         from reportlab.lib import colors
#         from reportlab.lib.pagesizes import A4
#         from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
#         from reportlab.lib.units import mm
#         from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
#         from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
#         from reportlab.pdfbase import pdfmetrics
#         from reportlab.pdfbase.ttfonts import TTFont
#     except ImportError:
#         return f"Invoice #{invoice_data['invoice_number']}\nTotal: Rs. {invoice_data['total_amount']}".encode()
    
#     buffer = BytesIO()
    
#     # Create document with minimal margins for single page
#     def add_pdf_metadata(canvas, doc):
#         canvas.setAuthor(COMPANY_NAME)
#         canvas.setTitle(f"Invoice {invoice_data['invoice_number']}")
#         canvas.setSubject("Proforma Invoice")
#         canvas.setCreator(COMPANY_NAME)

#     doc = SimpleDocTemplate(
#         buffer, 
#         pagesize=A4, 
#         rightMargin=25*mm, 
#         leftMargin=25*mm, 
#         topMargin=15*mm, 
#         bottomMargin=15*mm
#     )
    
#     elements = []
#     styles = getSampleStyleSheet()
#     width = A4[0] - 50*mm  # Available width
    
#     # Colors
#     primary = colors.HexColor('#1a365d')  # Dark blue
#     accent = colors.HexColor('#2563eb')   # Blue
#     light_bg = colors.HexColor('#f8fafc')
#     border_color = colors.HexColor('#e2e8f0')
    
#     # Styles
#     title_style = ParagraphStyle('Title', fontSize=18, fontName='Helvetica-Bold', textColor=primary, alignment=TA_CENTER)
#     heading_style = ParagraphStyle('Heading', fontSize=9, fontName='Helvetica-Bold', textColor=primary)
#     normal_style = ParagraphStyle('Normal', fontSize=9, fontName='Helvetica', textColor=colors.black, leading=12)
#     small_style = ParagraphStyle('Small', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#64748b'), leading=10)
#     right_style = ParagraphStyle('Right', fontSize=9, fontName='Helvetica', textColor=colors.black, alignment=TA_RIGHT)
#     center_style = ParagraphStyle('Center', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#64748b'), alignment=TA_CENTER)
    
#     # Parse date
#     invoice_date = invoice_data.get('date', datetime.utcnow())
#     if isinstance(invoice_date, str):
#         try:
#             invoice_date = datetime.fromisoformat(invoice_date.replace('Z', '+00:00'))
#         except:
#             invoice_date = datetime.utcnow()
    
#     # ===== HEADER =====
#     elements.append(Paragraph("PROFORMA INVOICE", title_style))
#     elements.append(Spacer(1, 10*mm))
    
#     # Company and Invoice Info side by side
#     header_data = [
#         [
#             # Left: Company Info
#             Paragraph(f"<b>{COMPANY_NAME}</b><br/>"
#                      f"<font size='8'>{COMPANY_ADDRESS}<br/>"
#                      f"GSTIN: {COMPANY_GST} | PAN: {COMPANY_PAN}<br/>"
#                      f"Email: {COMPANY_EMAIL} | Phone: {COMPANY_PHONE}</font>", normal_style),
#             # Right: Invoice Details
#             Paragraph(f"<b>Invoice No:</b> {invoice_data['invoice_number']}<br/>"
#                      f"<b>Date:</b> {invoice_date.strftime('%d %b %Y')}<br/>"
#                      f"<b>Due Date:</b> On Receipt", right_style)
#         ]
#     ]
#     header_table = Table(header_data, colWidths=[width*0.65, width*0.35])
#     header_table.setStyle(TableStyle([
#         ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#         ('LEFTPADDING', (0, 0), (-1, -1), 0),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 0),
#     ]))
#     elements.append(header_table)
#     elements.append(Spacer(1, 5*mm))
    
#     # ===== BILL TO =====
#     bill_to_data = [
#         [Paragraph("<b>BILL TO</b>", heading_style)],
#         [Paragraph(f"<b>{invoice_data['company_name']}</b><br/>"
#                   f"{invoice_data['client_name']}<br/>"
#                   f"{invoice_data['street_address']}, {invoice_data['city']}<br/>"
#                   f"GSTIN/PAN: {invoice_data['gst_pan']}<br/>"
#                   f"Email: {invoice_data['email']}", normal_style)]
#     ]
#     bill_table = Table(bill_to_data, colWidths=[width])
#     bill_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, -1), light_bg),
#         ('BOX', (0, 0), (-1, -1), 0.5, border_color),
#         ('LEFTPADDING', (0, 0), (-1, -1), 8),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 8),
#         ('TOPPADDING', (0, 0), (-1, -1), 6),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
#     ]))
#     elements.append(bill_table)
#     elements.append(Spacer(1, 5*mm))
    
#     # ===== ITEMS TABLE =====
#     service_fee = invoice_data.get('service_fee', 0)
#     gst_amount = invoice_data.get('gst_amount', 0)
#     total_amount = invoice_data.get('total_amount', 0)
#     cgst = gst_amount / 2
#     sgst = gst_amount / 2
    
#     items_data = [
#         ['S.No', 'Description', 'HSN/SAC', 'Qty', 'Rate', 'Amount'],
#         ['1', 'Professional Services / Consulting Fee', '998311', '1', format_inr(service_fee), format_inr(service_fee)],
#         ['', '', '', '', '', ''],
#         ['', '', '', '', Paragraph('<b>Subtotal</b>', right_style), format_inr(service_fee)],
#         ['', '', '', '', Paragraph('<b>CGST (9%)</b>', right_style), format_inr(cgst)],
#         ['', '', '', '', Paragraph('<b>SGST (9%)</b>', right_style), format_inr(sgst)],
#     ]
    
#     col_widths = [25, width*0.40, 50, 30, 70, 70]
#     items_table = Table(items_data, colWidths=col_widths)
#     items_table.setStyle(TableStyle([
#         # Header
#         ('BACKGROUND', (0, 0), (-1, 0), primary),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('FONTSIZE', (0, 0), (-1, 0), 9),
#         ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
#         # Body
#         ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
#         ('FONTSIZE', (0, 1), (-1, -1), 9),
#         ('ALIGN', (0, 1), (0, -1), 'CENTER'),
#         ('ALIGN', (2, 1), (3, -1), 'CENTER'),
#         ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        
#         # Padding
#         ('TOPPADDING', (0, 0), (-1, -1), 6),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
#         ('LEFTPADDING', (0, 0), (-1, -1), 4),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        
#         # Grid
#         ('GRID', (0, 0), (-1, 1), 0.5, border_color),
#         ('LINEBELOW', (4, 2), (-1, -1), 0.5, border_color),
        
#         # Box
#         ('BOX', (0, 0), (-1, -1), 1, primary),
#     ]))
#     elements.append(items_table)
    
#     # ===== TOTAL BOX =====
#     total_data = [
#         [Paragraph(f"<b>GRAND TOTAL</b>", ParagraphStyle('', fontSize=11, fontName='Helvetica-Bold', textColor=colors.white)),
#          Paragraph(f"<b>{format_inr(total_amount)}</b>", ParagraphStyle('', fontSize=11, fontName='Helvetica-Bold', textColor=colors.white, alignment=TA_RIGHT))]
#     ]
#     total_table = Table(total_data, colWidths=[width*0.7, width*0.3])
#     total_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, -1), accent),
#         ('TOPPADDING', (0, 0), (-1, -1), 8),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
#         ('LEFTPADDING', (0, 0), (-1, -1), 10),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 10),
#     ]))
#     elements.append(total_table)
#     elements.append(Spacer(1, 3*mm))
    
#     # ===== AMOUNT IN WORDS =====
#     rupees = int(total_amount)
#     paise = int((total_amount - rupees) * 100)
#     words = f"Rupees {number_to_words(rupees)}"
#     if paise > 0:
#         words += f" and {number_to_words(paise)} Paise"
#     words += " Only"
    
#     words_data = [[Paragraph(f"<b>Amount in Words:</b> {words}", normal_style)]]
#     words_table = Table(words_data, colWidths=[width])
#     words_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, -1), light_bg),
#         ('BOX', (0, 0), (-1, -1), 0.5, border_color),
#         ('TOPPADDING', (0, 0), (-1, -1), 5),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
#         ('LEFTPADDING', (0, 0), (-1, -1), 8),
#     ]))
#     elements.append(words_table)
#     elements.append(Spacer(1, 5*mm))
    

#     stamp_img = None
#     if os.path.exists(STAMP_PATH):
#         stamp_img = Image(
#             STAMP_PATH,
#             width=45 * mm,   # adjust if needed
#             height=45 * mm,
#             kind='proportional'
#         )

#     # ===== BANK DETAILS & TERMS =====
#     bank_terms_data = [
#         [
#             Paragraph(f"<b>BANK DETAILS</b><br/><br/>"
#                      f"Bank: {BANK_NAME}<br/>"
#                      f"A/C No: {BANK_ACCOUNT}<br/>"
#                      f"IFSC: {BANK_IFSC}<br/>"
#                      f"Branch: {BANK_BRANCH}", normal_style),
#             Paragraph(f"<b>TERMS & CONDITIONS</b><br/><br/>"
#                      f"1. Payment due upon receipt.<br/>"
#                      f"2. Quote invoice number when remitting.<br/>"
#                      f"3. This is a Proforma Invoice.", normal_style),
#            [
#             Paragraph(f"<b>For {COMPANY_NAME}</b>", ParagraphStyle(
#                 '', fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER
#             )),
#             Spacer(1, 5 * mm),
#             stamp_img if stamp_img else Spacer(1, 40),
#             Spacer(1, 3 * mm),
#             Paragraph("________________________", ParagraphStyle(
#                 '', fontSize=9, alignment=TA_CENTER
#             )),
#             Paragraph("Authorized Signatory", ParagraphStyle(
#                 '', fontSize=9, alignment=TA_CENTER
#             ))
#         ]
#         ]
#     ]
#     bank_table = Table(bank_terms_data, colWidths=[width*0.35, width*0.35, width*0.30])
#     bank_table.setStyle(TableStyle([
#         ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#         ('BOX', (0, 0), (-1, -1), 0.5, border_color),
#         ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
#         ('TOPPADDING', (0, 0), (-1, -1), 8),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
#         ('LEFTPADDING', (0, 0), (-1, -1), 8),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 8),
#     ]))
#     elements.append(bank_table)
#     elements.append(Spacer(1, 5*mm))
    
#     # ===== FOOTER =====
#     elements.append(Paragraph("This is a computer-generated Proforma Invoice.", center_style))
#     elements.append(Paragraph(f"Thank you for your business!", center_style))
    
#     doc.build(elements, onFirstPage=add_pdf_metadata)
#     buffer.seek(0)
#     return buffer.getvalue()

# @router.post("/create")
# async def create_invoice(
#     invoice_data: InvoiceCreate,
#     current_user: dict = Depends(get_current_user)
# ):
#     """Create new Performa Invoice"""
#     invoices_collection = get_collection("invoices")
    
#     invoice_number = generate_invoice_number()
#     total_amount = invoice_data.service_fee + invoice_data.gst_amount
    
#     invoice = {
#         "invoice_number": invoice_number,
#         "company_name": invoice_data.company_name,
#         "client_name": invoice_data.client_name,
#         "email": invoice_data.email,
#         "street_address": invoice_data.street_address,
#         "city": invoice_data.city,
#         "gst_pan": invoice_data.gst_pan,
#         "service_fee": invoice_data.service_fee,
#         "gst_amount": invoice_data.gst_amount,
#         "total_amount": total_amount,
#         "date": datetime.utcnow(),
#         "created_by": current_user["id"],
#         "created_by_name": current_user["name"],
#         "created_at": datetime.utcnow()
#     }
    
#     result = await invoices_collection.insert_one(invoice)
    
#     return {
#         "id": str(result.inserted_id),
#         "invoice_number": invoice_number,
#         "total_amount": total_amount,
#         "message": "Invoice created successfully",
#         "pdf_ready": True
#     }

# @router.get("/{invoice_id}/download")
# async def download_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
#     """Download invoice as PDF"""
#     invoices_collection = get_collection("invoices")
    
#     try:
#         invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
#     if not invoice:
#         raise HTTPException(status_code=404, detail="Invoice not found")
    
#     pdf_bytes = await generate_pdf(invoice)
    
#     return StreamingResponse(
#         BytesIO(pdf_bytes),
#         media_type="application/pdf",
#         headers={
#             "Content-Disposition": f"attachment; filename=Invoice_{invoice['invoice_number']}.pdf"
#         }
#     )

# @router.get("/")
# async def get_all_invoices(
#     search: Optional[str] = Query(None),
#     start_date: Optional[datetime] = Query(None),
#     end_date: Optional[datetime] = Query(None),
#     page: int = Query(1, ge=1),
#     page_size: int = Query(20, ge=1, le=100),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Get all invoices"""
#     invoices_collection = get_collection("invoices")
    
#     query = {}
    
#     if current_user["role"] == UserRole.BDM:
#         query["created_by"] = current_user["id"]
    
#     if search:
#         query["$or"] = [
#             {"company_name": {"$regex": search, "$options": "i"}},
#             {"client_name": {"$regex": search, "$options": "i"}},
#             {"invoice_number": {"$regex": search, "$options": "i"}}
#         ]
    
#     if start_date or end_date:
#         query["date"] = {}
#         if start_date:
#             query["date"]["$gte"] = start_date
#         if end_date:
#             query["date"]["$lte"] = end_date
    
#     total = await invoices_collection.count_documents(query)
    
#     skip = (page - 1) * page_size
#     cursor = invoices_collection.find(query).skip(skip).limit(page_size).sort("created_at", -1)
    
#     invoices = []
#     async for invoice in cursor:
#         invoices.append({
#             "id": str(invoice["_id"]),
#             "invoice_number": invoice["invoice_number"],
#             "company_name": invoice["company_name"],
#             "client_name": invoice["client_name"],
#             "email": invoice["email"],
#             "total_amount": invoice["total_amount"],
#             "date": invoice["date"],
#             "created_by_name": invoice.get("created_by_name", "Unknown")
#         })
    
#     return {
#         "items": invoices,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": (total + page_size - 1) // page_size
#     }

# @router.get("/{invoice_id}")
# async def get_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
#     """Get single invoice details"""
#     invoices_collection = get_collection("invoices")
    
#     try:
#         invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
#     if not invoice:
#         raise HTTPException(status_code=404, detail="Invoice not found")
    
#     if current_user["role"] == UserRole.BDM and invoice.get("created_by") != current_user["id"]:
#         raise HTTPException(status_code=403, detail="Access denied")
    
#     return {
#         "id": str(invoice["_id"]),
#         "invoice_number": invoice["invoice_number"],
#         "company_name": invoice["company_name"],
#         "client_name": invoice["client_name"],
#         "email": invoice["email"],
#         "street_address": invoice["street_address"],
#         "city": invoice["city"],
#         "gst_pan": invoice["gst_pan"],
#         "service_fee": invoice["service_fee"],
#         "gst_amount": invoice["gst_amount"],
#         "total_amount": invoice["total_amount"],
#         "date": invoice["date"],
#         "created_by_name": invoice.get("created_by_name", "Unknown")
#     }

# @router.post("/{invoice_id}/send-email")
# async def send_invoice_via_email(invoice_id: str, current_user: dict = Depends(get_current_user)):
#     """Send invoice to client via email"""
#     invoices_collection = get_collection("invoices")
    
#     try:
#         invoice = await invoices_collection.find_one({"_id": ObjectId(invoice_id)})
#     except:
#         raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
#     if not invoice:
#         raise HTTPException(status_code=404, detail="Invoice not found")
    
#     pdf_bytes = await generate_pdf(invoice)
    
#     success = await send_invoice_email(
#         to_email=invoice["email"],
#         client_name=invoice["client_name"],
#         invoice_number=invoice["invoice_number"],
#         total_amount=invoice["total_amount"],
#         pdf_attachment=pdf_bytes
#     )
    
#     if success:
#         return {"message": "Invoice sent successfully"}
#     else:
#         raise HTTPException(status_code=500, detail="Failed to send email")





"""
Invoices Router
Handles Performa Invoice generation with PDF download
"""

# from tkinter import Image
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP_PATH = os.path.join(BASE_DIR, "assets", "stamp.png")


router = APIRouter()

# Company details for invoice
COMPANY_NAME = os.getenv("COMPANY_NAME", "Your Company Name")
COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "123 Business Street, City, State - 123456")
COMPANY_GST = os.getenv("COMPANY_GST", "GSTIN123456789")
COMPANY_PAN = os.getenv("COMPANY_PAN", "ABCDE1234F")
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "accounts@company.com")
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "+91 9511428816")
BANK_NAME = os.getenv("BANK_NAME", "HDFC Bank")
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "50200102049496")
BANK_IFSC = os.getenv("BANK_IFSC", "HDFC0000975")
BANK_BRANCH = os.getenv("BANK_BRANCH", "NOIDA SECTOR 63")

def generate_invoice_number():
    """Generate unique invoice number"""
    now = datetime.utcnow()
    return f"PI-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

def number_to_words(num):
    """Convert number to words (Indian format)"""
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
            'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
            'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
    
    if num == 0:
        return 'Zero'
    if num < 0:
        return 'Negative ' + number_to_words(-num)
    if num < 20:
        return ones[int(num)]
    if num < 100:
        return tens[int(num) // 10] + ('' if num % 10 == 0 else ' ' + ones[int(num) % 10])
    if num < 1000:
        return ones[int(num) // 100] + ' Hundred' + ('' if num % 100 == 0 else ' and ' + number_to_words(num % 100))
    if num < 100000:
        return number_to_words(num // 1000) + ' Thousand' + ('' if num % 1000 == 0 else ' ' + number_to_words(num % 1000))
    if num < 10000000:
        return number_to_words(num // 100000) + ' Lakh' + ('' if num % 100000 == 0 else ' ' + number_to_words(num % 100000))
    return number_to_words(num // 10000000) + ' Crore' + ('' if num % 10000000 == 0 else ' ' + number_to_words(num % 10000000))

def format_inr(amount):
    """Format amount in Indian Rupee format"""
    if amount is None:
        return "Rs. 0.00"
    return f"Rs. {amount:,.2f}"

async def generate_pdf(invoice_data: dict) -> bytes:
    """Generate professional single-page Proforma Invoice PDF"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return f"Invoice #{invoice_data['invoice_number']}\nTotal: Rs. {invoice_data['total_amount']}".encode()
    
    buffer = BytesIO()
    
    # Create document with minimal margins for single page
    def add_pdf_metadata(canvas, doc):
        canvas.setAuthor(COMPANY_NAME)
        canvas.setTitle(f"Invoice {invoice_data['invoice_number']}")
        canvas.setSubject("Proforma Invoice")
        canvas.setCreator(COMPANY_NAME)

    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=25*mm, 
        leftMargin=25*mm, 
        topMargin=15*mm, 
        bottomMargin=15*mm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    width = A4[0] - 50*mm  # Available width
    
    # Colors
    primary = colors.HexColor('#1a365d')  # Dark blue
    accent = colors.HexColor('#2563eb')   # Blue
    light_bg = colors.HexColor('#f8fafc')
    border_color = colors.HexColor('#e2e8f0')
    
    # Styles
    title_style = ParagraphStyle('Title', fontSize=18, fontName='Helvetica-Bold', textColor=primary, alignment=TA_CENTER)
    heading_style = ParagraphStyle('Heading', fontSize=9, fontName='Helvetica-Bold', textColor=primary)
    normal_style = ParagraphStyle('Normal', fontSize=9, fontName='Helvetica', textColor=colors.black, leading=12)
    small_style = ParagraphStyle('Small', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#64748b'), leading=10)
    right_style = ParagraphStyle('Right', fontSize=9, fontName='Helvetica', textColor=colors.black, alignment=TA_RIGHT)
    center_style = ParagraphStyle('Center', fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#64748b'), alignment=TA_CENTER)
    
    # Parse date
    invoice_date = invoice_data.get('date', datetime.utcnow())
    if isinstance(invoice_date, str):
        try:
            invoice_date = datetime.fromisoformat(invoice_date.replace('Z', '+00:00'))
        except:
            invoice_date = datetime.utcnow()
    
    # ===== HEADER =====
    elements.append(Paragraph("PROFORMA INVOICE", title_style))
    elements.append(Spacer(1, 10*mm))
    
    # Company and Invoice Info side by side
    header_data = [
        [
            # Left: Company Info
            Paragraph(f"<b>{COMPANY_NAME}</b><br/>"
                     f"<font size='8'>{COMPANY_ADDRESS}<br/>"
                     f"Email: {COMPANY_EMAIL} | Phone: {COMPANY_PHONE}</font>", normal_style),
            # Right: Invoice Details
            Paragraph(f"<b>Invoice No:</b> {invoice_data['invoice_number']}<br/>"
                     f"<b>Date:</b> {invoice_date.strftime('%d %b %Y')}<br/>"
                     f"<b>Due Date:</b> On Receipt", right_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[width*0.65, width*0.35])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 5*mm))
    
    # ===== BILL TO =====
    bill_to_data = [
        [Paragraph("<b>BILL TO</b>", heading_style)],
        [Paragraph(f"<b>{invoice_data['company_name']}</b><br/>"
                  f"{invoice_data['client_name']}<br/>"
                  f"{invoice_data['street_address']}, {invoice_data['city']}<br/>"
                  f"GSTIN/PAN: {invoice_data['gst_pan']}<br/>"
                  f"Email: {invoice_data['email']}", normal_style)]
    ]
    bill_table = Table(bill_to_data, colWidths=[width])
    bill_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, border_color),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(bill_table)
    elements.append(Spacer(1, 5*mm))
    
    # ===== ITEMS TABLE =====
    service_fee = invoice_data.get('service_fee', 0)
    gst_amount = invoice_data.get('gst_amount', 0)
    total_amount = invoice_data.get('total_amount', 0)
    cgst = gst_amount / 2
    sgst = gst_amount / 2
    
    items_data = [
    ['S.No', 'Description', 'HSN/SAC', 'Qty', 'Rate', 'Amount'],
    ['1', 'Professional Services / Consulting Fee', '998311', '1',
     format_inr(service_fee), format_inr(service_fee)],

     ['', '', '', '', '', ''],

    ['', '', '', '', 'Subtotal', format_inr(service_fee)],
    ['', '', '', '', 'CGST (9%)', format_inr(cgst)],
    ['', '', '', '', 'SGST (9%)', format_inr(sgst)],
    ['', '', '', '', 'GRAND TOTAL', format_inr(total_amount)],  # ✅ LAST ROW
]


    
    col_widths = [25, width*0.40, 50, 30, 70, 70]
    items_table = Table(items_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
    # Header
    ('BACKGROUND', (0, 0), (-1, 0), primary),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

    # Grid (excluding total row)
    ('GRID', (0, 0), (-1, -2), 0.5, border_color),

    # Alignment
    ('ALIGN', (0, 1), (0, -1), 'CENTER'),
    ('ALIGN', (2, 1), (3, -1), 'CENTER'),
    ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),

    # Padding
    ('TOPPADDING', (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('LINEBELOW', (0, 1), (-1, 1), 0, colors.white),


    # ✅ GRAND TOTAL (LAST ROW ONLY)
    ('BACKGROUND', (0, -1), (-1, -1), accent),
    ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
]))


    elements.append(items_table)
    
    # ===== TOTAL BOX =====

    # ===== AMOUNT IN WORDS =====
    rupees = int(total_amount)
    paise = int((total_amount - rupees) * 100)
    words = f"Rupees {number_to_words(rupees)}"
    if paise > 0:
        words += f" and {number_to_words(paise)} Paise"
    words += " Only"
    
    words_data = [[Paragraph(f"<b>Amount in Words:</b> {words}", normal_style)]]
    words_table = Table(words_data, colWidths=[width])
    words_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(words_table)
    elements.append(Spacer(1, 5*mm))
    

    stamp_img = None
    if os.path.exists(STAMP_PATH):
        stamp_img = Image(
            STAMP_PATH,
            width=45 * mm,   # adjust if needed
            height=45 * mm,
            kind='proportional'
        )

    # ===== BANK DETAILS & TERMS =====
    bank_terms_data = [
        [
            Paragraph(f"<b>BANK DETAILS</b><br/><br/>"
                     f"Bank: {BANK_NAME}<br/>"
                     f"A/C No: {BANK_ACCOUNT}<br/>"
                     f"IFSC: {BANK_IFSC}<br/>"
                     f"Branch: {BANK_BRANCH}", normal_style),
            Paragraph(f"<b>TERMS & CONDITIONS</b><br/><br/>"
                     f"1. Payment due upon receipt.<br/>"
                     f"2. Quote invoice number when remitting.<br/>"
                     f"3. This is a Proforma Invoice.", normal_style),
           [
            Paragraph(f"<b>For {COMPANY_NAME}</b>", ParagraphStyle(
                '', fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER
            )),
            Spacer(1, 5 * mm),
            stamp_img if stamp_img else Spacer(1, 40),
            Spacer(1, 3 * mm),
            Paragraph("________________________", ParagraphStyle(
                '', fontSize=9, alignment=TA_CENTER
            )),
            Paragraph("Authorized Signatory", ParagraphStyle(
                '', fontSize=9, alignment=TA_CENTER
            ))
        ]
        ]
    ]
    bank_table = Table(bank_terms_data, colWidths=[width*0.35, width*0.35, width*0.30])
    bank_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(bank_table)
    elements.append(Spacer(1, 5*mm))
    
    # ===== FOOTER =====
    elements.append(Paragraph("This is a computer-generated Proforma Invoice.", center_style))
    elements.append(Paragraph(f"Thank you for your business!", center_style))
    
    doc.build(elements, onFirstPage=add_pdf_metadata)
    buffer.seek(0)
    return buffer.getvalue()

@router.post("/create")
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new Performa Invoice"""
    invoices_collection = get_collection("invoices")
    
    invoice_number = generate_invoice_number()
    total_amount = invoice_data.service_fee + invoice_data.gst_amount
    
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
    search: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get all invoices"""
    invoices_collection = get_collection("invoices")
    
    query = {}
    
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
    
    pdf_bytes = await generate_pdf(invoice)
    
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

