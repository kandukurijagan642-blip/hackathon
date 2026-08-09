import os
import secrets
from flask import current_app, request
from database import db
from models import User, Certificate, FinalResult, SystemSetting
from certificate_pdf import generate_pdf_certificate

def get_unique_cert_id():
    """
    Generates a collision-resistant Certificate ID using a cryptographically
    random 4-byte hex suffix. Retries on the rare chance of a collision.
    Format: HC2026-XXXXXXXX  (e.g. HC2026-3A7F9C12)

    This replaces the previous count+1 approach which had a race condition:
    two concurrent registrations could both read count=100 and both try to
    insert HC2026-000101, causing one to fail with a primary-key collision.
    """
    for _ in range(10):  # Up to 10 retries — probability of collision is negligible
        candidate = f"HC2026-{secrets.token_hex(4).upper()}"
        if not Certificate.query.filter_by(certificate_id=candidate).first():
            return candidate
    # Extremely unlikely fallback: use full 8-byte hex for guaranteed uniqueness
    return f"HC2026-{secrets.token_hex(8).upper()}"

def auto_generate_team_certificates(team, cert_type='Participant'):
    """
    Called once at registration time to create LOCKED certificate rows
    for a team (Leader + Members). This is the ONLY path that creates
    Certificate rows -- ensure_certificates_ready() and quick_edit are
    disk-only helpers that never create new rows.

    Exceptions are logged but NOT re-raised -- a failed PDF generation
    should never roll back a completed registration.
    """
    try:
        # Idempotent: do nothing if certs already exist for this team
        existing = Certificate.query.filter_by(team_id=team.team_id).first()
        if existing:
            return

        sig_path = os.path.join(current_app.root_path, 'static', 'images', 'signature.png')
        logo_path = os.path.join(current_app.root_path, 'static', 'images', 'college_logo.png')

        try:
            host_url = request.host_url.rstrip('/')
        except Exception:
            host_url = "http://localhost:5000"

        # Ensure output directory exists
        os.makedirs(os.path.join(current_app.root_path, 'static', 'certificates'), exist_ok=True)

        # 1. Generate certificate for Team Leader
        leader_user = User.query.get(team.leader_id)
        leader_name = leader_user.name if leader_user else "Team Leader"

        leader_cert_id = get_unique_cert_id()
        leader_token = secrets.token_urlsafe(16)
        leader_pdf_filename = f"{leader_cert_id}.pdf"
        leader_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', leader_pdf_filename)

        verification_url = f"{host_url}/verify-certificate/{leader_token}"

        try:
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
        except Exception as pdf_err:
            print(f"[cert_automation] PDF generation failed for leader {leader_name}: {pdf_err}")

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
            released_time=None,
            released_by=None,
            verification_token=leader_token
        )
        db.session.add(leader_cert)
        db.session.commit()

        # 2. Generate certificates for each Team Member
        for member in team.members:
            m_cert_id = get_unique_cert_id()
            m_token = secrets.token_urlsafe(16)
            m_pdf_filename = f"{m_cert_id}.pdf"
            m_pdf_path = os.path.join(current_app.root_path, 'static', 'certificates', m_pdf_filename)

            m_verification_url = f"{host_url}/verify-certificate/{m_token}"

            try:
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
            except Exception as pdf_err:
                print(f"[cert_automation] PDF generation failed for member {member.student_name}: {pdf_err}")

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
                released_time=None,
                released_by=None,
                verification_token=m_token
            )
            db.session.add(m_cert)
            db.session.commit()

    except Exception as e:
        # Log the error but do NOT re-raise -- a cert generation failure must
        # never roll back a completed team registration.
        print(f"[cert_automation] ERROR generating certificates for team {team.team_id}: {e}")



