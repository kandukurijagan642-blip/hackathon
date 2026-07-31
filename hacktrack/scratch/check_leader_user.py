import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from models import User, Team

with app.app_context():
    u = User.query.filter_by(email="192472374@1").first()
    if u:
        print("Found User:", u.id, u.name, u.email, u.role)
        t = Team.query.filter_by(leader_id=u.id).first()
        if t:
            print("Found Team:", t.team_id, t.team_name, t.college)
            certs = t.certificates
            print(f"Team has {len(certs)} certificates.")
            for c in certs:
                print(f"  - {c.student_name} ({c.registration_number}): status={c.certificate_status}, path={c.certificate_path}")
        else:
            print("No team found for this user.")
    else:
        print("User 192472374@1 NOT found in database!")
