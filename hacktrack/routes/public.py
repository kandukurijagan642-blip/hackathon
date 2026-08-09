from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from werkzeug.security import generate_password_hash
import os
import secrets
from database import db
from models import User, Team, TeamMember, Attendance, ProblemSubmission, SystemSetting, Certificate, Round1Marks, Round2Marks, Round3Marks, FinalResult
from utils import generate_team_qr, send_mock_email

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    return render_template('public/landing.html')

@public_bp.route('/api/health-check')
def health_check():
    try:
        # Simple query to verify DB is online
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@public_bp.route('/api/team-status/<team_id>')
def api_team_status(team_id):
    from flask import request
    from models import User
    
    clean_id = team_id.strip().upper()
    team = Team.query.filter_by(team_id=clean_id).first()
    if not team:
        team = Team.query.filter(db.func.upper(Team.team_id) == clean_id).first()
    if not team:
        return jsonify({"success": False, "message": "Team not found. Please verify your Team ID."})
        
    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({"success": False, "message": "Leader Email address is required to check status."})
        
    leader = User.query.get(team.leader_id)
    if not leader or leader.email.lower().strip() != email:
        return jsonify({"success": False, "message": "Unauthorized. The email address does not match this Team ID."})
        
    att = Attendance.query.filter_by(team_id=team.team_id).first()
    sub = team.problem_submission
    r1 = Round1Marks.query.filter_by(team_id=team.team_id, is_submitted=True).first()
    r2 = Round2Marks.query.filter_by(team_id=team.team_id, is_submitted=True).first()
    r3 = Round3Marks.query.filter_by(team_id=team.team_id, is_submitted=True).first()
    cert = Certificate.query.filter_by(team_id=team.team_id).first()
    
    return jsonify({
        "success": True,
        "team_name": team.team_name,
        "college": team.college,
        "status": {
            "registration": "completed",
            "attendance": "completed" if (att and att.status == 'Present') else "pending",
            "project_submission": "completed" if (sub and sub.project_title) else "pending",
            "round1": "completed" if r1 else "pending",
            "round2": "completed" if r2 else "pending",
            "round3": "completed" if r3 else "pending",
            "certificates": "released" if (cert and cert.certificate_status == 'RELEASED') else ("generated" if cert else "pending")
        }
    })


