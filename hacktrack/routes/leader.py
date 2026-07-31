from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app, abort
from flask_login import login_required, current_user
import os

from database import db
from models import User, Team, TeamMember, Attendance, FinalResult, Round1Marks, Round2Marks, Round3Marks, ActivityLog, SystemSetting, ProblemSubmission, Certificate
from utils import generate_member_certificate, send_mock_email_with_attachments
from certificate_pdf import generate_pdf_certificate
import io
import zipfile
import secrets

leader_bp = Blueprint('leader', __name__, url_prefix='/leader')

def log_leader_activity(action, details=None):
    try:
        log = ActivityLog(user_id=current_user.id, action=action, ip_address=request.remote_addr, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging leader activity: {e}")

@leader_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'Leader':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('auth.login'))
        
    team = Team.query.filter_by(leader_id=current_user.id).first()
    if not team:
        flash('No team found for your user account.', 'warning')
        return render_template('leader/dashboard.html', team=None)
        
    # Attendance status
    att = Attendance.query.filter_by(team_id=team.team_id).first()
    attendance_status = att.status if att else 'Absent'
    checkin_time = att.checkin_time if att else None
    
    # Phase settings
    problem_released = (SystemSetting.get_setting('problem_released', 'False') == 'True')
    submission = ProblemSubmission.query.filter_by(team_id=team.team_id).first()
    
    # Marks / Evaluation Feedback (average scores across all evaluations)
    r1_marks = Round1Marks.query.filter_by(team_id=team.team_id).all()
    r2_marks = Round2Marks.query.filter_by(team_id=team.team_id).all()
    r3_marks = Round3Marks.query.filter_by(team_id=team.team_id).all()
    
    # Compute averages
    r1_avg = sum(m.total_marks for m in r1_marks) / len(r1_marks) if r1_marks else 0.0
    r2_avg = sum(m.total_marks for m in r2_marks) / len(r2_marks) if r2_marks else 0.0
    r3_avg = sum(m.total_marks for m in r3_marks) / len(r3_marks) if r3_marks else 0.0
    grand_total = r1_avg + r2_avg + r3_avg
    
    feedback = {
        'round1': [m.comments for m in r1_marks if m.comments],
        'round2': [m.comments for m in r2_marks if m.comments],
        'round3': [m.comments for m in r3_marks if m.comments],
    }
    
    # Rank check
    final_res = FinalResult.query.filter_by(team_id=team.team_id).first()
    rank = final_res.rank if final_res else None
    
    certificates_active = (
        FinalResult.query.count() > 0 or 
        SystemSetting.get_setting('certificates_enabled', 'False') == 'True'
    )
    
    certs = Certificate.query.filter_by(team_id=team.team_id).all()
    certs_generated = len(certs) > 0
    released = False
    if certs_generated and certs[0].certificate_status == 'RELEASED':
        released = True
        
    return render_template(
        'leader/dashboard.html',
        team=team,
        attendance_status=attendance_status,
        checkin_time=checkin_time,
        problem_released=problem_released,
        submission=submission,
        r1_avg=round(r1_avg, 2),
        r2_avg=round(r2_avg, 2),
        r3_avg=round(r3_avg, 2),
        grand_total=round(grand_total, 2),
        feedback=feedback,
        rank=rank,
        certificates_active=certificates_active,
        certs_generated=certs_generated,
        released=released
    )

