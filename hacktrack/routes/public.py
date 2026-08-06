from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from werkzeug.security import generate_password_hash
import os
import secrets
from database import db
from models import User, Team, TeamMember, Attendance, ProblemSubmission, SystemSetting, Certificate
from utils import generate_team_qr, send_mock_email

public_bp = Blueprint('public', __name__)

@public_bp.route('/verify-certificate/<token>')
def verify_certificate(token):
    # Lookup the certificate using the verification token
    cert = Certificate.query.filter_by(verification_token=token).first()
    status = "Valid" if cert else "Invalid"
    return render_template('public/verify_certificate.html', cert=cert, status=status)

@public_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        team_name = request.form.get('team_name', '').strip()
        college = request.form.get('college', '').strip()
        department = request.form.get('department', '').strip()
        
        # Leader Details
        leader_name = request.form.get('leader_name', '').strip()
        leader_email = request.form.get('leader_email', '').strip()
        leader_phone = request.form.get('leader_phone', '').strip()
        
        # Check if team name and leader name already exist (case-insensitive)
        existing_teams = Team.query.filter(db.func.lower(Team.team_name) == team_name.lower().strip()).all()
        for t in existing_teams:
            l_user = User.query.get(t.leader_id)
            if l_user and l_user.name.lower().strip() == leader_name.lower().strip():
                flash(f'Team "{team_name}" led by leader "{leader_name}" already exists!', 'danger')
                return render_template('public/register_team.html')
            
        # Get existing leader user or create a new leader account
        leader_user = User.query.filter_by(email=leader_email).first()
        if not leader_user:
            default_pwd = f"{team_name.replace(' ', '')}@12309"
            hashed_pwd = generate_password_hash(default_pwd)
            leader_user = User(
                name=leader_name,
                email=leader_email,
                password=hashed_pwd,
                role='Leader'
            )
            db.session.add(leader_user)
            db.session.commit()
        
        # 2. Auto-generate guaranteed unique Team ID
        from utils import generate_unique_team_id
        team_id = generate_unique_team_id()
        
        # 3. Create Team
        new_team = Team(
            team_id=team_id,
            team_name=team_name,
            college=college,
            department=department,
            leader_id=leader_user.id
        )
        db.session.add(new_team)
        db.session.commit()
        
        # 4. Create initial Attendance record (Absent by default)
        att = Attendance(team_id=new_team.team_id, status='Absent')
        db.session.add(att)
        db.session.commit()
        
        # 5. Generate QR Code containing link to quick-edit page
        generate_team_qr(
            team_id=new_team.team_id,
            team_name=new_team.team_name,
            leader_name=leader_user.name,
            host_url=request.host_url.rstrip('/')
        )
        
        # 6. Add Members
        member_names = request.form.getlist('member_name[]')
        member_regs = request.form.getlist('member_reg[]') if 'member_reg[]' in request.form else []
        member_emails = request.form.getlist('member_email[]')
        member_phones = request.form.getlist('member_phone[]')
        
        for idx, (name, email, phone) in enumerate(zip(member_names, member_emails, member_phones)):
            if name.strip():
                reg_val = member_regs[idx].strip() if idx < len(member_regs) and member_regs[idx].strip() else f"{new_team.team_id}-M{idx+1}"
                m = TeamMember(
                    team_id=new_team.team_id,
                    student_name=name.strip(),
                    registration_number=reg_val,
                    email=email.strip(),
                    phone=phone.strip()
                )
                db.session.add(m)
                
        db.session.commit()

        # Sync to MongoDB Atlas for permanent persistence
        try:
            from mongo_sync import sync_all_to_mongo
            sync_all_to_mongo()
        except Exception as e:
            print(f"MongoDB sync error: {e}")

        # Auto generate LOCKED certificates in the background immediately
        from certificate_automation import auto_generate_team_certificates
        auto_generate_team_certificates(new_team)
        
        # Send mock welcome email
        email_body = f"""Hello {leader_name},

Your team '{team_name}' has been registered for the HackTrack Hackathon!

Your Custom Team ID: {team_id}

You can login to the website with:
- Email: {leader_email}
- Password: {default_pwd}

Or simply scan/keep your team QR code to access your team page directly without logging in.

Best regards,
HackTrack Team"""
        send_mock_email(leader_email, "Welcome to HackTrack - Team Registration Confirmation", email_body)
        
        # Log activity
        try:
            from models import ActivityLog
            log = ActivityLog(user_id=leader_user.id, action="Public Team Registry", ip_address=request.remote_addr, details=f"Registered team {team_id} ({team_name})")
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Log error: {e}")
            
        flash(f"Congratulations! Team '{team_name}' registered successfully! Your Team ID is {team_id}.", "success")
        return redirect(url_for('public.registration_success', team_id=team_id))
        
    return render_template('public/register_team.html')

@public_bp.route('/registration-success/<team_id>')
def registration_success(team_id):
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    return render_template('public/registration_success.html', team=team)

@public_bp.route('/qr/registration')
def registration_qr():
    import qrcode
    from io import BytesIO
    from flask import send_file
    from utils import get_actual_host_url
    
    actual_host = get_actual_host_url()
    payload = f"{actual_host}/register"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return send_file(buf, mimetype="image/png")

@public_bp.route('/qr/team/<team_id>')
def team_qr(team_id):
    import qrcode
    from io import BytesIO
    from flask import send_file, abort
    from utils import get_actual_host_url
    from models import Team
    
    clean_id = team_id.strip().upper()
    team = Team.query.filter_by(team_id=clean_id).first()
    if not team:
        abort(404)
        
    actual_host = get_actual_host_url()
    payload = f"{actual_host}/leader/quick-edit/{team.team_id}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return send_file(buf, mimetype="image/png")
