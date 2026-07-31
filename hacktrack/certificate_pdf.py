import os
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def generate_pdf_certificate(cert_id, student_name, team_name, project_title, cert_type, verification_url, output_path, signature_path=None, logo_path=None):
    """
    Generates a professional Landscape Certificate PDF matching the SIMATS mockup design.
    """
    # Create the folder if it does not exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 1. Generate the verification QR code image
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(verification_url)
    qr.make(fit=True)
    
    temp_qr_path = output_path + ".qr.png"
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img.save(temp_qr_path)
    
    # 2. Initialize Landscape Page
    c = canvas.Canvas(output_path, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    # Draw double border margins
    # Outer brown border
    c.setStrokeColor(colors.HexColor('#8b0000')) # Dark red/maroon border
    c.setLineWidth(6)
    c.rect(15, 15, width - 30, height - 30)
    
    # Inner gold border
    c.setStrokeColor(colors.HexColor('#d4af37')) # Gold accent border
    c.setLineWidth(2)
    c.rect(22, 22, width - 44, height - 44)
    
    # Draw decorative corner triangles
    c.setFillColor(colors.HexColor('#d4af37'))
    # Top Left
    p = c.beginPath()
    p.moveTo(22, height - 22)
    p.lineTo(60, height - 22)
    p.lineTo(22, height - 60)
    p.close()
    c.drawPath(p, fill=True, stroke=False)
    
    # Top Right
    p = c.beginPath()
    p.moveTo(width - 22, height - 22)
    p.lineTo(width - 60, height - 22)
    p.lineTo(width - 22, height - 60)
    p.close()
    c.drawPath(p, fill=True, stroke=False)
    
    # Bottom Left
    p = c.beginPath()
    p.moveTo(22, 22)
    p.lineTo(60, 22)
    p.lineTo(22, 60)
    p.close()
    c.drawPath(p, fill=True, stroke=False)
    
    # Bottom Right
    p = c.beginPath()
    p.moveTo(width - 22, 22)
    p.lineTo(width - 60, 22)
    p.lineTo(width - 22, 60)
    p.close()
    c.drawPath(p, fill=True, stroke=False)
    
    # Draw Header Text & Logos
    c.setFillColor(colors.HexColor('#002855')) # Navy main brand color
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2.0, height - 70, "SIMATS ENGINEERING")
    
    c.setFillColor(colors.HexColor('#0056b3'))
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2.0, height - 90, "NBA Tier 1  |  IET-UK  |  ABET Accreditation")
    
    # Drawing Logo (if present, draw top-left; otherwise draw geometric branding mark)
    if logo_path and os.path.exists(logo_path):
        c.drawImage(logo_path, 45, height - 95, width=65, height=55, mask='auto')
    else:
        # Default placeholder geometric logo (Shield shape)
        c.setStrokeColor(colors.HexColor('#002855'))
        c.setFillColor(colors.HexColor('#2563eb'))
        p = c.beginPath()
        p.moveTo(55, height - 50)
        p.lineTo(85, height - 50)
        p.lineTo(85, height - 75)
        p.lineTo(70, height - 90)
        p.lineTo(55, height - 75)
        p.close()
        c.drawPath(p, fill=True, stroke=True)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(70, height - 72, "SE")
    
    # Main Certificate Title
    c.setFillColor(colors.HexColor('#1f2937'))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width / 2.0, height - 150, "CERTIFICATE")
    
    c.setFillColor(colors.HexColor('#d4af37')) # Gold subhead
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2.0, height - 175, f"OF {cert_type.upper()}")
    
    c.setFillColor(colors.HexColor('#4b5563'))
    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(width / 2.0, height - 210, "This is proudly presented to")
    
    # Student Name
    c.setFillColor(colors.HexColor('#111827'))
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2.0, height - 250, student_name)
    
    # Line under name
    c.setStrokeColor(colors.HexColor('#d1d5db'))
    c.setLineWidth(1)
    c.line(width / 2.0 - 150, height - 260, width / 2.0 + 150, height - 260)
    
    # Description Body
    c.setFillColor(colors.HexColor('#374151'))
    c.setFont("Helvetica", 13)
    
    body_text_1 = f"active member of Team \"{team_name}\" in recognition of their dynamic participation"
    body_text_2 = f"and successful implementation of the project: \"{project_title}\""
    body_text_3 = "during the HackTrack Hackathon Management & Evaluation Portal 2026."
    
    c.drawCentredString(width / 2.0, height - 290, body_text_1)
    c.drawCentredString(width / 2.0, height - 310, body_text_2)
    c.drawCentredString(width / 2.0, height - 330, body_text_3)
    
    # Issue Date and Certificate ID
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor('#6b7280'))
    c.drawString(45, 60, f"Date of Issue: {datetime.now().strftime('%B %d, %Y')}")
    c.drawString(45, 45, f"Certificate ID: {cert_id}")
    
    # Signatures
    # 1. HOD / Event Coordinator Signature
    c.setStrokeColor(colors.HexColor('#9ca3af'))
    c.line(width - 250, 75, width - 130, 75)
    
    c.setFillColor(colors.HexColor('#1f2937'))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(width - 250, 60, "HoD / Event Coordinator")
    
    # 2. Principal Signature
    c.line(width - 110, 75, width - 40, 75)
    c.drawString(width - 110, 60, "Principal")
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(width - 110, 45, "Dr. B. Ramesh")
    
    # Draw digital signatures if uploaded, else placeholder script text
    if signature_path and os.path.exists(signature_path):
        c.drawImage(signature_path, width - 230, 80, width=80, height=35, mask='auto')
    else:
        # Placeholder script fonts
        c.setFont("Courier-Oblique", 14)
        c.setFillColor(colors.HexColor('#1d4ed8'))
        c.drawString(width - 210, 85, "S.K. Singh")
        c.drawString(width - 95, 85, "B. Ramesh")
    
    # Draw dynamic verification QR Code on bottom right
    c.drawImage(temp_qr_path, width / 2.0 - 35, 45, width=70, height=70)
    c.setFillColor(colors.HexColor('#9ca3af'))
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(width / 2.0, 38, "SCAN TO VERIFY")
    
    # Save the page
    c.showPage()
    c.save()
    
    # Cleanup temp QR code image
    try:
        os.remove(temp_qr_path)
    except:
        pass
