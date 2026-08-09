import os
import qrcode
import pandas as pd
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line

from config import Config

def get_actual_host_url(default_val="http://localhost:5000"):
    try:
        from flask import request
        if request:
            import os
            env_url = os.environ.get('APP_BASE_URL')
            if env_url:
                return env_url.rstrip('/')
            proto = request.headers.get('X-Forwarded-Proto', request.scheme)
            host = request.headers.get('X-Forwarded-Host', request.host)
            return f"{proto}://{host}"
    except Exception as e:
        print(f"Error getting request context: {e}")
    import os
    env_url = os.environ.get('APP_BASE_URL')
    if env_url:
        return env_url.rstrip('/')
    return default_val

def generate_unique_team_id():
    """
    Generates a cryptographically random, collision-resistant Team ID in HT2026-XXXXXX format
    to prevent race conditions during concurrent registrations.
    """
    import secrets
    from models import Team
    try:
        for _ in range(10):
            candidate = f"HT2026-{secrets.token_hex(3).upper()}"
            if not Team.query.get(candidate):
                return candidate
        # Fallback if somehow there's a collision
        return f"HT2026-{secrets.token_hex(6).upper()}"
    except Exception as e:
        import time
        return f"HT2026-{int(time.time()) % 1000:03d}-{secrets.token_hex(2).upper()}"

def generate_team_qr(team_id, team_name, leader_name, host_url="http://localhost:5000"):
    """
    Generates a QR code for a team containing: Team ID | Team Name | Leader Name
    and saves it as a PNG file in the static directory.
    """
    from models import Team
    from flask import current_app
    
    actual_host = get_actual_host_url(host_url)
    
    team = None
    try:
        team = Team.query.get(team_id)
    except Exception:
        pass
        
    if team:
        qr_payload = team.get_qr_url(actual_host)
    else:
        from itsdangerous import URLSafeSerializer
        try:
            secret_key = current_app.config['SECRET_KEY']
        except Exception:
            secret_key = Config.SECRET_KEY
        serializer = URLSafeSerializer(secret_key, salt='qr-access-salt')
        token = serializer.dumps(team_id)
        qr_payload = f"{actual_host.rstrip('/')}/qr-access/{token}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    qr_filename = f"team_{team_id}_qr.png"
    qr_filepath = os.path.join(Config.BASE_DIR, 'static', 'qrcodes', qr_filename)
    img.save(qr_filepath)
    return f"qrcodes/{qr_filename}"

def generate_registration_qr(host_url="http://localhost:5000"):
    actual_host = get_actual_host_url(host_url)
    qr_payload = f"{actual_host}/register"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    qr_filename = "registration_qr.png"
    qr_filepath = os.path.join(Config.BASE_DIR, 'static', 'qrcodes', qr_filename)
    os.makedirs(os.path.dirname(qr_filepath), exist_ok=True)
    img.save(qr_filepath)
    return f"qrcodes/{qr_filename}"

def export_to_excel(data_list, columns, filepath):
    """
    Exports list of dicts to an Excel sheet.
    """
    df = pd.DataFrame(data_list, columns=columns)
    df.to_excel(filepath, index=False, engine='openpyxl')
    return filepath

def generate_pdf_report(title, headers, data, filepath):
    """
    Generates a professional PDF report with a styled table.
    """
    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=54, bottomMargin=54)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        alignment=1, # Centered
        spaceAfter=20
    )
    
    normal_style = ParagraphStyle(
        'ReportNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569')
    )
    
    # Add title
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(f"Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    story.append(Spacer(1, 15))
    
    # Format table data
    table_data = [headers]
    for row in data:
        formatted_row = []
        for cell in row:
            # Wrap cells in Paragraph to support auto-wrapping
            formatted_row.append(Paragraph(str(cell) if cell is not None else '', normal_style))
        table_data.append(formatted_row)
        
    # Table design
    col_count = len(headers)
    col_width = 540 / col_count if col_count > 0 else 540
    col_widths = [col_width] * col_count
    
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')), # Dark navy header
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#F8FAFC'), colors.white]), # Alternating rows
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
    ]))
    
    story.append(t)
    doc.build(story)
    return filepath

