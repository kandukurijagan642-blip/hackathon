from flask import Blueprint, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from database import db
from models import SystemSetting, ActivityLog

integrations_bp = Blueprint('integrations', __name__, url_prefix='/admin/integrations')


def check_admin():
    return current_user.is_authenticated and current_user.role == 'Admin'


def log_action(action, details=None):
    try:
        log = ActivityLog(user_id=current_user.id, action=action, ip_address=request.remote_addr, details=details)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Log error: {e}")


# ─── SETTINGS SAVE ───────────────────────────────────────────────

@integrations_bp.route('/save-settings', methods=['POST'])
@login_required
def save_settings():
    if not check_admin():
        return redirect(url_for('auth.login'))

    fields = ['telegram_bot_token', 'telegram_channel_id',
              'google_sheet_webhook_url', 'export_email']

    for field in fields:
        val = request.form.get(field, '').strip()
        if val:
            SystemSetting.set_setting(field, val)

    log_action("Save Integration Settings", "Updated Telegram/Sheets/Email integration credentials")
    flash('Integration settings saved successfully!', 'success')
    return redirect(url_for('admin.dashboard'))


# ─── TELEGRAM ────────────────────────────────────────────────────

@integrations_bp.route('/telegram', methods=['POST'])
@login_required
def send_telegram():
    if not check_admin():
        return redirect(url_for('auth.login'))
    try:
        from integrations import collect_summary_data, build_telegram_summary, send_telegram_message
        data = collect_summary_data()
        msg = build_telegram_summary(data)
        ok, err = send_telegram_message(msg)
        if ok:
            log_action("Send Telegram Summary", f"Sent summary to Telegram channel")
            flash('Summary sent to Telegram successfully!', 'success')
        else:
            flash(f'Telegram error: {err}', 'danger')
    except Exception as e:
        flash(f'Error sending Telegram message: {str(e)}', 'danger')
    return redirect(url_for('admin.dashboard'))


# ─── GOOGLE SHEETS ───────────────────────────────────────────────

@integrations_bp.route('/sheets', methods=['POST'])
@login_required
def push_sheets():
    if not check_admin():
        return redirect(url_for('auth.login'))
    try:
        from integrations import collect_summary_data, push_to_google_sheet
        data = collect_summary_data()

        errors = []

        ok, err = push_to_google_sheet(
            sheet_name='Teams',
            headers=['Team ID', 'Team Name', 'College', 'Dept', 'Leader', 'Email', 'Members', 'Attendance', 'Project', 'Domain'],
            rows=data['rows_teams']
        )
        if not ok:
            errors.append(f"Teams: {err}")

        ok, err = push_to_google_sheet(
            sheet_name='Marks',
            headers=['Team ID', 'Team Name', 'College', 'Round 1', 'Round 2', 'Round 3', 'Grand Total', 'Rank'],
            rows=data['rows_marks']
        )
        if not ok:
            errors.append(f"Marks: {err}")

        ok, err = push_to_google_sheet(
            sheet_name='Certificates',
            headers=['Team ID', 'Team Name', 'Student', 'Type', 'Status', 'Released At'],
            rows=data['rows_certs']
        )
        if not ok:
            errors.append(f"Certificates: {err}")

        if errors:
            flash(f'Some sheets failed: {"; ".join(errors)}', 'warning')
        else:
            log_action("Push to Google Sheets", "Pushed Teams/Marks/Certificates to Google Sheets")
            flash('All data pushed to Google Sheets successfully!', 'success')
    except Exception as e:
        flash(f'Error pushing to Google Sheets: {str(e)}', 'danger')
    return redirect(url_for('admin.dashboard'))


# ─── EMAIL REPORT ────────────────────────────────────────────────

@integrations_bp.route('/email', methods=['POST'])
@login_required
def send_email_report():
    if not check_admin():
        return redirect(url_for('auth.login'))
    try:
        from integrations import collect_summary_data, build_html_report, send_export_email
        import datetime
        data = collect_summary_data()
        html = build_html_report(data)
        subject = f"HackTrack Full Report — {datetime.datetime.now().strftime('%d %b %Y')}"
        ok, err = send_export_email(subject, html)
        if ok:
            log_action("Send Email Report", "Sent full HTML report to export email")
            flash('Full report emailed successfully!', 'success')
        else:
            flash(f'Email error: {err}', 'danger')
    except Exception as e:
        flash(f'Error sending email report: {str(e)}', 'danger')
    return redirect(url_for('admin.dashboard'))


# ─── SEND ALL ────────────────────────────────────────────────────

@integrations_bp.route('/all', methods=['POST'])
@login_required
def send_all():
    if not check_admin():
        return redirect(url_for('auth.login'))
    results = []
    try:
        from integrations import collect_summary_data, build_telegram_summary, send_telegram_message
        from integrations import push_to_google_sheet, build_html_report, send_export_email
        import datetime

        data = collect_summary_data()

        # Telegram
        ok, err = send_telegram_message(build_telegram_summary(data))
        results.append(f"Telegram: {'OK' if ok else err}")

        # Sheets
        for sheet_name, headers, rows_key in [
            ('Teams', ['Team ID','Team Name','College','Dept','Leader','Email','Members','Attendance','Project','Domain'], 'rows_teams'),
            ('Marks', ['Team ID','Team Name','College','Round 1','Round 2','Round 3','Grand Total','Rank'], 'rows_marks'),
            ('Certificates', ['Team ID','Team Name','Student','Type','Status','Released At'], 'rows_certs'),
        ]:
            ok, err = push_to_google_sheet(sheet_name, headers, data[rows_key])
            results.append(f"Sheet-{sheet_name}: {'OK' if ok else err}")

        # Email
        html = build_html_report(data)
        subject = f"HackTrack Full Report — {datetime.datetime.now().strftime('%d %b %Y')}"
        ok, err = send_export_email(subject, html)
        results.append(f"Email: {'OK' if ok else err}")

        log_action("Send All Integrations", "; ".join(results))
        flash('All integrations triggered! Results: ' + ' | '.join(results), 'info')
    except Exception as e:
        flash(f'Error in Send All: {str(e)}', 'danger')
    return redirect(url_for('admin.dashboard'))
