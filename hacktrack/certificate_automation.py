import os
import secrets
from flask import current_app, request
from database import db
from models import User, Certificate, FinalResult, SystemSetting
from certificate_pdf import generate_pdf_certificate

def auto_generate_team_certificates(team):
    """
    Generates and saves LOCKED certificate records and PDF files for the team leader and members.
    Can be run dynamically in the request context after registration.
    """
    # Check if already generated
    existing = Certificate.query.filter_by(team_id=team.team_id).first()
    if existing:
        return
        
    # Default to Participant (will be updated if leaderboard ranks are published later)
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
    
    try:
        host_url = request.host_url.rstrip('/')
    except:
        host_url = "http://localhost:5000"
        
    # Ensure output directory exists
    os.makedirs(os.path.join(current_app.root_path, 'static', 'certificates'), exist_ok=True)

    # 1. Generate for Team Leader
    leader_user = User.query.get(team.leader_id)
    leader_name = leader_user.name if leader_user else "Team Leader"
    
    cert_count = Certificate.query.count()
    new_cert_num = cert_count + 1
    leader_cert_id = f"HC2026-{new_cert_num:06d}"
    leader_token = secrets.token_urlsafe(16)
    leader_pdf_filename = f"{leader_cert_id}.pdf"
    leader_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', leader_pdf_filename)
    
    verification_url = f"{host_url}/verify-certificate/{leader_token}"
    
    generate_pdf_certificate(
        cert_id=leader_cert_id,
        student_name=leader_name,
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
        student_name=leader_name,
        registration_number=f"{team.team_id}-LDR",
        college_name=team.college,
        team_name=team.team_name,
        certificate_type=cert_type,
        certificate_path=f"certificates/{leader_pdf_filename}",
        certificate_status='LOCKED',
        verification_token=leader_token
    )
    db.session.add(leader_cert)
    
    # 2. Generate for each Team Member
    for member in team.members:
        cert_count = Certificate.query.count()
        new_cert_num = cert_count + 1
        m_cert_id = f"HC2026-{new_cert_num:06d}"
        m_token = secrets.token_urlsafe(16)
        m_pdf_filename = f"{m_cert_id}.pdf"
        m_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', m_pdf_filename)
        
        m_verification_url = f"{host_url}/verify-certificate/{m_token}"
        
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
            certificate_status='LOCKED',
            verification_token=m_token
        )
        db.session.add(m_cert)
        
    db.session.commit()