@leader_bp.route('/submit-problem', methods=['GET', 'POST'])
@login_required
def submit_problem():
    if current_user.role != 'Leader':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('auth.login'))
        
    team = Team.query.filter_by(leader_id=current_user.id).first_or_404()
    
    # 1. Verify Phase 2 Release state
    problem_released = (SystemSetting.get_setting('problem_released', 'False') == 'True')
    if not problem_released:
        flash('The problem statement has not been released yet.', 'warning')
        return redirect(url_for('leader.dashboard'))
        
    # 2. Check if submission already exists
    submission = ProblemSubmission.query.filter_by(team_id=team.team_id).first()
    
    if request.method == 'POST':
        if submission:
            flash('Your project details have already been submitted and cannot be edited.', 'danger')
            return redirect(url_for('leader.dashboard'))
            
        project_title = request.form.get('project_title', '').strip()
        problem_statement = request.form.get('problem_statement', '').strip()
        domain = request.form.get('domain', '').strip()
        abstract = request.form.get('abstract', '').strip()
        technology_stack = request.form.get('technology_stack', '').strip()
        
        if not all([project_title, problem_statement, domain, abstract, technology_stack]):
            flash('Please fill in all the required submission details.', 'warning')
            return render_template('leader/submit_problem.html', team=team, submission=None)
            
        new_sub = ProblemSubmission(
            team_id=team.team_id,
            project_title=project_title,
            problem_statement=problem_statement,
            domain=domain,
            abstract=abstract,
            technology_stack=technology_stack
        )
        db.session.add(new_sub)
        db.session.commit()
        
        log_leader_activity("Submit Problem Statement", f"Submitted project details for {team.team_id} ({project_title})")
        flash('Submission Successful.', 'success')
        return redirect(url_for('leader.dashboard'))
        
    return render_template('leader/submit_problem.html', team=team, submission=submission)

@leader_bp.route('/download-certificate/<type>/<id>')
@login_required
def download_certificate(type, id):
    if current_user.role != 'Leader':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('auth.login'))
        
    team = Team.query.filter_by(leader_id=current_user.id).first()
    if not team:
        flash('Team not found.', 'danger')
        return redirect(url_for('leader.dashboard'))
        
    # Check attendance
    att = Attendance.query.filter_by(team_id=team.team_id).first()
    if not att or att.status != 'Present':
        flash('Attendance check-in is required before downloading certificates.', 'warning')
        return redirect(url_for('leader.dashboard'))
        
    final_res = FinalResult.query.filter_by(team_id=team.team_id).first()
    rank_text = None
    if final_res and final_res.rank in [1, 2, 3]:
        ranks = {1: '1st Place Winner', 2: '2nd Place Runner-Up', 3: '3rd Place Second Runner-Up'}
        rank_text = ranks[final_res.rank]
        
    recipient_name = ""
    # Ensure team_id strings compare correctly or integer conversion occurs
    if type == 'leader':
        if str(current_user.id) != str(id):
            flash('Access denied.', 'danger')
            return redirect(url_for('leader.dashboard'))
        recipient_name = current_user.name
    elif type == 'member':
        member = TeamMember.query.filter_by(member_id=int(id), team_id=team.team_id).first_or_404()
        recipient_name = member.student_name
    else:
        flash('Invalid certificate request.', 'danger')
        return redirect(url_for('leader.dashboard'))
        
    filename = f"cert_{recipient_name.lower().replace(' ', '_')}.pdf"
    filepath = os.path.join(current_app.config['EXPORT_FOLDER'], filename)
    
    # Load project title from submission if available, fallback to team metadata
    sub = ProblemSubmission.query.filter_by(team_id=team.team_id).first()
    proj_title = sub.project_title if sub else 'HackTrack Project'
    
    generate_member_certificate(
        team_name=team.team_name,
        project_title=proj_title,
        student_name=recipient_name,
        rank_text=rank_text,
        filepath=filepath
    )
    
    log_leader_activity("Download Certificate", f"Downloaded certificate for {recipient_name}")
    return send_file(filepath, as_attachment=True, download_name=f"{recipient_name}_Certificate.pdf")


