import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from models import User
from database import db

with app.app_context():
    u = User.query.filter_by(email="192472374@1").first()
    if u:
        u.email = "jane.doe@mit.edu"
        db.session.commit()
        print("Updated existing user email from 192472374@1 to jane.doe@mit.edu successfully.")
    else:
        print("User 192472374@1 not found (already updated).")
