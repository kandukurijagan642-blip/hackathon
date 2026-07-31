from datetime import datetime
from flask_login import UserMixin
from database import db

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Admin, Organizer, Judge, Leader
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    judge_profile = db.relationship('JudgeProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    teams_led = db.relationship('Team', backref='leader', foreign_keys='Team.leader_id')
    round1_evaluations = db.relationship('Round1Marks', backref='judge', foreign_keys='Round1Marks.judge_id')
    round2_evaluations = db.relationship('Round2Marks', backref='judge', foreign_keys='Round2Marks.judge_id')
    round3_evaluations = db.relationship('Round3Marks', backref='judge', foreign_keys='Round3Marks.judge_id')
    activity_logs = db.relationship('ActivityLog', backref='user')

    def get_id(self):
        return str(self.id)


class Team(db.Model):
    __tablename__ = 'teams'
    
    team_id = db.Column(db.String(20), primary_key=True) # Custom ID format e.g. HT2026001
    team_name = db.Column(db.String(100), unique=True, nullable=False)
    college = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('TeamMember', backref='team', cascade="all, delete-orphan")
    attendance = db.relationship('Attendance', backref='team', cascade="all, delete-orphan")
    problem_submission = db.relationship('ProblemSubmission', backref='team', uselist=False, cascade="all, delete-orphan")
    round1_marks = db.relationship('Round1Marks', backref='team', cascade="all, delete-orphan")
    round2_marks = db.relationship('Round2Marks', backref='team', cascade="all, delete-orphan")
    round3_marks = db.relationship('Round3Marks', backref='team', cascade="all, delete-orphan")
    final_result = db.relationship('FinalResult', backref='team', uselist=False, cascade="all, delete-orphan")


class TeamMember(db.Model):
    __tablename__ = 'team_members'
    
    member_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(20), db.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    registration_number = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)


class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    attendance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(20), db.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='Absent')  # Present, Absent
    checkin_time = db.Column(db.DateTime, nullable=True)


class ProblemSubmission(db.Model):
    __tablename__ = 'problem_submission'
    
    submission_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(20), db.ForeignKey('teams.team_id', ondelete='CASCADE'), unique=True, nullable=False)
    project_title = db.Column(db.String(150), nullable=False)
    problem_statement = db.Column(db.Text, nullable=False)
    domain = db.Column(db.String(100), nullable=False)
    abstract = db.Column(db.Text, nullable=False)
    technology_stack = db.Column(db.Text, nullable=False)
    submission_time = db.Column(db.DateTime, default=datetime.utcnow)


class JudgeProfile(db.Model):
    __tablename__ = 'judges'
    
    judge_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    specialization = db.Column(db.String(150), nullable=False)


class Round1Marks(db.Model):
    __tablename__ = 'round1_marks'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(20), db.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False)
    judge_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    innovation = db.Column(db.Integer, default=0)
    presentation = db.Column(db.Integer, default=0)
    feasibility = db.Column(db.Integer, default=0)
    confidence = db.Column(db.Integer, default=0)
    
    comments = db.Column(db.Text, nullable=True)
    total_marks = db.Column(db.Integer, default=0)  # Calculated as sum: max 100
    is_submitted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Round2Marks(db.Model):
    __tablename__ = 'round2_marks'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(20), db.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False)
    judge_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    prototype = db.Column(db.Integer, default=0)
    technical_implementation = db.Column(db.Integer, default=0)
    uiux = db.Column(db.Integer, default=0)
    question_answer = db.Column(db.Integer, default=0)
    
    comments = db.Column(db.Text, nullable=True)
    total_marks = db.Column(db.Integer, default=0)  # Calculated as sum: max 100
    is_submitted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Round3Marks(db.Model):
    __tablename__ = 'round3_marks'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(20), db.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False)
    judge_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    working_demo = db.Column(db.Integer, default=0)
    business_model = db.Column(db.Integer, default=0)
    scalability = db.Column(db.Integer, default=0)
    presentation = db.Column(db.Integer, default=0)
    
    comments = db.Column(db.Text, nullable=True)
    total_marks = db.Column(db.Integer, default=0)  # Calculated as sum: max 100
    is_submitted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FinalResult(db.Model):
    __tablename__ = 'results'  # renamed from final_results to results to match the new database list
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.String(20), db.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False, unique=True)
    
    round1_total = db.Column(db.Float, default=0.0)
    round2_total = db.Column(db.Float, default=0.0)
    round3_total = db.Column(db.Float, default=0.0)
    
    grand_total = db.Column(db.Float, default=0.0)
    rank = db.Column(db.Integer, nullable=True)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45), nullable=True)
    details = db.Column(db.Text, nullable=True)


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    setting_key = db.Column(db.String(50), unique=True, nullable=False)
    setting_value = db.Column(db.String(255), nullable=False)
    
    _cache = {}  # In-memory cache to avoid repeated DB queries
    
    @classmethod
    def get_setting(cls, key, default=None):
        if key in cls._cache:
            return cls._cache[key]
        try:
            setting = cls.query.filter_by(setting_key=key).first()
            val = setting.setting_value if setting else default
            if val is not None:
                cls._cache[key] = val
            return val
        except Exception:
            return default

    @classmethod
    def set_setting(cls, key, value):
        try:
            setting = cls.query.filter_by(setting_key=key).first()
            if not setting:
                setting = cls(setting_key=key, setting_value=str(value))
                db.session.add(setting)
            else:
                setting.setting_value = str(value)
            db.session.commit()
            cls._cache[key] = str(value)  # Update cache
        except Exception as e:
            print(f"SystemSetting set error: {e}")


class Certificate(db.Model):
    __tablename__ = 'certificates'
    
    certificate_id = db.Column(db.String(50), primary_key=True) # Format: HC2026-000001
    team_id = db.Column(db.String(50), db.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('team_members.member_id', ondelete='CASCADE'), nullable=True) # null if leader
    student_name = db.Column(db.String(100), nullable=False)
    registration_number = db.Column(db.String(50), nullable=False)
    college_name = db.Column(db.String(150), nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    certificate_type = db.Column(db.String(50), default='Participant') # Participant, Winner, Finalist
    certificate_path = db.Column(db.String(255), nullable=True)
    certificate_status = db.Column(db.String(20), default='LOCKED') # LOCKED, RELEASED
    generated_time = db.Column(db.DateTime, default=datetime.utcnow)
    released_time = db.Column(db.DateTime, nullable=True)
    download_count = db.Column(db.Integer, default=0)
    verification_token = db.Column(db.String(100), unique=True, nullable=False)
    released_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    email_sent = db.Column(db.Boolean, default=False)
    
    team = db.relationship('Team', backref=db.backref('certificates', cascade='all, delete-orphan'))
    member = db.relationship('TeamMember', backref=db.backref('certificate', uselist=False, cascade='all, delete-orphan'))