@leader_bp.route('/quick-edit/<team_id>', methods=['GET', 'POST'])
def quick_edit(team_id):
    team = Team.query.filter_by(team_id=team_id).first_or_404()
        
    submission = ProblemSubmission.query.filter_by(team_id=team_id).first()
    
    # Check if certificates module is active (results published or enabled by admin)
    certificates_active = (
        FinalResult.query.count() > 0 or 
        SystemSetting.get_setting('certificates_enabled', 'False') == 'True'
    )
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # Public QR Generation trigger
        if action == 'generate_certs' and certificates_active:
            existing = Certificate.query.filter_by(team_id=team.team_id).first()
            if not existing:
                cert_type = "Participant"
                final_res = FinalResult.query.filter_by(team_id=team.team_id).first()
                if final_res:
                    if final_res.rank == 1:
                        cert_type = "Winner"
                    else:
                        cert_type = "Finalist"
                        
                sig_path = SystemSetting.get_setting('organizer_signature_path')
                logo_path = SystemSetting.get_setting('college_logo_path')
                
                # Create for Leader
                leader_user = User.query.get(team.leader_id)
                leader_name = leader_user.name if leader_user else "Team Leader"
                cert_count = Certificate.query.count()
                new_cert_num = cert_count + 1
                leader_cert_id = f"HC2026-{new_cert_num:06d}"
                leader_token = secrets.token_urlsafe(16)
                leader_pdf_filename = f"{leader_cert_id}.pdf"
                leader_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', leader_pdf_filename)
                
                verification_url = f"{request.host_url.rstrip('/')}/verify-certificate/{leader_token}"
                
                generate_pdf_certificate(
                    cert_id=leader_cert_id,
                    student_name=leader_name,
                    team_name=team.team_name,
                    project_title=submission.project_title if submission else "Hackathon Project",
                    cert_type=cert_type,
                    verification_url=verification_url,
                    output_path=leader_pdf_path,
                    signature_path=sig_path,
                    logo_path=logo_path
                )
                
                leader_cert = Certificate(
                    certificate_id=leader_cert_id,
                    team_id=team.team_id,
                    member_id=None,
                    student_name=leader_name,
                    registration_number=f"{team.team_id}-LDR",
                    college_name=team.college,
                    team_name=team.team_name,
                    certificate_type=cert_type,
                    certificate_path=f"certificates/{leader_pdf_filename}",
                    certificate_status='RELEASED',
                    verification_token=leader_token
                )
                db.session.add(leader_cert)
                db.session.commit()
                
                # Create for members
                for member in team.members:
                    cert_count = Certificate.query.count()
                    new_cert_num = cert_count + 1
                    m_cert_id = f"HC2026-{new_cert_num:06d}"
                    m_token = secrets.token_urlsafe(16)
                    m_pdf_filename = f"{m_cert_id}.pdf"
                    m_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', m_pdf_filename)
                    
                    m_verification_url = f"{request.host_url.rstrip('/')}/verify-certificate/{m_token}"
                    
                    generate_pdf_certificate(
                        cert_id=m_cert_id,
                        student_name=member.student_name,
                        team_name=team.team_name,
                        project_title=submission.project_title if submission else "Hackathon Project",
                        cert_type=cert_type,
                        verification_url=m_verification_url,
                        output_path=m_pdf_path,
                        signature_path=sig_path,
                        logo_path=logo_path
                    )
                    
                    m_cert = Certificate(
                        certificate_id=m_cert_id,
                        team_id=team.team_id,
                        member_id=member.member_id,
                        student_name=member.student_name,
                        registration_number=member.registration_number,
                        college_name=team.college,
                        team_name=team.team_name,
                        certificate_type=cert_type,
                        certificate_path=f"certificates/{m_pdf_filename}",
                        certificate_status='RELEASED',
                        verification_token=m_token
                    )
                    db.session.add(m_cert)
                    db.session.commit()
                    
                try:
                    log = ActivityLog(
                        user_id=None,
                        action="Generate Certificates (QR Link)",
                        ip_address=request.remote_addr,
                        details=f"Generated certificates for team {team.team_id} anonymously via QR code access."
                    )
                    db.session.add(log)
                    db.session.commit()
                except:
                    pass
                
                flash('Team certificates generated successfully!', 'success')
            return redirect(url_for('leader.quick_edit', team_id=team_id))
            
        if submission:
            flash('Your project details have already been submitted and locked. Editing is no longer permitted.', 'danger')
            return redirect(url_for('leader.quick_edit', team_id=team_id))
            
        project_title = request.form.get('project_title', '').strip()
        problem_statement = request.form.get('problem_statement', '').strip()
        domain = request.form.get('domain', '').strip()
        
        if not all([project_title, problem_statement, domain]):
            flash('All fields are required.', 'warning')
            return render_template(
                'leader/quick_edit.html',
                team=team,
                submission=submission,
                certificates_active=certificates_active,
                certs_generated=False,
                leader_cert=None,
                certs_by_member={}
            )
            
        # Create submission details (One-time submit lock)
        submission = ProblemSubmission(
            team_id=team_id,
            project_title=project_title,
            problem_statement=problem_statement,
            domain=domain,
            abstract='Abstract Details (Pending)',
            technology_stack='Tech Stack (Pending)'
        )
        db.session.add(submission)
        db.session.commit()
        
        try:
            log = ActivityLog(
                user_id=None,
                action="Quick Edit Team",
                ip_address=request.remote_addr,
                details=f"Anonymous update of team {team_id} details via QR shortcut."
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Log fail: {e}")
            
        flash('Team details and project submission updated successfully!', 'success')
        return redirect(url_for('leader.quick_edit', team_id=team_id))
        
    certs = Certificate.query.filter_by(team_id=team_id).all()
    certs_by_member = {c.member_id: c for c in certs if c.member_id is not None}
    leader_cert = next((c for c in certs if c.member_id is None), None)
    
    released = len(certs) > 0 and any(c.certificate_status == 'RELEASED' for c in certs)
        
    return render_template(
        'leader/quick_edit.html',
        team=team,
        submission=submission,
        certificates_active=certificates_active,
        certs_generated=len(certs) > 0,
        leader_cert=leader_cert,
        certs_by_member=certs_by_member,
        released=released
    )


@leader_bp.route('/certificates')
@login_required
def certificates():
    team = Team.query.filter_by(leader_id=current_user.id).first()
    if not team:
        flash('Unauthorized team access.', 'danger')
        return redirect(url_for('auth.login'))
        
    # Check if certificates module is active (results published or enabled by admin)
    certificates_active = (
        FinalResult.query.count() > 0 or 
        SystemSetting.get_setting('certificates_enabled', 'False') == 'True'
    )
    if not certificates_active:
        flash('Certificates will be available once the final leaderboard results are published by the organizer.', 'warning')
        return redirect(url_for('leader.dashboard'))
        
    # Fetch existing generated certificates for this team
    certs = Certificate.query.filter_by(team_id=team.team_id).all()
    certs_by_member = {c.member_id: c for c in certs if c.member_id is not None}
    leader_cert = next((c for c in certs if c.member_id is None), None)
    
    released = False
    if leader_cert and leader_cert.certificate_status == 'RELEASED':
        released = True
        
    return render_template(
        'leader/certificates.html',
        team=team,
        certs_by_member=certs_by_member,
        leader_cert=leader_cert,
        certs_generated=len(certs) > 0,
        released=released
    )


@leader_bp.route('/certificates/generate', methods=['POST'])
@login_required
def generate_certificates():
    team = Team.query.filter_by(leader_id=current_user.id).first()
    if not team:
        abort(403)
        
    # Check if already generated
    existing = Certificate.query.filter_by(team_id=team.team_id).first()
    if existing:
        flash('Certificates have already been generated for your team.', 'info')
        return redirect(url_for('leader.certificates'))
        
    # Determine certificate participation type based on rank
    cert_type = "Participant"
    final_res = FinalResult.query.filter_by(team_id=team.team_id).first()
    if final_res:
        if final_res.rank == 1:
            cert_type = "Winner"
        else:
            cert_type = "Finalist"
            
    # Load signature & logo paths if configured by admin
    sig_path = SystemSetting.get_setting('organizer_signature_path')
    logo_path = SystemSetting.get_setting('college_logo_path')
    
    # 1. Generate for Team Leader
    cert_count = Certificate.query.count()
    new_cert_num = cert_count + 1
    leader_cert_id = f"HC2026-{new_cert_num:06d}"
    leader_token = secrets.token_urlsafe(16)
    leader_pdf_filename = f"{leader_cert_id}.pdf"
    leader_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', leader_pdf_filename)
    
    verification_url = f"{request.host_url.rstrip('/')}/verify-certificate/{leader_token}"
    
    generate_pdf_certificate(
        cert_id=leader_cert_id,
        student_name=current_user.name,
        team_name=team.team_name,
        project_title=team.problem_submission.project_title if team.problem_submission else "Hackathon Project",
        cert_type=cert_type,
        verification_url=verification_url,
        output_path=leader_pdf_path,
        signature_path=sig_path,
        logo_path=logo_path
    )
    
    leader_cert = Certificate(
        certificate_id=leader_cert_id,
        team_id=team.team_id,
        member_id=None,
        student_name=current_user.name,
        registration_number=f"{team.team_id}-LDR",
        college_name=team.college,
        team_name=team.team_name,
        certificate_type=cert_type,
        certificate_path=f"certificates/{leader_pdf_filename}",
        certificate_status='RELEASED',
        verification_token=leader_token
    )
    db.session.add(leader_cert)
    db.session.commit()
    
    # 2. Generate for each Team Member
    for member in team.members:
        cert_count = Certificate.query.count()
        new_cert_num = cert_count + 1
        m_cert_id = f"HC2026-{new_cert_num:06d}"
        m_token = secrets.token_urlsafe(16)
        m_pdf_filename = f"{m_cert_id}.pdf"
        m_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', m_pdf_filename)
        
        m_verification_url = f"{request.host_url.rstrip('/')}/verify-certificate/{m_token}"
        
        generate_pdf_certificate(
            cert_id=m_cert_id,
            student_name=member.student_name,
            team_name=team.team_name,
            project_title=team.problem_submission.project_title if team.problem_submission else "Hackathon Project",
            cert_type=cert_type,
            verification_url=m_verification_url,
            output_path=m_pdf_path,
            signature_path=sig_path,
            logo_path=logo_path
        )
        
        m_cert = Certificate(
            certificate_id=m_cert_id,
            team_id=team.team_id,
            member_id=member.member_id,
            student_name=member.student_name,
            registration_number=member.registration_number,
            college_name=team.college,
            team_name=team.team_name,
            certificate_type=cert_type,
            certificate_path=f"certificates/{m_pdf_filename}",
            certificate_status='RELEASED',
            verification_token=m_token
        )
        db.session.add(m_cert)
        db.session.commit()
        
    log_leader_activity("Generate Certificates", f"Generated certificates for team {team.team_id}")
    flash('Certificates generated successfully!', 'success')
    return redirect(url_for('leader.certificates'))


@leader_bp.route('/certificates/download/<cert_id>')
@login_required
def download_team_certificate(cert_id):
    team = Team.query.filter_by(leader_id=current_user.id).first()
    if not team:
        abort(403)
        
    cert = Certificate.query.get_or_404(cert_id)
    if cert.team_id != team.team_id:
        abort(403)
        
    if cert.certificate_status != 'RELEASED':
        flash('Certificates have not been released by the organizer yet.', 'warning')
        return redirect(url_for('leader.certificates'))
        
    # Increment download count if not a preview request
    preview = request.args.get('preview', '0') == '1'
    if not preview:
        cert.download_count = (cert.download_count or 0) + 1
        db.session.commit()
    
    full_path = os.path.normpath(os.path.join(current_app.root_path, 'static', cert.certificate_path))
    return send_file(
        full_path,
        mimetype='application/pdf',
        as_attachment=not preview,
        download_name=f"{cert.student_name}_Certificate.pdf" if not preview else None
    )


@leader_bp.route('/certificates/download-all')
@login_required
def download_all_certificates():
    team = Team.query.filter_by(leader_id=current_user.id).first()
    if not team:
        abort(403)
        
    certs = Certificate.query.filter_by(team_id=team.team_id).all()
    if not certs:
        flash('No certificates found.', 'warning')
        return redirect(url_for('leader.certificates'))
        
    if certs[0].certificate_status != 'RELEASED':
        flash('Certificates have not been released by the organizer yet.', 'warning')
        return redirect(url_for('leader.certificates'))
        
    # Zip in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for cert in certs:
            full_path = os.path.join(current_app.root_path, 'static', cert.certificate_path)
            if os.path.exists(full_path):
                zipf.write(full_path, arcname=f"{cert.student_name}_Certificate.pdf")
                cert.download_count = (cert.download_count or 0) + 1
                
    db.session.commit()
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{team.team_name}_Certificates.zip"
    )


