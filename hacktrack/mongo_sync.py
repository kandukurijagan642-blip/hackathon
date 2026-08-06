import os
from database import get_mongo_db, db
from models import User, Team, TeamMember, ProblemSubmission, Attendance, Round1Marks, Round2Marks, Round3Marks, FinalResult, SystemSetting
from werkzeug.security import generate_password_hash

def sync_all_to_mongo():
    """
    Export all teams, users, submissions, and marks from SQL database to MongoDB Atlas.
    """
    try:
        mongo = get_mongo_db()
        if mongo is None:
            return
            
        # 1. Sync Users
        users = User.query.all()
        user_docs = []
        for u in users:
            user_docs.append({
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'password': u.password,
                'role': u.role
            })
        if user_docs:
            mongo.users.delete_many({})
            mongo.users.insert_many(user_docs)

        # 2. Sync Teams and Members
        teams = Team.query.all()
        team_docs = []
        for t in teams:
            members = []
            for m in t.members:
                members.append({
                    'member_id': m.member_id,
                    'student_name': m.student_name,
                    'registration_number': m.registration_number,
                    'email': m.email,
                    'phone': m.phone
                })
            
            sub = t.problem_submission
            sub_dict = None
            if sub:
                sub_dict = {
                    'project_title': sub.project_title,
                    'domain': sub.domain,
                    'problem_statement': sub.problem_statement,
                    'abstract': sub.abstract,
                    'technology_stack': sub.technology_stack,
                    'github_url': sub.github_url,
                    'demo_url': sub.demo_url,
                    'is_locked': sub.is_locked
                }
                
            att = Attendance.query.filter_by(team_id=t.team_id).first()
            att_status = att.status if att else 'Absent'

            team_docs.append({
                'team_id': t.team_id,
                'team_name': t.team_name,
                'college': t.college,
                'department': t.department,
                'leader_id': t.leader_id,
                'members': members,
                'submission': sub_dict,
                'attendance': att_status
            })
            
        if team_docs:
            mongo.teams.delete_many({})
            mongo.teams.insert_many(team_docs)

        # 3. Sync Round 1, 2, 3 Marks
        r1_list = [{
            'team_id': r.team_id,
            'judge_id': r.judge_id,
            'innovation': r.innovation,
            'presentation': r.presentation,
            'feasibility': r.feasibility,
            'confidence': r.confidence,
            'comments': r.comments,
            'total_marks': r.total_marks,
            'is_submitted': r.is_submitted
        } for r in Round1Marks.query.all()]
        if r1_list:
            mongo.round1_marks.delete_many({})
            mongo.round1_marks.insert_many(r1_list)

        r2_list = [{
            'team_id': r.team_id,
            'judge_id': r.judge_id,
            'prototype': r.prototype,
            'technical_implementation': r.technical_implementation,
            'uiux': r.uiux,
            'question_answer': r.question_answer,
            'comments': r.comments,
            'total_marks': r.total_marks,
            'is_submitted': r.is_submitted
        } for r in Round2Marks.query.all()]
        if r2_list:
            mongo.round2_marks.delete_many({})
            mongo.round2_marks.insert_many(r2_list)

        r3_list = [{
            'team_id': r.team_id,
            'judge_id': r.judge_id,
            'working_demo': r.working_demo,
            'business_model': r.business_model,
            'scalability': r.scalability,
            'presentation': r.presentation,
            'comments': r.comments,
            'total_marks': r.total_marks,
            'is_submitted': r.is_submitted
        } for r in Round3Marks.query.all()]
        if r3_list:
            mongo.round3_marks.delete_many({})
            mongo.round3_marks.insert_many(r3_list)
            
        # 4. Sync System Settings
        settings = [{
            'key_name': s.key_name,
            'value': s.value
        } for s in SystemSetting.query.all()]
        if settings:
            mongo.system_settings.delete_many({})
            mongo.system_settings.insert_many(settings)

    except Exception as e:
        print(f"Error syncing data to MongoDB Atlas: {e}")

