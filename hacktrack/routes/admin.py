from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import os
import pandas as pd
import zipfile
from datetime import datetime

from database import db
from models import User, Team, TeamMember, Attendance, JudgeProfile, Round1Marks, Round2Marks, Round3Marks, FinalResult, ActivityLog, ProblemSubmission, SystemSetting, Certificate
from utils import export_to_excel, generate_pdf_report
from certificate_pdf import generate_pdf_certificate
import csv
import io

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def log_admin_activity(action, details=None):
    try:
        log = ActivityLog(user_id=current_user.id, action=action, ip_address=request.remote_addr, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging admin activity: {e}")

def check_admin():
    if current_user.role != 'Admin':
        flash('Unauthorized access!', 'danger')
        return False
    return True

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    total_teams = Team.query.count()
    total_students = TeamMember.query.count() + total_teams
    
    total_expected = Team.query.count()
    total_present = Attendance.query.filter_by(status='Present').count()
    attendance_rate = round((total_present / total_expected * 100), 2) if total_expected > 0 else 0.0
    
    r1_graded = db.session.query(Round1Marks.team_id).distinct().count()
    r2_graded = db.session.query(Round2Marks.team_id).distinct().count()
    r3_graded = db.session.query(Round3Marks.team_id).distinct().count()
    
    recent_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(8).all()
    
    # Domain Distribution: Query domain from ProblemSubmission join Team
    domains = db.session.query(ProblemSubmission.domain, db.func.count(Team.team_id))\
                        .join(Team, ProblemSubmission.team_id == Team.team_id)\
                        .group_by(ProblemSubmission.domain).all()
    domain_labels = [d[0] for d in domains]
    domain_counts = [d[1] for d in domains]
    
    return render_template(
        'admin/dashboard.html',
        total_teams=total_teams,
        total_students=total_students,
        attendance_rate=attendance_rate,
        r1_graded=r1_graded,
        r2_graded=r2_graded,
        r3_graded=r3_graded,
        recent_logs=recent_logs,
        domain_labels=domain_labels,
        domain_counts=domain_counts
    )

@admin_bp.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_user':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role')
            specialization = request.form.get('specialization', '').strip()
            
            if User.query.filter_by(email=email).first():
                flash('User with this email already exists.', 'danger')
            else:
                hashed_pw = generate_password_hash(password)
                new_user = User(name=name, email=email, password=hashed_pw, role=role)
                db.session.add(new_user)
                db.session.commit()
                
                if role == 'Judge':
                    judge_profile = JudgeProfile(user_id=new_user.id, specialization=specialization or 'General')
                    db.session.add(judge_profile)
                    db.session.commit()
                    
                log_admin_activity("Add User", f"Created user {name} as {role}")
                flash(f'{role} created successfully!', 'success')
                
        elif action == 'delete_user':
            user_id = request.form.get('user_id')
            user_to_del = User.query.get(user_id)
            if user_to_del and user_to_del.id != current_user.id:
                name = user_to_del.name
                role = user_to_del.role
                db.session.delete(user_to_del)
                db.session.commit()
                log_admin_activity("Delete User", f"Deleted user {name} ({role})")
                flash('User deleted successfully.', 'success')
            else:
                flash('Cannot delete user or self.', 'danger')
                
        return redirect(url_for('admin.manage_users'))
        
    organizers = User.query.filter_by(role='Organizer').all()
    judges = User.query.filter_by(role='Judge').all()
    return render_template('admin/users.html', organizers=organizers, judges=judges)

