from flask import Flask, redirect, url_for
from flask_login import LoginManager, login_required
from werkzeug.security import generate_password_hash
import os

from config import Config
from database import db, create_database_if_not_exists
from models import User, JudgeProfile, Team, TeamMember, Attendance, FinalResult, SystemSetting, ProblemSubmission, Certificate

# 1. Create target MySQL Database if it does not exist
create_database_if_not_exists()

# 2. Instantiate Flask App
app = Flask(__name__)
app.config.from_object(Config)

# 3. Initialize SQLAlchemy database
db.init_app(app)

# 4. Setup Flask-Login session management
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 5. Register blueprints
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.organizer import organizer_bp
from routes.judge import judge_bp
from routes.leader import leader_bp
from routes.public import public_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(organizer_bp)
app.register_blueprint(judge_bp)
app.register_blueprint(leader_bp)
app.register_blueprint(public_bp)

# Root route redirection
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

@app.route('/quick-edit/<team_id>', methods=['GET', 'POST'])
def root_quick_edit(team_id):
    return redirect(url_for('leader.quick_edit', team_id=team_id))

@app.route('/certificates/preview/<cert_id>')
def preview_certificate(cert_id):
    from flask import render_template
    from flask_login import current_user
    cert = Certificate.query.get_or_404(cert_id)
    
    # Check if certificate system is enabled and cert is released
    certificates_active = (
        FinalResult.query.count() > 0 or 
        SystemSetting.get_setting('certificates_enabled', 'False') == 'True'
    )
    is_released = (cert.certificate_status == 'RELEASED') and certificates_active
    
    # Admins & Organizers can preview locked certs for inspection
    if current_user.is_authenticated and current_user.role in ['Admin', 'Organizer']:
        return render_template('certificate_preview.html', cert=cert)
        
    # If certificates are locked or system disabled, display locked notice
    if not is_released:
        return render_template('certificate_locked.html', cert=cert)
        
    return render_template('certificate_preview.html', cert=cert)

# Custom context processor to expose now and system settings helper in templates
@app.context_processor
def inject_globals():
    import datetime
    return {
        'now': datetime.datetime.utcnow(),
        'get_setting': SystemSetting.get_setting
    }

