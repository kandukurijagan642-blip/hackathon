from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import datetime
import os
import pandas as pd

from database import db
from models import User, Team, TeamMember, Attendance, ActivityLog, SystemSetting, ProblemSubmission
from utils import generate_team_qr, send_mock_email

organizer_bp = Blueprint('organizer', __name__, url_prefix='/organizer')

def log_organizer_activity(action, details=None):
    try:
        log = ActivityLog(user_id=current_user.id, action=action, ip_address=request.remote_addr, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging organizer activity: {e}")

def check_organizer():
    if not current_user.is_authenticated or current_user.role not in ['Admin', 'Organizer']:
        flash('Unauthorized access!', 'danger')
        return False
    return True

@organizer_bp.route('/dashboard')
@login_required
def dashboard():
    if not check_organizer(): return redirect(url_for('auth.login'))
    
    total_teams = Team.query.count()
    checked_in = Attendance.query.filter_by(status='Present').count()
    pending = total_teams - checked_in
    
    recent_teams = Team.query.order_by(Team.created_at.desc()).limit(5).all()
    
    return render_template(
        'organizer/dashboard.html',
        total_teams=total_teams,
        checked_in=checked_in,
        pending=pending,
        recent_teams=recent_teams
    )

@organizer_bp.route('/toggle-setting/<key>', methods=['POST'])
@login_required
def toggle_setting(key):
    if not check_organizer():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        return redirect(url_for('auth.login'))
    
    current_val = SystemSetting.get_setting(key, 'False')
    new_val = 'True' if current_val == 'False' else 'False'
    SystemSetting.set_setting(key, new_val)
    
    log_organizer_activity("Toggle System Setting", f"Toggled setting '{key}' to {new_val}")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
        return jsonify({'success': True, 'new_value': new_val})
        
    flash(f"System state '{key}' updated to {new_val}.", "success")
    return redirect(url_for('organizer.dashboard'))

@organizer_bp.route('/teams')
@login_required
def view_teams():
    if not check_organizer(): return redirect(url_for('auth.login'))
    teams = Team.query.order_by(Team.created_at.desc()).all()
    return render_template('organizer/teams.html', teams=teams)

@organizer_bp.route('/register-team', methods=['GET', 'POST'])
@login_required
def register_team():
    if not check_organizer(): return redirect(url_for('auth.login'))
    
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
                return render_template('organizer/register_team.html')
            
        # Get existing leader user or create a new leader account
        default_pwd = f"{team_name.replace(' ', '')}@12309"
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
        
        # 5. Generate QR Code containing: Team ID | Team Name | Leader Name
        qr_path = generate_team_qr(
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
        
        email_body = f"""Hello {leader_name},

Your team '{team_name}' has been registered for the HackTrack Hackathon!

Your Custom Team ID: {team_id}

Your Leader login credentials are:
- Email: {leader_email}
- Password: {default_pwd}

Please log in to your dashboard to track your team progress, attendance status, and download your QR Code.
Note that the problem statement release phase is currently locked. You will be notified when submissions unlock.

Best regards,
HackTrack Organizer Team"""
        send_mock_email(leader_email, "Welcome to HackTrack - Team Registration Confirmation", email_body)
        
        log_organizer_activity("Register Team", f"Registered team {team_id} ({team_name})")
        flash(f"Team '{team_name}' (ID: {team_id}) registered successfully! Credentials sent to {leader_email}.", "success")
        return redirect(url_for('organizer.registration_success', team_id=team_id))
        
    return render_template('organizer/register_team.html')

@organizer_bp.route('/registration-success/<team_id>')
@login_required
def registration_success(team_id):
    if not check_organizer(): return redirect(url_for('auth.login'))
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    return render_template('organizer/registration_success.html', team=team)

@organizer_bp.route('/checkin/<team_id>', methods=['GET', 'POST'])
@login_required
def checkin_team(team_id):
    if not check_organizer(): return redirect(url_for('auth.login'))
    
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    att = Attendance.query.filter_by(team_id=team_id).first()
    
    if not att:
        att = Attendance(team_id=team_id, status='Absent')
        db.session.add(att)
        
    att.status = 'Present'
    att.checkin_time = datetime.datetime.utcnow()
    db.session.commit()
    
    # Notify team leader
    leader = User.query.get(team.leader_id)
    if leader:
        email_body = f"""Hello {leader.name},

Your team '{team.team_name}' has successfully checked in to the HackTrack Hackathon at {att.checkin_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC).

Attendance Status: PRESENT

Stay tuned for evaluation round announcements.

Best regards,
HackTrack Organizing Team"""
        send_mock_email(leader.email, "HackTrack - Attendance Check-in Successful", email_body)
        
    log_organizer_activity("QR Checkin", f"Team {team.team_id} checked in via QR code")
    
    # Check if request is AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return jsonify({'success': True, 'message': f'Attendance marked PRESENT for team {team.team_id} ({team.team_name}).'})
        
    return render_template('organizer/checkin_success.html', team=team, att=att)

@organizer_bp.route('/scan-qr')
@login_required
def scan_qr():
    if not check_organizer(): return redirect(url_for('auth.login'))
    return render_template('organizer/scan_qr.html')

@organizer_bp.route('/csv-import', methods=['POST'])
@login_required
def csv_import():
    if not check_organizer(): return redirect(url_for('auth.login'))
    
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.', 'danger')
        return redirect(url_for('organizer.view_teams'))
        
    try:
        df = pd.read_csv(file)
        imported_count = 0
        for _, row in df.iterrows():
            team_name = str(row['team_name']).strip()
            leader_name = str(row['leader_name']).strip()
            
            existing_teams = Team.query.filter(db.func.lower(Team.team_name) == team_name.lower().strip()).all()
            is_dup = False
            for t in existing_teams:
                l_user = User.query.get(t.leader_id)
                if l_user and l_user.name.lower().strip() == leader_name.lower().strip():
                    is_dup = True
                    break
            if is_dup:
                continue
                
            leader_email = str(row['leader_email']).strip()
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
            
            from utils import generate_unique_team_id
            team_id = generate_unique_team_id()
            
            new_team = Team(
                team_id=team_id,
                team_name=team_name,
                college=str(row['college']).strip(),
                department=str(row['department']).strip(),
                leader_id=leader_user.id
            )
            db.session.add(new_team)
            db.session.commit()
            
            att = Attendance(team_id=new_team.team_id, status='Absent')
            db.session.add(att)
            db.session.commit()
            
            generate_team_qr(
                team_id=new_team.team_id,
                team_name=new_team.team_name,
                leader_name=leader_user.name,
                host_url=request.host_url.rstrip('/')
            )
            from certificate_automation import auto_generate_team_certificates
            auto_generate_team_certificates(new_team)
            imported_count += 1
            
        db.session.commit()
        log_organizer_activity("CSV Import", f"Imported {imported_count} teams from CSV")
        flash(f"Successfully imported {imported_count} teams from CSV file.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error parsing CSV file: {e}", "danger")
        
    return redirect(url_for('organizer.view_teams'))


@organizer_bp.route('/teams/edit/<team_id>', methods=['GET', 'POST'])
@login_required
def edit_team(team_id):
    if not check_organizer(): return redirect(url_for('auth.login'))
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    
    if request.method == 'POST':
        team.team_name = request.form.get('team_name', '').strip()
        team.college = request.form.get('college', '').strip()
        team.department = request.form.get('department', '').strip()
        
        # Leader details
        leader = User.query.get(team.leader_id)
        if leader:
            leader.name = request.form.get('leader_name', '').strip()
            leader.email = request.form.get('leader_email', '').strip()
            
        # Optional submission details edit/creation
        project_title = request.form.get('project_title', '').strip()
        domain = request.form.get('domain', '').strip()
        problem_statement = request.form.get('problem_statement', '').strip()
        abstract = request.form.get('abstract', '').strip()
        technology_stack = request.form.get('technology_stack', '').strip()
        
        if project_title or domain or problem_statement:
            if not team.problem_submission:
                sub = ProblemSubmission(
                    team_id=team.team_id,
                    project_title=project_title,
                    domain=domain,
                    problem_statement=problem_statement,
                    abstract=abstract or 'Abstract Details (Pending)',
                    technology_stack=technology_stack or 'Tech Stack (Pending)'
                )
                db.session.add(sub)
            else:
                team.problem_submission.project_title = project_title
                team.problem_submission.domain = domain
                if problem_statement:
                    team.problem_submission.problem_statement = problem_statement
                if abstract:
                    team.problem_submission.abstract = abstract
                if technology_stack:
                    team.problem_submission.technology_stack = technology_stack
                    
        db.session.commit()
        log_organizer_activity("Edit Team", f"Updated/entered details for team {team.team_id}")
        flash('Team details updated successfully.', 'success')
        return redirect(url_for('organizer.view_teams'))
        
    return render_template('organizer/edit_team.html', team=team)


@organizer_bp.route('/rounds')
@login_required
def manage_rounds():
    if not check_organizer(): return redirect(url_for('auth.login'))
    return render_template('organizer/rounds.html')


@organizer_bp.route('/teams/toggle-lock/<team_id>', methods=['POST'])
@organizer_bp.route('/teams/unlock/<team_id>', methods=['POST'])
@login_required
def toggle_team_lock(team_id):
    if current_user.role not in ['Admin', 'Organizer']:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('auth.login'))
        
    sub = ProblemSubmission.query.filter_by(team_id=team_id).first()
    if sub:
        sub.is_locked = not sub.is_locked
        db.session.commit()
        state = "unlocked" if not sub.is_locked else "locked"
        flash(f"Team {team_id} project details have been successfully {state}.", "success")
        log_msg = f"Toggled lock state for team {team_id} project submission to {state}"
        try:
            log = ActivityLog(user_id=current_user.id, action="Toggle Project Lock", ip_address=request.remote_addr, details=log_msg)
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Log fail: {e}")
    else:
        flash("No problem statement has been submitted by this team yet.", "warning")
        
    ref = request.referrer
    if ref and ('admin/teams' in ref or 'organizer/teams' in ref):
        return redirect(ref)
    return redirect(url_for('organizer.view_teams'))