@admin_bp.route('/teams', methods=['GET', 'POST'])
@login_required
def manage_teams():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    search_query = request.args.get('search', '').strip()
    dept_filter = request.args.get('department', '').strip()
    college_filter = request.args.get('college', '').strip()
    domain_filter = request.args.get('domain', '').strip()
    attendance_filter = request.args.get('attendance', '').strip()
    
    query = Team.query
    
    if search_query:
        query = query.join(User, Team.leader_id == User.id, isouter=True)\
                     .join(TeamMember, Team.team_id == TeamMember.team_id, isouter=True)\
                     .join(ProblemSubmission, Team.team_id == ProblemSubmission.team_id, isouter=True)\
                     .filter(
                         (Team.team_name.like(f"%{search_query}%")) |
                         (Team.team_id.like(f"%{search_query}%")) |
                         (User.name.like(f"%{search_query}%")) |
                         (Team.college.like(f"%{search_query}%")) |
                         (ProblemSubmission.project_title.like(f"%{search_query}%")) |
                         (TeamMember.registration_number.like(f"%{search_query}%"))
                     ).distinct()
                     
    if dept_filter:
        query = query.filter(Team.department == dept_filter)
    if college_filter:
        query = query.filter(Team.college == college_filter)
    if domain_filter:
        query = query.join(ProblemSubmission).filter(ProblemSubmission.domain == domain_filter)
        
    if attendance_filter:
        if attendance_filter == 'Present':
            query = query.join(Attendance).filter(Attendance.status == 'Present')
        elif attendance_filter == 'Absent':
            query = query.join(Attendance).filter(Attendance.status == 'Absent')
            
    teams = query.all()
    
    departments = db.session.query(Team.department).distinct().all()
    colleges = db.session.query(Team.college).distinct().all()
    domains = db.session.query(ProblemSubmission.domain).distinct().all()
    
    return render_template(
        'admin/teams.html',
        teams=teams,
        departments=[d[0] for d in departments],
        colleges=[c[0] for c in colleges],
        domains=[dm[0] for dm in domains],
        search=search_query,
        selected_dept=dept_filter,
        selected_college=college_filter,
        selected_domain=domain_filter,
        selected_attendance=attendance_filter
    )

@admin_bp.route('/teams/edit/<team_id>', methods=['GET', 'POST'])
@login_required
def edit_team(team_id):
    if not check_admin(): return redirect(url_for('auth.login'))
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
        
        if project_title or domain or problem_statement:
            if not team.problem_submission:
                sub = ProblemSubmission(
                    team_id=team.team_id,
                    project_title=project_title,
                    domain=domain,
                    problem_statement=problem_statement,
                    abstract='Abstract Details (Pending)',
                    technology_stack='Tech Stack (Pending)'
                )
                db.session.add(sub)
            else:
                team.problem_submission.project_title = project_title
                team.problem_submission.domain = domain
                if problem_statement:
                    team.problem_submission.problem_statement = problem_statement
                    
        db.session.commit()
        log_admin_activity("Edit Team", f"Updated details for team {team.team_id}")
        flash('Team details updated successfully.', 'success')
        return redirect(url_for('admin.manage_teams'))
        
    return render_template('admin/edit_team.html', team=team)

@admin_bp.route('/teams/delete/<team_id>', methods=['POST'])
@login_required
def delete_team(team_id):
    if not check_admin(): return redirect(url_for('auth.login'))
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    team_name = team.team_name
    
    leader = User.query.get(team.leader_id)
    if leader:
        db.session.delete(leader)
        
    db.session.delete(team)
    db.session.commit()
    log_admin_activity("Delete Team", f"Removed team {team_id} ({team_name})")
    flash(f'Team {team_name} deleted successfully.', 'success')
    return redirect(url_for('admin.manage_teams'))

@admin_bp.route('/attendance')
@login_required
def view_attendance():
    if not check_admin(): return redirect(url_for('auth.login'))
    teams = Team.query.all()
    return render_template('admin/attendance.html', teams=teams)

@admin_bp.route('/leaderboard')
@login_required
def leaderboard():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    teams = Team.query.all()
    leaderboard_data = []
    
    for team in teams:
        r1_avg = db.session.query(db.func.avg(Round1Marks.total_marks)).filter(Round1Marks.team_id == team.team_id).scalar() or 0.0
        r2_avg = db.session.query(db.func.avg(Round2Marks.total_marks)).filter(Round2Marks.team_id == team.team_id).scalar() or 0.0
        r3_avg = db.session.query(db.func.avg(Round3Marks.total_marks)).filter(Round3Marks.team_id == team.team_id).scalar() or 0.0
        
        grand_total = r1_avg + r2_avg + r3_avg
        leader = User.query.get(team.leader_id)
        
        leaderboard_data.append({
            'team': team,
            'leader_name': leader.name if leader else 'N/A',
            'round1': round(r1_avg, 2),
            'round2': round(r2_avg, 2),
            'round3': round(r3_avg, 2),
            'grand_total': round(grand_total, 2)
        })
        
    leaderboard_data.sort(key=lambda x: x['grand_total'], reverse=True)
    
    for idx, item in enumerate(leaderboard_data):
        item['rank'] = idx + 1
        
    return render_template('admin/leaderboard.html', leaderboard=leaderboard_data)