def seed_database():
    """
    Seeds initial system roles, default states, and a sample team.
    """
    try:
        # Seed default state variables
        SystemSetting.set_setting('problem_released', 'False')
        SystemSetting.set_setting('round1_enabled', 'False')
        SystemSetting.set_setting('round2_enabled', 'False')
        SystemSetting.set_setting('round3_enabled', 'False')
        
        # Check if Admin already exists
        admin = User.query.filter_by(role='Admin').first()
        if not admin:
            print("Seeding database with default accounts...")
            # 1. Create Super Admin
            admin_user = User(
                name='Super Admin',
                email='admin@hacktrack.com',
                password=generate_password_hash('Admin@123'),
                role='Admin'
            )
            db.session.add(admin_user)
            
            # 2. Create Event Organizer
            organizer_user = User(
                name='Organizer Team',
                email='organizer@hacktrack.com',
                password=generate_password_hash('Organizer@123'),
                role='Organizer'
            )
            db.session.add(organizer_user)
            
            # 3. Create Judges
            judge1 = User(
                name='Prof. Alan Turing',
                email='judge1@hacktrack.com',
                password=generate_password_hash('Judge@123'),
                role='Judge'
            )
            db.session.add(judge1)
            
            judge2 = User(
                name='Dr. Grace Hopper',
                email='judge2@hacktrack.com',
                password=generate_password_hash('Judge@123'),
                role='Judge'
            )
            db.session.add(judge2)
            db.session.commit()
            
            # Add judge specializations
            db.session.add(JudgeProfile(user_id=judge1.id, specialization='AI & Cyber Security'))
            db.session.add(JudgeProfile(user_id=judge2.id, specialization='Web3 & System Software'))
            
            # 4. Seed 10 default teams and their member rosters
            teams_data = [
                {
                    "name": "Web Wizards",
                    "leader": "Jane Doe",
                    "email": "jane.doe@mit.edu",
                    "college": "MIT",
                    "dept": "Information Technology",
                    "members": [
                        ("Alice Smith", "MIT2601", "alice@mit.edu", "+1 555-0101"),
                        ("Bob Jones", "MIT2602", "bob@mit.edu", "+1 555-0102"),
                        ("Charlie Brown", "MIT2603", "charlie@mit.edu", "+1 555-0103")
                    ],
                    "attendance": "Present",
                    "project": {
                        "title": "Decentralized Health Ledger",
                        "domain": "Healthcare & Blockchain",
                        "statement": "Integrate Web3 tech into electronic health records to secure access management."
                    }
                },
                {
                    "name": "Cyber Sentinels",
                    "leader": "John Smith",
                    "email": "leader2@hacktrack.com",
                    "college": "Stanford",
                    "dept": "Computer Science",
                    "members": [
                        ("David Miller", "STAN2601", "david@stanford.edu", "+1 555-0201"),
                        ("Emma Wilson", "STAN2602", "emma@stanford.edu", "+1 555-0202"),
                        ("Frank Thomas", "STAN2603", "frank@stanford.edu", "+1 555-0203")
                    ],
                    "attendance": "Present",
                    "project": {
                        "title": "AI Phishing Shield",
                        "domain": "Cyber Security",
                        "statement": "Real-time AI email filtering model to detect credential harvesting pages."
                    }
                },
                {
                    "name": "AI Pioneers",
                    "leader": "Sarah Connor",
                    "email": "leader3@hacktrack.com",
                    "college": "UC Berkeley",
                    "dept": "Data Science",
                    "members": [
                        ("Grace Hopper", "BERK2601", "grace@berkeley.edu", "+1 555-0301"),
                        ("Henry Ford", "BERK2602", "henry@berkeley.edu", "+1 555-0302"),
                        ("Ivy League", "BERK2603", "ivy@berkeley.edu", "+1 555-0303")
                    ],
                    "attendance": "Absent",
                    "project": {
                        "title": "Smart Crop Optimizer",
                        "domain": "Agriculture & ML",
                        "statement": "Predict soil nutrient deficiencies using computer vision on crop leaf images."
                    }
                },
                {
                    "name": "Code Crusaders",
                    "leader": "Bruce Wayne",
                    "email": "leader4@hacktrack.com",
                    "college": "Gotham Tech",
                    "dept": "Robotics Engineering",
                    "members": [
                        ("Jack Ryan", "GOT2601", "jack@gotham.edu", "+1 555-0401"),
                        ("Karen Page", "GOT2602", "karen@gotham.edu", "+1 555-0402"),
                        ("Leo Fitz", "GOT2603", "leo@gotham.edu", "+1 555-0403")
                    ],
                    "attendance": "Present",
                    "project": None
                },
                {
                    "name": "Cloud Knights",
                    "leader": "Clark Kent",
                    "email": "leader5@hacktrack.com",
                    "college": "Metropolis Univ",
                    "dept": "Cloud Infrastructure",
                    "members": [
                        ("Mary Jane", "MET2601", "mary@metropolis.edu", "+1 555-0501"),
                        ("Ned Leeds", "MET2602", "ned@metropolis.edu", "+1 555-0502"),
                        ("Oliver Queen", "MET2603", "oliver@metropolis.edu", "+1 555-0503")
                    ],
                    "attendance": "Absent",
                    "project": {
                        "title": "Kubernetes Resource Scaler",
                        "domain": "Cloud & DevOps",
                        "statement": "Dynamic cluster resource autoscaling algorithm based on deep network metrics."
                    }
                },
                {
                    "name": "Data Dynamos",
                    "leader": "Peter Parker",
                    "email": "leader6@hacktrack.com",
                    "college": "Empire State Univ",
                    "dept": "Applied Mathematics",
                    "members": [
                        ("Peggy Carter", "EMP2601", "peggy@empire.edu", "+1 555-0601"),
                        ("Quentin Beck", "EMP2602", "quentin@empire.edu", "+1 555-0602"),
                        ("Reed Richards", "EMP2603", "reed@empire.edu", "+1 555-0603")
                    ],
                    "attendance": "Present",
                    "project": {
                        "title": "Quantum Safe Encryption",
                        "domain": "Cryptography",
                        "statement": "Lattice-based signature library compiled to rust-wasm for browsers."
                    }
                },
                {
                    "name": "DevOps Dragons",
                    "leader": "Tony Stark",
                    "email": "leader7@hacktrack.com",
                    "college": "Stark Inst",
                    "dept": "Aerospace Engineering",
                    "members": [
                        ("Steve Rogers", "STK2601", "steve@stark.edu", "+1 555-0701"),
                        ("Sam Wilson", "STK2602", "sam@stark.edu", "+1 555-0702"),
                        ("Thor Odinson", "STK2603", "thor@stark.edu", "+1 555-0703")
                    ],
                    "attendance": "Present",
                    "project": None
                },
                {
                    "name": "Neural Ninjas",
                    "leader": "Barry Allen",
                    "email": "leader8@hacktrack.com",
                    "college": "Central City Univ",
                    "dept": "Bio-Physics",
                    "members": [
                        ("Wanda Maximoff", "CCU2601", "wanda@central.edu", "+1 555-0801"),
                        ("Vision Victor", "CCU2602", "vision@central.edu", "+1 555-0802"),
                        ("Natasha Romanoff", "CCU2603", "natasha@central.edu", "+1 555-0803")
                    ],
                    "attendance": "Absent",
                    "project": {
                        "title": "EEG Signal Classifier",
                        "domain": "Neural Engineering",
                        "statement": "Real-time brain signal categorization framework using 1D temporal CNNs."
                    }
                },
                {
                    "name": "App Avengers",
                    "leader": "Steve Jobs",
                    "email": "leader9@hacktrack.com",
                    "college": "Cupertino Design",
                    "dept": "Interaction Design",
                    "members": [
                        ("Clint Barton", "CUP2601", "clint@cupertino.edu", "+1 555-0901"),
                        ("Bruce Banner", "CUP2602", "bruce@cupertino.edu", "+1 555-0902"),
                        ("Loki Laufeyson", "CUP2603", "loki@cupertino.edu", "+1 555-0903")
                    ],
                    "attendance": "Present",
                    "project": {
                        "title": "Accessibility Mapping App",
                        "domain": "Mobile Development",
                        "statement": "Crowdsourced maps providing wheelchair accessibility route scoring in real-time."
                    }
                },
                {
                    "name": "IoT Innovators",
                    "leader": "Ada Lovelace",
                    "email": "leader10@hacktrack.com",
                    "college": "Oxford College",
                    "dept": "Mathematics & Computation",
                    "members": [
                        ("Charles Babbage", "OXF2601", "charles@oxford.edu", "+1 555-1001"),
                        ("Alan Turing", "OXF2602", "alan@oxford.edu", "+1 555-1002"),
                        ("John von Neumann", "OXF2603", "john@oxford.edu", "+1 555-1003")
                    ],
                    "attendance": "Present",
                    "project": None
                }
            ]

            from utils import generate_team_qr
            for idx, t_info in enumerate(teams_data):
                # 1. Seed Leader user account
                leader_user = User(
                    name=t_info["leader"],
                    email=t_info["email"],
                    password=generate_password_hash('192472374' if t_info["email"] == 'jane.doe@mit.edu' else f"{t_info['name'].replace(' ', '')}@12309"),
                    role='Leader'
                )
                db.session.add(leader_user)
                db.session.commit()
                
                # 2. Seed Team details
                team_id = f"HT2026{idx+1:03d}"
                team = Team(
                    team_id=team_id,
                    team_name=t_info["name"],
                    college=t_info["college"],
                    department=t_info["dept"],
                    leader_id=leader_user.id
                )
                db.session.add(team)
                db.session.commit()
                
                # 3. Seed initial Attendance
                db.session.add(Attendance(team_id=team.team_id, status=t_info["attendance"]))
                
                # 4. Seed members
                for m_name, m_reg, m_email, m_phone in t_info["members"]:
                    db.session.add(TeamMember(
                        team_id=team.team_id,
                        student_name=m_name,
                        registration_number=m_reg,
                        email=m_email,
                        phone=m_phone
                    ))
                db.session.commit()
                
                # 5. Seed Project details submission (if exists)
                if t_info["project"]:
                    p = t_info["project"]
                    sub = ProblemSubmission(
                        team_id=team.team_id,
                        project_title=p["title"],
                        domain=p["domain"],
                        problem_statement=p["statement"],
                        abstract="A placeholder abstract generated during database seeding.",
                        technology_stack="Python, Flask, SQLAlchemy, MySQL, Bootstrap"
                    )
                    db.session.add(sub)
                    db.session.commit()
                
                # 6. Generate QR Code image file
                base_url = os.environ.get('APP_BASE_URL', 'http://localhost:5000').rstrip('/')
                generate_team_qr(
                    team_id=team.team_id,
                    team_name=team.team_name,
                    leader_name=leader_user.name,
                    host_url=base_url
                )
                

            print("Database seeding completed. Admin, Organizer, Judges, and 10 default Teams seeded successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error seeding database: {e}")