def generate_member_certificate(team_name, project_title, student_name, rank_text=None, filepath=None):
    """
    Generates a highly styled Certificate of Participation or Achievement.
    Landscape format.
    """
    if not filepath:
        filename = f"cert_{student_name.lower().replace(' ', '_')}.pdf"
        filepath = os.path.join(Config.EXPORT_FOLDER, filename)
        
    doc = SimpleDocTemplate(filepath, pagesize=landscape(letter), rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CertTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=36,
        leading=42,
        textColor=colors.HexColor('#1E3A8A'), # Navy blue
        alignment=1,
        spaceAfter=20
    )
    
    subtitle_style = ParagraphStyle(
        'CertSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#4B5563'),
        alignment=1,
        spaceAfter=30
    )
    
    name_style = ParagraphStyle(
        'CertName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=32,
        textColor=colors.HexColor('#B45309'), # Amber/Gold
        alignment=1,
        spaceAfter=20
    )
    
    text_style = ParagraphStyle(
        'CertText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=20,
        textColor=colors.HexColor('#374151'),
        alignment=1,
        spaceAfter=20
    )
    
    cert_content = [
        [Spacer(1, 15)],
        [Paragraph("CERTIFICATE OF EXCELLENCE" if rank_text else "CERTIFICATE OF PARTICIPATION", title_style)],
        [Paragraph("THIS IS PROUDLY PRESENTED TO", subtitle_style)],
        [Paragraph(student_name.upper(), name_style)],
        [Paragraph(f"for actively participating and demonstrating excellence in <b>HackTrack Hackathon</b>", text_style)],
        [Paragraph(f"with the project <b>\"{project_title}\"</b> under team <b>{team_name}</b>.", text_style)],
    ]
    
    if rank_text:
        cert_content.append([Paragraph(f"achieving <b>{rank_text}</b> in the final evaluation.", text_style)])
    else:
        cert_content.append([Spacer(1, 15)])
        
    cert_content.append([Spacer(1, 30)])
    
    sig_data = [
        [
            Paragraph("______________________<br/><b>Event Convener</b><br/>HackTrack Committee", text_style),
            Paragraph("______________________<br/><b>Chief Judge</b><br/>HackTrack Jury", text_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[300, 300])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    
    cert_content.append([sig_table])
    
    main_table = Table(cert_content, colWidths=[680])
    main_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 4, colors.HexColor('#1E3A8A')),  # Outer Navy Box
        ('INNERGRID', (0,0), (-1,-1), 1, colors.HexColor('#F59E0B')), # Golden grid lines / frame highlight
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFCF5')), # Soft cream background
        ('TOPPADDING', (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('LEFTPADDING', (0,0), (-1,-1), 40),
        ('RIGHTPADDING', (0,0), (-1,-1), 40),
    ]))
    
    story.append(main_table)
    doc.build(story)
    return filepath

def send_mock_email(to_email, subject, body_text):
    """
    Sends a real email via SMTP if configured, otherwise mocks by logging to file.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body_text, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            print(f"Email sent to {to_email} with subject '{subject}'")
            return
        except Exception as e:
            print(f"SMTP send failed: {e}, falling back to mock log.")
    
    # Fallback: log to file
    log_file = os.path.join(Config.BASE_DIR, 'exports', 'mock_emails.log')
    email_content = f"""
===================================================
TIMESTAMP: {pd.Timestamp.now()}
TO: {to_email}
SUBJECT: {subject}
---------------------------------------------------
{body_text}
===================================================
"""
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(email_content)
        print(f"Mock email sent to {to_email} with subject '{subject}'. Recorded in exports/mock_emails.log")
    except Exception as e:
        print(f"Failed to write mock email: {e}")


def send_mock_email_with_attachments(to_email, subject, body_text, attachments=None):
    """
    Sends a real email with PDF attachments via SMTP if configured,
    otherwise mocks by logging to file.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication
    
    try:
        from models import SystemSetting
        sys_user = SystemSetting.get_setting('smtp_user', '')
        sys_pass = SystemSetting.get_setting('smtp_pass', '')
        sys_server = SystemSetting.get_setting('smtp_server', 'smtp.gmail.com')
        sys_port = SystemSetting.get_setting('smtp_port', '587')
    except Exception:
        sys_user = sys_pass = ''
        sys_server = 'smtp.gmail.com'
        sys_port = '587'
        
    smtp_user = os.environ.get('SMTP_USER', '') or sys_user
    smtp_pass = os.environ.get('SMTP_PASS', '') or sys_pass
    smtp_server = os.environ.get('SMTP_SERVER', '') or sys_server
    smtp_port_val = os.environ.get('SMTP_PORT', '') or sys_port
    smtp_port = int(smtp_port_val) if smtp_port_val and str(smtp_port_val).isdigit() else 587
    
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body_text, 'plain'))
            
            if attachments:
                for filename, data in attachments:
                    part = MIMEApplication(data, Name=filename)
                    part['Content-Disposition'] = f'attachment; filename="{filename}"'
                    msg.attach(part)
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            print(f"Email with {len(attachments or [])} attachment(s) sent to {to_email}")
            return
        except Exception as e:
            print(f"SMTP send failed: {e}, falling back to mock log.")
    
    # Fallback: log to file
    log_file = os.path.join(Config.BASE_DIR, 'exports', 'mock_emails.log')
    attach_str = ""
    if attachments:
        attach_str = "\nATTACHMENTS:\n" + "\n".join([f"- {name} ({len(data)} bytes)" for name, data in attachments])
    
    email_content = f"""
===================================================
TIMESTAMP: {pd.Timestamp.now()}
TO: {to_email}
SUBJECT: {subject}
---------------------------------------------------
{body_text}
{attach_str}
===================================================
"""
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(email_content)
        print(f"Mock email with attachments sent to {to_email}. Recorded in exports/mock_emails.log")
    except Exception as e:
        print(f"Failed to write mock email: {e}")


def generate_random_password(length=12):
    """
    Generates a secure, random alphanumeric password.
    """
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