@public_bp.route('/verify-certificate', methods=['GET', 'POST'])
@public_bp.route('/verify-certificate/<search_term>', methods=['GET'])
def verify_certificate(search_term=None):
    import hashlib
    
    query = search_term or request.form.get('query') or request.args.get('query', '')
    query = query.strip()
    
    cert = None
    if query:
        clean_q = query.upper()
        cert = Certificate.query.filter(
            (Certificate.verification_token == query) |
            (db.func.upper(Certificate.certificate_id) == clean_q) |
            (db.func.upper(Certificate.registration_number) == clean_q)
        ).first()
        
    # A certificate is only Valid if it has been officially RELEASED by the admin.
    # LOCKED certificates exist in the DB but are not yet authorised for public use.
    status = "Valid" if (cert and cert.certificate_status == 'RELEASED') else ("Invalid" if query else None)
    
    # Compute cryptographic checksum hash for digital authenticity badge
    digital_signature_hash = None
    if cert:
        raw_token = f"{cert.certificate_id}:{cert.student_name}:{cert.team_name}:{cert.verification_token}"
        digital_signature_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()[:16].upper()
        
    return render_template('public/verify_certificate.html', cert=cert, status=status, query=query, digital_hash=digital_signature_hash)

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
        
        # Check if team name already exists (case-insensitive)
        existing_team = Team.query.filter(db.func.lower(Team.team_name) == team_name.lower().strip()).first()
        if existing_team:
            flash(f'Team name "{team_name}" is already taken! Please choose a unique name.', 'danger')
            return render_template('public/register_team.html')
            
        # Validate leader email uniqueness/role
        leader_user = User.query.filter_by(email=leader_email).first()
        if leader_user:
            # If the user is already leading a team
            already_leading = Team.query.filter_by(leader_id=leader_user.id).first()
            if already_leading:
                flash(f'The email "{leader_email}" is already registered as the leader of team "{already_leading.team_name}". Each team must have a unique leader email.', 'danger')
                return render_template('public/register_team.html')
            
            # If the user exists but has a different role
            if leader_user.role != 'Leader':
                flash(f'The email "{leader_email}" is registered with the role "{leader_user.role}" and cannot be used as a team leader.', 'danger')
                return render_template('public/register_team.html')
            
        # Get existing leader user or create a new leader account
        from utils import generate_random_password
        default_pwd = generate_random_password()
        leader_user = User.query.filter_by(email=leader_email).first()
        if not leader_user:
            hashed_pwd = generate_password_hash(default_pwd)
            leader_user = User(
                name=leader_name,
                email=leader_email,
                password=hashed_pwd,
                role='Leader'
            )
            db.session.add(leader_user)
            db.session.flush()    # Get leader_user.id without committing
        
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
        
        # 4. Create initial Attendance record (Absent by default)
        att = Attendance(team_id=team_id, status='Absent')
        db.session.add(att)
        
        # 5. Add Members
        member_names = request.form.getlist('member_name[]')
        member_regs = request.form.getlist('member_reg[]') if 'member_reg[]' in request.form else []
        member_emails = request.form.getlist('member_email[]')
        member_phones = request.form.getlist('member_phone[]')
        
        for idx, (name, email, phone) in enumerate(zip(member_names, member_emails, member_phones)):
            if name.strip():
                reg_val = member_regs[idx].strip() if idx < len(member_regs) and member_regs[idx].strip() else f"{team_id}-M{idx+1}"
                m = TeamMember(
                    team_id=team_id,
                    student_name=name.strip(),
                    registration_number=reg_val,
                    email=email.strip(),
                    phone=phone.strip()
                )
                db.session.add(m)

        # --- Single atomic commit for all core records ---
        db.session.commit()

        # --- Side effects after commit (failures here are non-fatal) ---

        # 6. Generate QR Code
        try:
            generate_team_qr(
                team_id=new_team.team_id,
                team_name=new_team.team_name,
                leader_name=leader_user.name,
                host_url=request.host_url.rstrip('/')
            )
        except Exception as e:
            print(f"QR generation error: {e}")

        # 7. Auto-generate LOCKED certificates
        try:
            from certificate_automation import auto_generate_team_certificates
            auto_generate_team_certificates(new_team)
        except Exception as e:
            print(f"Certificate generation error: {e}")

        # 8. Sync to Local Backup & MongoDB Atlas for permanent persistence
        try:
            from persistent_backup import save_local_backup
            save_local_backup()
        except Exception as e:
            print(f"Local backup error: {e}")

        try:
            from mongo_sync import sync_all_to_mongo
            sync_all_to_mongo()
        except Exception as e:
            print(f"MongoDB sync error: {e}")

        # 9. Send mock welcome email
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
    clean_id = team_id.strip().upper()
    team = Team.query.filter(db.func.lower(Team.team_id) == clean_id.lower()).first()
    if not team:
        try:
            from persistent_backup import restore_local_backup
            restore_local_backup(current_app, db)
            team = Team.query.filter(db.func.lower(Team.team_id) == clean_id.lower()).first()
        except Exception:
            pass
    if not team:
        flash(f"Team '{team_id}' registration is confirmed! Please check your dashboard or contact organizer.", "info")
        return redirect(url_for('auth.login'))
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
    payload = team.get_qr_url(actual_host)
    
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


@public_bp.route('/qr-access/<token>')
def qr_access(token):
    from itsdangerous import URLSafeSerializer
    from flask import current_app, redirect, url_for, flash, request, abort
    from flask_login import current_user
    from models import Team, Attendance
    from datetime import datetime
    
    serializer = URLSafeSerializer(current_app.config['SECRET_KEY'], salt='qr-access-salt')
    try:
        team_id = serializer.loads(token)
    except Exception:
        flash("Invalid or expired secure QR code token.", "danger")
        abort(403)
        
    team = Team.query.get_or_404(team_id)
    
    if not current_user.is_authenticated:
        from flask_login import login_user
        leader_user = User.query.get(team.leader_id)
        if leader_user:
            login_user(leader_user)
            flash(f"Welcome back, {leader_user.name}! Logged in securely via QR access.", "success")
            return redirect(url_for('leader.quick_edit', team_id=team.team_id))
        else:
            return redirect(url_for('auth.login'))
        
    if current_user.role in ['Admin', 'Organizer']:
        att = Attendance.query.filter_by(team_id=team.team_id).first()
        if not att:
            att = Attendance(team_id=team.team_id)
            db.session.add(att)
        att.status = 'Present'
        if not att.checkin_time:
            att.checkin_time = datetime.utcnow()
        db.session.commit()
        
        flash(f"✅ Check-in success! {team.team_name} has been marked as Present.", "success")
        return redirect(url_for('leader.quick_edit', team_id=team.team_id))
    elif current_user.role == 'Leader':
        if team.leader_id == current_user.id:
            return redirect(url_for('leader.quick_edit', team_id=team.team_id))
        else:
            flash("Unauthorized access! You can only scan/edit your own team's details.", "danger")
            return redirect(url_for('leader.dashboard'))
    else:
        abort(403)
