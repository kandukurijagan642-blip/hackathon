from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
import datetime

from database import db
from models import User, Team, Round1Marks, Round2Marks, Round3Marks, ActivityLog, SystemSetting

judge_bp = Blueprint('judge', __name__, url_prefix='/judge')

def log_judge_activity(action, details=None):
    try:
        log = ActivityLog(user_id=current_user.id, action=action, ip_address=request.remote_addr, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging judge activity: {e}")

def check_judge():
    if current_user.role not in ['Admin', 'Judge']:
        flash('Unauthorized access!', 'danger')
        return False
    return True

@judge_bp.route('/dashboard')
@login_required
def dashboard():
    if not check_judge(): return redirect(url_for('auth.login'))
    
    teams = Team.query.all()
    
    # Check settings
    r1_active = (SystemSetting.get_setting('round1_enabled', 'False') == 'True')
    r2_active = (SystemSetting.get_setting('round2_enabled', 'False') == 'True')
    r3_active = (SystemSetting.get_setting('round3_enabled', 'False') == 'True')
    
    evaluated_teams = []
    for team in teams:
        r1 = Round1Marks.query.filter_by(team_id=team.team_id, judge_id=current_user.id).first()
        r2 = Round2Marks.query.filter_by(team_id=team.team_id, judge_id=current_user.id).first()
        r3 = Round3Marks.query.filter_by(team_id=team.team_id, judge_id=current_user.id).first()
        
        # Check if project has submitted problem details (Phased workflow)
        is_submitted = (team.problem_submission is not None)
        
        evaluated_teams.append({
            'team': team,
            'is_submitted': is_submitted,
            'r1_status': 'Finalized' if r1 and r1.is_submitted else ('Draft' if r1 else 'Not Evaluated'),
            'r1_score': r1.total_marks if r1 else '-',
            'r2_status': 'Finalized' if r2 and r2.is_submitted else ('Draft' if r2 else 'Not Evaluated'),
            'r2_score': r2.total_marks if r2 else '-',
            'r3_status': 'Finalized' if r3 and r3.is_submitted else ('Draft' if r3 else 'Not Evaluated'),
            'r3_score': r3.total_marks if r3 else '-'
        })
        
    return render_template(
        'judge/dashboard.html',
        evaluated_teams=evaluated_teams,
        r1_active=r1_active,
        r2_active=r2_active,
        r3_active=r3_active
    )

@judge_bp.route('/evaluate/<int:round_num>/<team_id>', methods=['GET', 'POST'])
@login_required
def evaluate(round_num, team_id):
    if not check_judge(): return redirect(url_for('auth.login'))
    if round_num not in [1, 2, 3]:
        flash('Invalid evaluation round.', 'danger')
        return redirect(url_for('judge.dashboard'))
        
    # Check if the Organizer has enabled evaluations for this round
    active_key = f"round{round_num}_enabled"
    if SystemSetting.get_setting(active_key, 'False') == 'False':
        flash(f'Round {round_num} Jury evaluation is not enabled yet by the organizer.', 'warning')
        return redirect(url_for('judge.dashboard'))
        
    team = Team.query.filter_by(team_id=team_id).first_or_404()
    
    # Retrieve existing marks
    if round_num == 1:
        marks = Round1Marks.query.filter_by(team_id=team_id, judge_id=current_user.id).first()
    elif round_num == 2:
        marks = Round2Marks.query.filter_by(team_id=team_id, judge_id=current_user.id).first()
    else:
        marks = Round3Marks.query.filter_by(team_id=team_id, judge_id=current_user.id).first()
        
    # Check lock mechanism: Cannot edit after final submission
    if marks and marks.is_submitted:
        flash('This evaluation has been finalized and locked. Editing is no longer permitted.', 'warning')
        return redirect(url_for('judge.dashboard'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        is_submitted = (action == 'final')
        comments = request.form.get('comments', '').strip()
        
        if round_num == 1:
            inn = int(request.form.get('innovation', 0))
            pres = int(request.form.get('presentation', 0))
            feas = int(request.form.get('feasibility', 0))
            conf = int(request.form.get('confidence', 0))
            
            # Validation: 25 marks each
            if not all(0 <= x <= 25 for x in [inn, pres, feas, conf]):
                flash('Marks must be between 0 and 25.', 'danger')
                return redirect(request.url)
                
            total = inn + pres + feas + conf
            
            if not marks:
                marks = Round1Marks(team_id=team_id, judge_id=current_user.id)
                db.session.add(marks)
                
            marks.innovation = inn
            marks.presentation = pres
            marks.feasibility = feas
            marks.confidence = conf
            marks.comments = comments
            marks.total_marks = total
            marks.is_submitted = is_submitted
            
        elif round_num == 2:
            proto = int(request.form.get('prototype', 0))
            tech = int(request.form.get('technical_implementation', 0))
            ui = int(request.form.get('uiux', 0))
            qa = int(request.form.get('question_answer', 0))
            
            # Validation
            if not (0 <= proto <= 30 and 0 <= tech <= 30 and 0 <= ui <= 20 and 0 <= qa <= 20):
                flash('Invalid marks ranges. Prototype/Tech (30 max), UIUX/QA (20 max).', 'danger')
                return redirect(request.url)
                
            total = proto + tech + ui + qa
            
            if not marks:
                marks = Round2Marks(team_id=team_id, judge_id=current_user.id)
                db.session.add(marks)
                
            marks.prototype = proto
            marks.technical_implementation = tech
            marks.uiux = ui
            marks.question_answer = qa
            marks.comments = comments
            marks.total_marks = total
            marks.is_submitted = is_submitted
            
        elif round_num == 3:
            demo = int(request.form.get('working_demo', 0))
            biz = int(request.form.get('business_model', 0))
            scal = int(request.form.get('scalability', 0))
            pres = int(request.form.get('presentation', 0))
            
            # Validation
            if not (0 <= demo <= 40 and 0 <= biz <= 20 and 0 <= scal <= 20 and 0 <= pres <= 20):
                flash('Invalid marks ranges. Demo (40 max), Biz/Scal/Pres (20 max).', 'danger')
                return redirect(request.url)
                
            total = demo + biz + scal + pres
            
            if not marks:
                marks = Round3Marks(team_id=team_id, judge_id=current_user.id)
                db.session.add(marks)
                
            marks.working_demo = demo
            marks.business_model = biz
            marks.scalability = scal
            marks.presentation = pres
            marks.comments = comments
            marks.total_marks = total
            marks.is_submitted = is_submitted
            
        db.session.commit()
        log_judge_activity(
            "Submit Evaluation" if is_submitted else "Draft Evaluation",
            f"Evaluated team {team.team_id} in Round {round_num}. Total: {total}"
        )
        
        status_text = "finalized and locked" if is_submitted else "saved as draft"
        flash(f"Round {round_num} marks for team {team.team_id} have been {status_text}.", "success")
        return redirect(url_for('judge.dashboard'))
        
    return render_template('judge/evaluate.html', round_num=round_num, team=team, marks=marks)