@admin_bp.route('/declare-winners', methods=['POST'])
@login_required
def declare_winners():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    teams = Team.query.all()
    leaderboard_data = []
    
    for team in teams:
        r1_avg = db.session.query(db.func.avg(Round1Marks.total_marks)).filter(Round1Marks.team_id == team.team_id).scalar() or 0.0
        r2_avg = db.session.query(db.func.avg(Round2Marks.total_marks)).filter(Round2Marks.team_id == team.team_id).scalar() or 0.0
        r3_avg = db.session.query(db.func.avg(Round3Marks.total_marks)).filter(Round3Marks.team_id == team.team_id).scalar() or 0.0
        grand_total = r1_avg + r2_avg + r3_avg
        
        leaderboard_data.append({
            'team_id': team.team_id,
            'r1': r1_avg,
            'r2': r2_avg,
            'r3': r3_avg,
            'grand': grand_total
        })
        
    leaderboard_data.sort(key=lambda x: x['grand'], reverse=True)
    
    FinalResult.query.delete()
    for idx, item in enumerate(leaderboard_data):
        rank = idx + 1
        res = FinalResult(
            team_id=item['team_id'],
            round1_total=round(item['r1'], 2),
            round2_total=round(item['r2'], 2),
            round3_total=round(item['r3'], 2),
            grand_total=round(item['grand'], 2),
            rank=rank
        )
        db.session.add(res)
        
    db.session.commit()
    log_admin_activity("Declare Winners", "Rankings calculated and locked in final results")
    flash('Winners declared and final leaderboard locked successfully!', 'success')
    return redirect(url_for('admin.leaderboard'))