@leader_bp.route('/certificates/send-email', methods=['POST'])
@login_required
def send_certificates_email():
    team = Team.query.filter_by(leader_id=current_user.id).first()
    if not team:
        abort(403)
        
    certs = Certificate.query.filter_by(team_id=team.team_id).all()
    if not certs:
        flash('No certificates found.', 'warning')
        return redirect(url_for('leader.certificates'))
        
    if certs[0].certificate_status != 'RELEASED':
        flash('Certificates have not been released by the organizer yet.', 'warning')
        return redirect(url_for('leader.certificates'))
        
    # Read files for attachment zipping
    attachments = []
    for cert in certs:
        full_path = os.path.join(current_app.root_path, 'static', cert.certificate_path)
        if os.path.exists(full_path):
            with open(full_path, 'rb') as f:
                attachments.append((f"{cert.student_name}_Certificate.pdf", f.read()))
                
    # Create ZIP of all PDFs
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for name, data in attachments:
            zipf.writestr(name, data)
    zip_buffer.seek(0)
    
    email_body = f"""Dear Team Leader,

Congratulations on participating in the Hackathon.

Attached are the participation certificates for all members of your team.

Thank you for participating.

Regards,
Hackathon Organizing Committee"""

    email_attachments = attachments + [(f"{team.team_name}_Certificates.zip", zip_buffer.getvalue())]
    
    send_mock_email_with_attachments(
        to_email=current_user.email,
        subject="Hackathon Certificates",
        body_text=email_body,
        attachments=email_attachments
    )
    
    for cert in certs:
        cert.email_sent = True
    db.session.commit()
    
    log_leader_activity("Send Certificates Email", f"Dispatched certificates email to {current_user.email}")
    flash('Certificates sent to leader email successfully!', 'success')
    return redirect(url_for('leader.certificates'))


