import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from models import Certificate, Team
from database import db

with app.app_context():
    # Find Web Wizards team
    team = Team.query.filter_by(team_name="Web Wizards").first()
    if not team:
        print("Team Web Wizards not found!")
        sys.exit(1)
        
    print(f"Initial state of Web Wizards certificates:")
    for c in team.certificates:
        print(f"  - {c.student_name}: {c.certificate_status}")
        
    # Simulate release
    print("Releasing certificates...")
    for c in team.certificates:
        c.certificate_status = 'RELEASED'
    db.session.commit()
    
    # Query again to confirm
    db.session.expire_all()
    team = Team.query.filter_by(team_name="Web Wizards").first()
    print("State after release commit:")
    for c in team.certificates:
        print(f"  - {c.student_name}: {c.certificate_status}")