@admin_bp.route('/reports/export/<format_type>/<report_type>')
@login_required
def export_reports(format_type, report_type):
    if not check_admin(): return redirect(url_for('auth.login'))
    
    filename = f"{report_type}_report.{'xlsx' if format_type == 'excel' else 'pdf'}"
    filepath = os.path.join(current_app.config['EXPORT_FOLDER'], filename)
    
    title = ""
    headers = []
    data = []
    
    if report_type == 'attendance':
        title = "HackTrack - Attendance Report"
        headers = ["Team ID", "Team Name", "College", "Department", "Check-in Status", "Timestamp"]
        teams = Team.query.all()
        for t in teams:
            att = Attendance.query.filter_by(team_id=t.team_id).first()
            status = att.status if att else 'Absent'
            time_str = att.checkin_time.strftime('%Y-%m-%d %H:%M:%S') if att and att.checkin_time else 'N/A'
            data.append([t.team_id, t.team_name, t.college, t.department, status, time_str])
            
    elif report_type in ['round1', 'round2', 'round3']:
        round_num = report_type[-1]
        title = f"HackTrack - Round {round_num} Marks Report"
        
        if round_num == '1':
            headers = ["Team ID", "Team Name", "Judge", "Innovation (25)", "Presentation (25)", "Feasibility (25)", "Confidence (25)", "Total (100)", "Comments"]
            marks = Round1Marks.query.all()
            for m in marks:
                j = User.query.get(m.judge_id)
                t = Team.query.filter_by(team_id=m.team_id).first()
                if t:
                    data.append([t.team_id, t.team_name, j.name if j else 'N/A', m.innovation, m.presentation, m.feasibility, m.confidence, m.total_marks, m.comments or ''])
        elif round_num == '2':
            headers = ["Team ID", "Team Name", "Judge", "Prototype (30)", "Tech Imp (30)", "UI/UX (20)", "Q&A (20)", "Total (100)", "Comments"]
            marks = Round2Marks.query.all()
            for m in marks:
                j = User.query.get(m.judge_id)
                t = Team.query.filter_by(team_id=m.team_id).first()
                if t:
                    data.append([t.team_id, t.team_name, j.name if j else 'N/A', m.prototype, m.technical_implementation, m.uiux, m.question_answer, m.total_marks, m.comments or ''])
        elif round_num == '3':
            headers = ["Team ID", "Team Name", "Judge", "Demo (40)", "Business (20)", "Scalability (20)", "Presentation (20)", "Total (100)", "Comments"]
            marks = Round3Marks.query.all()
            for m in marks:
                j = User.query.get(m.judge_id)
                t = Team.query.filter_by(team_id=m.team_id).first()
                if t:
                    data.append([t.team_id, t.team_name, j.name if j else 'N/A', m.working_demo, m.business_model, m.scalability, m.presentation, m.total_marks, m.comments or ''])
                    
    elif report_type == 'final':
        title = "HackTrack - Final Evaluation Leaderboard"
        headers = ["Rank", "Team ID", "Team Name", "Leader", "College", "Round 1 (Avg)", "Round 2 (Avg)", "Round 3 (Avg)", "Grand Total"]
        results = FinalResult.query.order_by(FinalResult.rank.asc()).all()
        for r in results:
            t = Team.query.filter_by(team_id=r.team_id).first()
            leader = User.query.get(t.leader_id) if t else None
            if t:
                data.append([r.rank, t.team_id, t.team_name, leader.name if leader else 'N/A', t.college, r.round1_total, r.round2_total, r.round3_total, r.grand_total])
                
    elif report_type == 'winners':
        title = "HackTrack - Podium Finishers"
        headers = ["Rank", "Team ID", "Team Name", "Project Title", "Leader", "College", "Grand Total"]
        results = FinalResult.query.filter(FinalResult.rank <= 3).order_by(FinalResult.rank.asc()).all()
        for r in results:
            t = Team.query.filter_by(team_id=r.team_id).first()
            leader = User.query.get(t.leader_id) if t else None
            if t:
                proj_title = t.problem_submission.project_title if t.problem_submission else '—'
                data.append([r.rank, t.team_id, t.team_name, proj_title, leader.name if leader else 'N/A', t.college, r.grand_total])
                
    else:
        flash('Invalid report type.', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    if not data:
        flash('No data available to generate report.', 'warning')
        return redirect(url_for('admin.dashboard'))
        
    if format_type == 'excel':
        export_to_excel(data, headers, filepath)
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        generate_pdf_report(title, headers, data, filepath)
        mimetype = 'application/pdf'
        
    log_admin_activity("Export Report", f"Exported {report_type} report in {format_type} format")
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype=mimetype)

@admin_bp.route('/activity-logs')
@login_required
def view_logs():
    if not check_admin(): return redirect(url_for('auth.login'))
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    return render_template('admin/activity_logs.html', logs=logs)


def check_admin():
    return current_user.role == 'Admin'


@admin_bp.route('/certificates')
@login_required
def certificates():
    if not check_admin(): return redirect(url_for('auth.login'))
    certs = Certificate.query.order_by(Certificate.generated_time.desc()).all()
    teams = Team.query.all()
    
    # Load settings
    certs_enabled = SystemSetting.get_setting('certificates_enabled', 'False') == 'True'
    sig_path = SystemSetting.get_setting('organizer_signature_path', '')
    logo_path = SystemSetting.get_setting('college_logo_path', '')
    
    return render_template(
        'admin/certificates.html',
        certs=certs,
        teams=teams,
        certs_enabled=certs_enabled,
        sig_path=sig_path,
        logo_path=logo_path
    )