@leader_bp.route('/certificates/public-download/<cert_id>')
def public_download_certificate(cert_id):
    cert = Certificate.query.get_or_404(cert_id)
    if cert.certificate_status != 'RELEASED':
        abort(403)
        
    preview = request.args.get('preview', '0') == '1'
    if not preview:
        cert.download_count = (cert.download_count or 0) + 1
        db.session.commit()
    
    full_path = os.path.normpath(os.path.join(current_app.root_path, 'static', cert.certificate_path))
    return send_file(
        full_path,
        mimetype='application/pdf',
        as_attachment=not preview,
        download_name=f"{cert.student_name}_Certificate.pdf" if not preview else None
    )


@leader_bp.route('/certificates/public-download-all/<team_id>')
def public_download_all_certificates(team_id):
    team = Team.query.get_or_404(team_id)
    certs = Certificate.query.filter_by(team_id=team.team_id).all()
    if not certs:
        abort(404)
        
    if certs[0].certificate_status != 'RELEASED':
        abort(403)
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for cert in certs:
            full_path = os.path.join(current_app.root_path, 'static', cert.certificate_path)
            if os.path.exists(full_path):
                zipf.write(full_path, arcname=f"{cert.student_name}_Certificate.pdf")
                cert.download_count = (cert.download_count or 0) + 1
                
    db.session.commit()
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{team.team_name}_Certificates.zip"
    )


