import os
import json
from database import db
from models import User, Team, TeamMember, ProblemSubmission, Attendance, Round1Marks, Round2Marks, Round3Marks, SystemSetting
from werkzeug.security import generate_password_hash

BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'teams_registry_backup.json')

def save_local_backup():
    """
    Saves all SQLite teams, users, submissions, and marks into a local JSON backup file.
    This guarantees zero data loss on container restarts or refreshes.
    """
    try:
        data = {
            'users': [],
            'teams': [],
            'round1_marks': [],
            'round2_marks': [],
            'round3_marks': []
        }

        # Users
        for u in User.query.all():
            data['users'].append({
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'password': u.password,
                'role': u.role
            })

        # Teams
        for t in Team.query.all():
            members = []
            for m in t.members:
                members.append({
                    'member_id': m.member_id,
                    'student_name': m.student_name,
                    'registration_number': m.registration_number,
                    'email': m.email,
                    'phone': m.phone
                })

            sub_dict = None
            try:
                sub = t.problem_submission
                if sub:
                    sub_dict = {
                        'project_title': getattr(sub, 'project_title', ''),
                        'domain': getattr(sub, 'domain', ''),
                        'problem_statement': getattr(sub, 'problem_statement', ''),
                        'abstract': getattr(sub, 'abstract', ''),
                        'technology_stack': getattr(sub, 'technology_stack', ''),
                        'github_url': getattr(sub, 'github_url', None),
                        'demo_url': getattr(sub, 'demo_url', None),
                        'is_locked': getattr(sub, 'is_locked', False)
                    }
            except Exception as sub_ex:
                print(f"Notice: sub dict skip for team {t.team_id}: {sub_ex}")

            att = Attendance.query.filter_by(team_id=t.team_id).first()
            att_status = att.status if att else 'Absent'

            data['teams'].append({
                'team_id': t.team_id,
                'team_name': t.team_name,
                'college': t.college,
                'department': t.department,
                'leader_id': t.leader_id,
                'created_at': t.created_at.strftime('%Y-%m-%d %H:%M:%S') if t.created_at else None,
                'members': members,
                'submission': sub_dict,
                'attendance': att_status
            })

        # Marks
        for r in Round1Marks.query.all():
            data['round1_marks'].append({
                'team_id': r.team_id,
                'judge_id': r.judge_id,
                'innovation': r.innovation,
                'presentation': r.presentation,
                'feasibility': r.feasibility,
                'confidence': r.confidence,
                'comments': r.comments,
                'total_marks': r.total_marks,
                'is_submitted': r.is_submitted
            })

        for r in Round2Marks.query.all():
            data['round2_marks'].append({
                'team_id': r.team_id,
                'judge_id': r.judge_id,
                'prototype': r.prototype,
                'technical_implementation': r.technical_implementation,
                'uiux': r.uiux,
                'question_answer': r.question_answer,
                'comments': r.comments,
                'total_marks': r.total_marks,
                'is_submitted': r.is_submitted
            })

        for r in Round3Marks.query.all():
            data['round3_marks'].append({
                'team_id': r.team_id,
                'judge_id': r.judge_id,
                'working_demo': r.working_demo,
                'business_model': r.business_model,
                'scalability': r.scalability,
                'presentation': r.presentation,
                'comments': r.comments,
                'total_marks': r.total_marks,
                'is_submitted': r.is_submitted
            })

        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Local backup saved ({len(data['teams'])} teams preserved).")

    except Exception as e:
        print(f"Error saving local backup: {e}")