@admin_bp.route('/certificates/toggle', methods=['POST'])
@login_required
def toggle_certificates():
    if not check_admin(): return redirect(url_for('auth.login'))
    current_val = SystemSetting.get_setting('certificates_enabled', 'False')
    new_val = 'True' if current_val == 'False' else 'False'
    SystemSetting.set_setting('certificates_enabled', new_val)
    
    log_admin_activity("Toggle Certificates Generation", f"Toggled certificates state to {new_val}")
    flash(f"Certificate generation is now {'Enabled' if new_val == 'True' else 'Disabled'}.", "success")
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/certificates/upload-assets', methods=['POST'])
@login_required
def upload_certificate_assets():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    
    sig_file = request.files.get('signature_file')
    if sig_file and sig_file.filename:
        filename = "signature.png"
        path = os.path.join(uploads_dir, filename)
        sig_file.save(path)
        SystemSetting.set_setting('organizer_signature_path', path)
        flash('Digital signature uploaded successfully.', 'success')
        
    logo_file = request.files.get('logo_file')
    if logo_file and logo_file.filename:
        filename = "college_logo.png"
        path = os.path.join(uploads_dir, filename)
        logo_file.save(path)
        SystemSetting.set_setting('college_logo_path', path)
        flash('College logo uploaded successfully.', 'success')
        
    log_admin_activity("Upload Certificate Assets", "Uploaded signature/logo assets")
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/certificates/regenerate', methods=['POST'])
@login_required
def regenerate_all_certificates():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    certs = Certificate.query.all()
    sig_path = SystemSetting.get_setting('organizer_signature_path')
    logo_path = SystemSetting.get_setting('college_logo_path')
    
    for cert in certs:
        # Re-resolve paths and details
        full_path = os.path.join(current_app.root_path, 'static', cert.certificate_path)
        verification_url = f"{request.host_url.rstrip('/')}/verify-certificate/{cert.verification_token}"
        
        generate_pdf_certificate(
            cert_id=cert.certificate_id,
            student_name=cert.student_name,
            team_name=cert.team.team_name,
            project_title=cert.team.problem_submission.project_title if cert.team.problem_submission else "Hackathon Project",
            cert_type=cert.certificate_type,
            verification_url=verification_url,
            output_path=full_path,
            signature_path=sig_path,
            logo_path=logo_path
        )
        
    log_admin_activity("Regenerate Certificates", f"Regenerated {len(certs)} certificate PDFs with updated templates")
    flash(f"Successfully regenerated all {len(certs)} certificate PDFs.", "success")
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/certificates/export')
@login_required
def export_certificates_csv():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    certs = Certificate.query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow(['Certificate ID', 'Student Name', 'Registration Number', 'Team Name', 'Type', 'Generated At', 'Status', 'Email Sent'])
    
    for cert in certs:
        writer.writerow([
            cert.certificate_id,
            cert.student_name,
            cert.registration_number,
            cert.team.team_name,
            cert.certificate_type,
            cert.generated_time.strftime('%Y-%m-%d %H:%M:%S'),
            cert.certificate_status,
            'Yes' if cert.email_sent else 'No'
        ])
        
    output.seek(0)
    
    log_admin_activity("Export Certificates Records", "Exported CSV list of all certificate records")
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='certificates_registry.csv'
    )


@admin_bp.route('/certificates/release/<team_id>', methods=['POST'])
@login_required
def release_team_certificates(team_id):
    if not check_admin(): return redirect(url_for('auth.login'))
    certs = Certificate.query.filter_by(team_id=team_id).all()
    if not certs:
        # If no certs exist, let's auto-generate them now!
        team = Team.query.filter_by(team_id=team_id).first_or_404()
        from certificate_automation import auto_generate_team_certificates
        auto_generate_team_certificates(team)
        certs = Certificate.query.filter_by(team_id=team_id).all()
        
    for cert in certs:
        cert.certificate_status = 'RELEASED'
        cert.released_time = datetime.utcnow()
        cert.released_by = current_user.id
        
    db.session.commit()
    
    # Automatically send the email to the Team Leader with the certificates attached in a ZIP
    team = Team.query.filter_by(team_id=team_id).first()
    if team and team.leader:
        # Read files for attachment zipping
        attachments = []
        for cert in certs:
            full_path = os.path.join(current_app.root_path, 'static', cert.certificate_path)
            if os.path.exists(full_path):
                with open(full_path, 'rb') as f:
                    attachments.append((f"{cert.student_name}_Certificate.pdf", f.read()))
                    
        if attachments:
            email_body = f"""Dear Team Leader,

Congratulations! The certificates for your team '{team.team_name}' have been released.

Please find all team members' participation certificates attached in PDF format.

Regards,
HackTrack Organizing Committee"""
            
            from routes.leader import send_mock_email_with_attachments
            send_mock_email_with_attachments(
                to_email=team.leader.email,
                subject=f"Hackathon Certificates - Team {team.team_name}",
                body_text=email_body,
                attachments=attachments
            )
            
            for cert in certs:
                cert.email_sent = True
            db.session.commit()
            
    log_admin_activity("Release Certificates", f"Released certificates for team {team_id}")
    flash(f"Certificates for team {team_id} released and emailed successfully.", "success")
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/certificates/lock/<team_id>', methods=['POST'])
@login_required
def lock_team_certificates(team_id):
    if not check_admin(): return redirect(url_for('auth.login'))
    certs = Certificate.query.filter_by(team_id=team_id).all()
    for cert in certs:
        cert.certificate_status = 'LOCKED'
        cert.released_time = None
        cert.released_by = None
    db.session.commit()
    log_admin_activity("Lock Certificates", f"Locked certificates for team {team_id}")
    flash(f"Certificates for team {team_id} locked successfully.", "warning")
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/certificates/download-zip/<team_id>')
@login_required
def download_team_certificates_zip(team_id):
    if not check_admin(): return redirect(url_for('auth.login'))
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    certs = Certificate.query.filter_by(team_id=team_id).all()
    if not certs:
        flash('No certificates found for this team.', 'warning')
        return redirect(url_for('admin.certificates'))
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for cert in certs:
            full_path = os.path.join(current_app.root_path, 'static', cert.certificate_path)
            if os.path.exists(full_path):
                zipf.write(full_path, arcname=f"{cert.student_name}_Certificate.pdf")
                
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{team.team_name}_Certificates.zip"
    )