# 6. Initialize database tables and seed
with app.app_context():
    try:
        if db.engine.name == 'mysql':
            with db.engine.connect() as conn:
                conn.execute(db.text("SET FOREIGN_KEY_CHECKS = 0;"))
                db.metadata.create_all(bind=conn)
                conn.execute(db.text("SET FOREIGN_KEY_CHECKS = 1;"))
                conn.commit()
        elif db.engine.name == 'sqlite':
            with db.engine.connect() as conn:
                conn.execute(db.text("PRAGMA foreign_keys = OFF;"))
                db.metadata.create_all(bind=conn)
                conn.execute(db.text("PRAGMA foreign_keys = ON;"))
                conn.commit()
        else:
            db.create_all()
        print("Database tables verified/created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        try:
            db.create_all()
        except Exception as ex:
            print(f"Fallback db.create_all error: {ex}")
        
    # Only seed default accounts if the user registry is empty
    try:
        if not User.query.first():
            seed_database()
    except Exception as e:
        print(f"Seeding check failed: {e}")
        try:
            db.create_all()
            if not User.query.first():
                seed_database()
        except Exception as ex:
            print(f"Retry seeding error: {ex}")

    # Regenerate QR codes using live base URL — only if file missing or base URL changed
    try:
        from utils import generate_team_qr, generate_registration_qr
        base_url = os.environ.get('APP_BASE_URL', 'http://localhost:5000').rstrip('/')
        stored_base_url = SystemSetting.get_setting('last_qr_base_url', '')
        url_changed = stored_base_url != base_url
        
        reg_qr_file = os.path.join(app.root_path, 'static', 'qrcodes', 'registration_qr.png')
        if not os.path.exists(reg_qr_file) or url_changed:
            generate_registration_qr(base_url)
            print(f"Main Registration QR generated/updated using: {base_url}")
            
        all_teams = Team.query.all()
        regenerated = 0
        for t in all_teams:
            qr_file = os.path.join(app.root_path, 'static', 'qrcodes', f'team_{t.team_id}_qr.png')
            if not os.path.exists(qr_file) or url_changed:
                leader_user = User.query.get(t.leader_id)
                generate_team_qr(
                    team_id=t.team_id,
                    team_name=t.team_name,
                    leader_name=leader_user.name if leader_user else 'Leader',
                    host_url=base_url
                )
                regenerated += 1
        if regenerated > 0:
            SystemSetting.set_setting('last_qr_base_url', base_url)
            db.session.commit()
            print(f"QR codes generated for {regenerated}/{len(all_teams)} teams using: {base_url}")
        else:
            print(f"All {len(all_teams)} QR codes are up to date.")
    except Exception as e:
        print(f"QR regeneration error: {e}")

@app.after_request
def add_security_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