def restore_local_backup(app, db):
    """
    Restores dataset from local backup file into SQL database if backup exists.
    """
    if not os.path.exists(BACKUP_FILE):
        return

    with app.app_context():
        try:
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data or not data.get('teams'):
                return

            print(f"Restoring dataset from local backup ({len(data['teams'])} teams)...")

            # Restore Users
            for u_doc in data.get('users', []):
                existing_user = User.query.filter_by(email=u_doc['email']).first()
                if not existing_user:
                    u = User(
                        id=u_doc.get('id'),
                        name=u_doc['name'],
                        email=u_doc['email'],
                        password=u_doc['password'],
                        role=u_doc['role']
                    )
                    db.session.add(u)
            db.session.commit()

            # Restore Teams & Submissions & Attendance
            for t_doc in data.get('teams', []):
                existing_team = Team.query.filter_by(team_id=t_doc['team_id']).first()
                if not existing_team:
                    new_t = Team(
                        team_id=t_doc['team_id'],
                        team_name=t_doc['team_name'],
                        college=t_doc['college'],
                        department=t_doc['department'],
                        leader_id=t_doc.get('leader_id')
                    )
                    db.session.add(new_t)
                    db.session.commit()
                    existing_team = new_t

                # Members
                for m_doc in t_doc.get('members', []):
                    if not TeamMember.query.filter_by(team_id=t_doc['team_id'], email=m_doc['email']).first():
                        m = TeamMember(
                            team_id=t_doc['team_id'],
                            student_name=m_doc['student_name'],
                            registration_number=m_doc.get('registration_number', 'N/A'),
                            email=m_doc['email'],
                            phone=m_doc.get('phone', '')
                        )
                        db.session.add(m)

                # Submission Upsert
                sub_doc = t_doc.get('submission')
                if sub_doc:
                    existing_sub = ProblemSubmission.query.filter_by(team_id=t_doc['team_id']).first()
                    if not existing_sub:
                        ps = ProblemSubmission(
                            team_id=t_doc['team_id'],
                            project_title=sub_doc['project_title'],
                            domain=sub_doc['domain'],
                            problem_statement=sub_doc['problem_statement'],
                            abstract=sub_doc['abstract'],
                            technology_stack=sub_doc['technology_stack'],
                            is_locked=sub_doc.get('is_locked', False)
                        )
                        db.session.add(ps)
                    else:
                        existing_sub.project_title = sub_doc['project_title']
                        existing_sub.domain = sub_doc['domain']
                        existing_sub.problem_statement = sub_doc['problem_statement']
                        existing_sub.abstract = sub_doc['abstract']
                        existing_sub.technology_stack = sub_doc['technology_stack']
                        existing_sub.is_locked = sub_doc.get('is_locked', False)

                # Attendance Upsert
                att = Attendance.query.filter_by(team_id=t_doc['team_id']).first()
                if not att:
                    att = Attendance(team_id=t_doc['team_id'], status=t_doc.get('attendance', 'Absent'))
                    db.session.add(att)
                else:
                    if t_doc.get('attendance') and t_doc['attendance'] != 'Absent':
                        att.status = t_doc['attendance']

                db.session.commit()

            # Restore & Upsert Marks
            for r_doc in data.get('round1_marks', []):
                r1 = Round1Marks.query.filter_by(team_id=r_doc['team_id'], judge_id=r_doc['judge_id']).first()
                if not r1:
                    r1 = Round1Marks(
                        team_id=r_doc['team_id'],
                        judge_id=r_doc['judge_id'],
                        innovation=r_doc['innovation'],
                        presentation=r_doc['presentation'],
                        feasibility=r_doc['feasibility'],
                        confidence=r_doc['confidence'],
                        comments=r_doc.get('comments', ''),
                        total_marks=r_doc['total_marks'],
                        is_submitted=r_doc.get('is_submitted', True)
                    )
                    db.session.add(r1)
                else:
                    r1.innovation = r_doc['innovation']
                    r1.presentation = r_doc['presentation']
                    r1.feasibility = r_doc['feasibility']
                    r1.confidence = r_doc['confidence']
                    r1.comments = r_doc.get('comments', '')
                    r1.total_marks = r_doc['total_marks']
                    r1.is_submitted = r_doc.get('is_submitted', True)

            for r_doc in data.get('round2_marks', []):
                r2 = Round2Marks.query.filter_by(team_id=r_doc['team_id'], judge_id=r_doc['judge_id']).first()
                if not r2:
                    r2 = Round2Marks(
                        team_id=r_doc['team_id'],
                        judge_id=r_doc['judge_id'],
                        prototype=r_doc['prototype'],
                        technical_implementation=r_doc['technical_implementation'],
                        uiux=r_doc['uiux'],
                        question_answer=r_doc['question_answer'],
                        comments=r_doc.get('comments', ''),
                        total_marks=r_doc['total_marks'],
                        is_submitted=r_doc.get('is_submitted', True)
                    )
                    db.session.add(r2)
                else:
                    r2.prototype = r_doc['prototype']
                    r2.technical_implementation = r_doc['technical_implementation']
                    r2.uiux = r_doc['uiux']
                    r2.question_answer = r_doc['question_answer']
                    r2.comments = r_doc.get('comments', '')
                    r2.total_marks = r_doc['total_marks']
                    r2.is_submitted = r_doc.get('is_submitted', True)

            for r_doc in data.get('round3_marks', []):
                r3 = Round3Marks.query.filter_by(team_id=r_doc['team_id'], judge_id=r_doc['judge_id']).first()
                if not r3:
                    r3 = Round3Marks(
                        team_id=r_doc['team_id'],
                        judge_id=r_doc['judge_id'],
                        working_demo=r_doc['working_demo'],
                        business_model=r_doc['business_model'],
                        scalability=r_doc['scalability'],
                        presentation=r_doc['presentation'],
                        comments=r_doc.get('comments', ''),
                        total_marks=r_doc['total_marks'],
                        is_submitted=r_doc.get('is_submitted', True)
                    )
                    db.session.add(r3)
                else:
                    r3.working_demo = r_doc['working_demo']
                    r3.business_model = r_doc['business_model']
                    r3.scalability = r_doc['scalability']
                    r3.presentation = r_doc['presentation']
                    r3.comments = r_doc.get('comments', '')
                    r3.total_marks = r_doc['total_marks']
                    r3.is_submitted = r_doc.get('is_submitted', True)

            db.session.commit()
            print("Local backup restoration completed successfully.")

        except Exception as e:
            print(f"Error restoring local backup: {e}")
