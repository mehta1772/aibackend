"""
Email Service
Handles sending welcome emails and notifications
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional
import aiosmtplib

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@yourcompany.com")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Your Company Name")

async def send_welcome_email(
    to_email: str,
    company_name: str,
    contact_person: str,
    services: list,
    total_amount: float,
    booking_date: str
):
    """Send welcome email after booking creation"""
    
    subject = f"Welcome to {COMPANY_NAME} - Booking Confirmation"
    
    services_list = ", ".join(services)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .highlight {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            .btn {{ display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
            h1 {{ margin: 0; }}
            .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }}
            .label {{ color: #666; }}
            .value {{ font-weight: 600; color: #333; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Booking Confirmed!</h1>
                <p>Thank you for choosing {COMPANY_NAME}</p>
            </div>
            <div class="content">
                <p>Dear <strong>{contact_person}</strong>,</p>
                <p>We are delighted to confirm your booking with us. Below are the details of your engagement:</p>
                
                <div class="highlight">
                    <div class="detail-row">
                        <span class="label">Company Name:</span>
                        <span class="value">{company_name}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Services:</span>
                        <span class="value">{services_list}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Total Amount:</span>
                        <span class="value">₹{total_amount:,.2f}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Booking Date:</span>
                        <span class="value">{booking_date}</span>
                    </div>
                </div>
                
                <p>Our team will be in touch with you shortly to guide you through the next steps.</p>
                <p>If you have any questions, feel free to reach out to us.</p>
                
                <p>Best regards,<br><strong>{COMPANY_NAME} Team</strong></p>
            </div>
            <div class="footer">
                <p>© 2025 {COMPANY_NAME}. All rights reserved.</p>
                <p>This is an automated message. Please do not reply directly to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text fallback
    text_content = f"""
    Welcome to {COMPANY_NAME}!
    
    Dear {contact_person},
    
    We are delighted to confirm your booking with us.
    
    Booking Details:
    - Company: {company_name}
    - Services: {services_list}
    - Total Amount: ₹{total_amount:,.2f}
    - Booking Date: {booking_date}
    
    Our team will be in touch with you shortly.
    
    Best regards,
    {COMPANY_NAME} Team
    """
    
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = FROM_EMAIL
        message["To"] = to_email
        
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        
        message.attach(part1)
        message.attach(part2)
        
        if SMTP_USER and SMTP_PASSWORD:
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
                start_tls=True,
            )
            return True
        else:
            print(f"Email would be sent to: {to_email}")
            print(f"Subject: {subject}")
            return True
            
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

async def send_invoice_email(
    to_email: str,
    client_name: str,
    invoice_number: str,
    total_amount: float,
    pdf_attachment: Optional[bytes] = None
):
    """Send invoice email with PDF attachment"""
    
    subject = f"Performa Invoice #{invoice_number} - {COMPANY_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 Performa Invoice</h1>
            </div>
            <div class="content">
                <p>Dear <strong>{client_name}</strong>,</p>
                <p>Please find attached your Performa Invoice #{invoice_number}.</p>
                <p><strong>Total Amount: ₹{total_amount:,.2f}</strong></p>
                <p>Thank you for your business!</p>
                <p>Best regards,<br><strong>{COMPANY_NAME} Team</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        message = MIMEMultipart()
        message["Subject"] = subject
        message["From"] = FROM_EMAIL
        message["To"] = to_email
        
        message.attach(MIMEText(html_content, "html"))
        
        if pdf_attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(pdf_attachment)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename=Invoice_{invoice_number}.pdf"
            )
            message.attach(part)
        
        if SMTP_USER and SMTP_PASSWORD:
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
                start_tls=True,
            )
            return True
        else:
            print(f"Invoice email would be sent to: {to_email}")
            return True
            
    except Exception as e:
        print(f"Failed to send invoice email: {str(e)}")
        return False