def restore_all_from_mongo(app, db):
    """
    Restore data from MongoDB Atlas into SQLite if SQL database is empty (e.g. after Render restart).
    """
    with app.app_context():
        try:
            mongo = get_mongo_db()
            if mongo is None:
                return

            # Check if MongoDB has teams and local SQLite is missing teams
            mongo_teams = list(mongo.teams.find({}))
            if not mongo_teams:
                return

            # Check local teams count
            sql_team_count = Team.query.count()
            if sql_team_count >= len(mongo_teams):
                return # SQL already has data

            print("Restoring dataset from MongoDB Atlas to SQL database...")
            
            # Restore Users
            mongo_users = list(mongo.users.find({}))
            for u_doc in mongo_users:
                if not User.query.filter_by(email=u_doc['email']).first():
                    u = User(
                        id=u_doc['id'],
                        name=u_doc['name'],
                        email=u_doc['email'],
                        password=u_doc['password'],
                        role=u_doc['role']
                    )
                    db.session.add(u)
            db.session.commit()

            # Restore Teams & Members
            for t_doc in mongo_teams:
                existing_team = Team.query.filter_by(team_id=t_doc['team_id']).first()
                if not existing_team:
                    t = Team(
                        team_id=t_doc['team_id'],
                        team_name=t_doc['team_name'],
                        college=t_doc['college'],
                        department=t_doc['department'],
                        leader_id=t_doc['leader_id']
                    )
                    db.session.add(t)
                    db.session.commit()

                    # Members
                    for m_doc in t_doc.get('members', []):
                        m = TeamMember(
                            team_id=t_doc['team_id'],
                            student_name=m_doc['student_name'],
                            registration_number=m_doc.get('registration_number', 'N/A'),
                            email=m_doc['email'],
                            phone=m_doc['phone']
                        )
                        db.session.add(m)

                    # Attendance
                    att = Attendance(team_id=t_doc['team_id'], status=t_doc.get('attendance', 'Absent'))
                    db.session.add(att)

                    # Problem Submission
                    sub_doc = t_doc.get('submission')
                    if sub_doc:
                        sub = ProblemSubmission(
                            team_id=t_doc['team_id'],
                            project_title=sub_doc.get('project_title', ''),
                            domain=sub_doc.get('domain', ''),
                            problem_statement=sub_doc.get('problem_statement', ''),
                            abstract=sub_doc.get('abstract', ''),
                            technology_stack=sub_doc.get('technology_stack', ''),
                            github_url=sub_doc.get('github_url', ''),
                            demo_url=sub_doc.get('demo_url', ''),
                            is_locked=sub_doc.get('is_locked', False)
                        )
                        db.session.add(sub)
                    db.session.commit()

            # Restore Round 1 Marks
            for r_doc in mongo.round1_marks.find({}):
                if not Round1Marks.query.filter_by(team_id=r_doc['team_id'], judge_id=r_doc['judge_id']).first():
                    r1 = Round1Marks(
                        team_id=r_doc['team_id'],
                        judge_id=r_doc['judge_id'],
                        innovation=r_doc.get('innovation', 0),
                        presentation=r_doc.get('presentation', 0),
                        feasibility=r_doc.get('feasibility', 0),
                        confidence=r_doc.get('confidence', 0),
                        comments=r_doc.get('comments', ''),
                        total_marks=r_doc.get('total_marks', 0),
                        is_submitted=r_doc.get('is_submitted', False)
                    )
                    db.session.add(r1)

            # Restore Round 2 Marks
            for r_doc in mongo.round2_marks.find({}):
                if not Round2Marks.query.filter_by(team_id=r_doc['team_id'], judge_id=r_doc['judge_id']).first():
                    r2 = Round2Marks(
                        team_id=r_doc['team_id'],
                        judge_id=r_doc['judge_id'],
                        prototype=r_doc.get('prototype', 0),
                        technical_implementation=r_doc.get('technical_implementation', 0),
                        uiux=r_doc.get('uiux', 0),
                        question_answer=r_doc.get('question_answer', 0),
                        comments=r_doc.get('comments', ''),
                        total_marks=r_doc.get('total_marks', 0),
                        is_submitted=r_doc.get('is_submitted', False)
                    )
                    db.session.add(r2)

            # Restore Round 3 Marks
            for r_doc in mongo.round3_marks.find({}):
                if not Round3Marks.query.filter_by(team_id=r_doc['team_id'], judge_id=r_doc['judge_id']).first():
                    r3 = Round3Marks(
                        team_id=r_doc['team_id'],
                        judge_id=r_doc['judge_id'],
                        working_demo=r_doc.get('working_demo', 0),
                        business_model=r_doc.get('business_model', 0),
                        scalability=r_doc.get('scalability', 0),
                        presentation=r_doc.get('presentation', 0),
                        comments=r_doc.get('comments', ''),
                        total_marks=r_doc.get('total_marks', 0),
                        is_submitted=r_doc.get('is_submitted', False)
                    )
                    db.session.add(r3)

            # Restore System Settings
            for s_doc in mongo.system_settings.find({}):
                if not SystemSetting.query.filter_by(key_name=s_doc['key_name']).first():
                    s = SystemSetting(key_name=s_doc['key_name'], value=s_doc['value'])
                    db.session.add(s)

            db.session.commit()
            print("Successfully restored database state from MongoDB Atlas!")
        except Exception as e:
            print(f"Error restoring from MongoDB Atlas: {e}")