@admin_bp.route('/certificates/release-all', methods=['POST'])
@login_required
def release_all_certificates():
    if not check_admin(): return redirect(url_for('auth.login'))
    
    # Enable system-wide certificates setting
    SystemSetting.set_setting('certificates_enabled', 'True')
    
    # Fetch all certificates and mark them RELEASED
    certs = Certificate.query.all()
    for cert in certs:
        cert.certificate_status = 'RELEASED'
        if not cert.released_time:
            cert.released_time = datetime.utcnow()
            cert.released_by = current_user.id
            
    db.session.commit()
    
    log_admin_activity("Release All Certificates", "Approved and released all student certificates system-wide")
    flash("All certificates have been approved, released, and published successfully!", "success")
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/certificates/send-email/<team_id>', methods=['POST'])
@login_required
def send_team_certificates_email(team_id):
    if not check_admin(): return redirect(url_for('auth.login'))
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    certs = Certificate.query.filter_by(team_id=team_id).all()
    if not certs:
        # If no certs exist, let's auto-generate them now
        from certificate_automation import auto_generate_team_certificates
        auto_generate_team_certificates(team)
        certs = Certificate.query.filter_by(team_id=team_id).all()
        
    # Read files for attachment zipping
    attachments = []
    for cert in certs:
        full_path = os.path.join(current_app.root_path, 'static', cert.certificate_path)
        if os.path.exists(full_path):
            with open(full_path, 'rb') as f:
                attachments.append((f"{cert.student_name}_Certificate.pdf", f.read()))
                
    if attachments:
        email_body = f"""Dear Team Leader {team.leader.name},

Congratulations! The certificates for your team '{team.team_name}' have been generated and released.

Please find all team members' participation certificates attached in PDF format.

Regards,
HackTrack Organizing Committee"""
        
        try:
            from utils import send_mock_email_with_attachments
            send_mock_email_with_attachments(
                to_email=team.leader.email,
                subject=f"Hackathon Certificates - Team {team.team_name}",
                body_text=email_body,
                attachments=attachments
            )
        except Exception as e:
            print(f"Email send error (non-fatal): {e}")
        
        for cert in certs:
            cert.email_sent = True
        db.session.commit()
        
        log_admin_activity("Send Certificates Email", f"Manually emailed certificates to leader of team {team_id}")
        flash(f"Certificates successfully emailed to {team.leader.email} for team {team.team_name}!", "success")
    else:
        flash('No certificate PDF files found on disk to email.', 'danger')
        
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/certificates/download/<cert_id>')
@login_required
def download_certificate(cert_id):
    if not check_admin(): return redirect(url_for('auth.login'))
    cert = Certificate.query.get_or_404(cert_id)
    preview = request.args.get('preview', '0') == '1'
    full_path = os.path.normpath(os.path.join(current_app.root_path, 'static', cert.certificate_path))
    return send_file(
        full_path,
        mimetype='application/pdf',
        as_attachment=not preview,
        download_name=f"{cert.student_name}_Certificate.pdf" if not preview else None
    )

