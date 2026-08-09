"""
integrations.py - Central module for Telegram, Google Sheets (Apps Script webhook), and Email exports.
All credentials are read from SystemSetting (DB) or environment variables.
"""
import os
import datetime


def _get_setting(key, default=''):
    try:
        from models import SystemSetting
        return SystemSetting.get_setting(key, default) or default
    except Exception:
        return os.environ.get(key.upper(), default)


# TELEGRAM

def send_telegram_message(text):
    try:
        import requests as req
    except ImportError:
        return False, "requests library not installed"

    bot_token = _get_setting('telegram_bot_token')
    channel_id = _get_setting('telegram_channel_id')

    if not bot_token or not channel_id:
        return False, "Telegram Bot Token or Channel ID not configured in Admin Settings."

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': channel_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    try:
        resp = req.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get('ok'):
            return True, ''
        return False, data.get('description', 'Unknown Telegram error')
    except Exception as e:
        return False, str(e)


# GOOGLE SHEETS (via Apps Script Web App)

def push_to_google_sheet(sheet_name, headers, rows, clear=True):
    try:
        import requests as req
    except ImportError:
        return False, "requests library not installed"

    webhook_url = _get_setting('google_sheet_webhook_url')
    if not webhook_url:
        return False, "Google Sheet Webhook URL not configured in Admin Settings."

    payload = {'sheet': sheet_name, 'clear': clear, 'headers': headers, 'rows': rows}
    try:
        resp = req.post(webhook_url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, ''
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


# EMAIL

def send_export_email(subject, html_body):
    to_email = _get_setting('export_email')
    if not to_email:
        return False, "Export email address not configured in Admin Settings."
    try:
        import re
        plain = re.sub(r'<[^>]+>', '', html_body)
        from utils import send_mock_email_with_attachments
        send_mock_email_with_attachments(to_email=to_email, subject=subject, body_text=plain, attachments=[])
        return True, ''
    except Exception as e:
        return False, str(e)


# DATA COLLECTOR

def _safe_avg(marks_list, field):
    if not marks_list:
        return 0.0
    vals = [getattr(m, field, 0) or 0 for m in marks_list]
    return sum(vals) / len(vals)


def collect_summary_data():
    from models import Team, TeamMember, Attendance, Round1Marks, Round2Marks, Round3Marks, FinalResult, Certificate

    teams = Team.query.order_by(Team.team_id).all()
    rows_teams, rows_marks, rows_certs = [], [], []
    total_present = total_absent = certs_released = certs_pending = 0

    for team in teams:
        leader = team.leader
        leader_name = leader.name if leader else 'N/A'
        leader_email = leader.email if leader else 'N/A'
        att = Attendance.query.filter_by(team_id=team.team_id).first()
        att_status = att.status if att else 'Absent'
        if att_status == 'Present':
            total_present += 1
        else:
            total_absent += 1
        sub = team.problem_submission
        project_title = sub.project_title if sub else 'N/A'
        domain = sub.domain if sub else 'N/A'
        member_count = TeamMember.query.filter_by(team_id=team.team_id).count()
        rows_teams.append([team.team_id, team.team_name, team.college, team.department,
                           leader_name, leader_email, member_count, att_status, project_title, domain])

        r1_avg = _safe_avg(Round1Marks.query.filter_by(team_id=team.team_id).all(), 'total_marks')
        r2_avg = _safe_avg(Round2Marks.query.filter_by(team_id=team.team_id).all(), 'total_marks')
        r3_avg = _safe_avg(Round3Marks.query.filter_by(team_id=team.team_id).all(), 'total_marks')
        grand = round(r1_avg + r2_avg + r3_avg, 2)
        final = FinalResult.query.filter_by(team_id=team.team_id).first()
        rank = final.rank if final else 'N/A'
        rows_marks.append([team.team_id, team.team_name, team.college,
                           round(r1_avg, 2), round(r2_avg, 2), round(r3_avg, 2), grand, rank])

        for c in Certificate.query.filter_by(team_id=team.team_id).all():
            if c.certificate_status == 'RELEASED':
                certs_released += 1
            else:
                certs_pending += 1
            released_at = c.released_time.strftime('%Y-%m-%d %H:%M') if c.released_time else 'N/A'
            rows_certs.append([team.team_id, team.team_name, c.student_name,
                               c.certificate_type, c.certificate_status, released_at])

    return {
        'rows_teams': rows_teams, 'rows_marks': rows_marks, 'rows_certs': rows_certs,
        'total_teams': len(teams), 'total_present': total_present,
        'total_absent': total_absent, 'certs_released': certs_released, 'certs_pending': certs_pending,
    }


# TELEGRAM MESSAGE BUILDERS

def build_telegram_summary(data):
    now = datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')
    top = sorted(data['rows_marks'], key=lambda r: r[6], reverse=True)[:5]
    leaderboard = ''.join(f"  {i+1}. {r[1]} - <b>{r[6]} pts</b>\n" for i, r in enumerate(top))
    return (
        f"<b>HackTrack - Full Event Summary</b>\n"
        f"Generated: {now}\n\n"
        f"Teams: {data['total_teams']}\n"
        f"Present: {data['total_present']}  |  Absent: {data['total_absent']}\n\n"
        f"<b>Top 5 Teams:</b>\n{leaderboard}\n"
        f"<b>Certificates:</b>\n"
        f"  Released: {data['certs_released']}\n"
        f"  Pending: {data['certs_pending']}\n"
        f"- HackTrack Bot"
    )


def build_cert_released_telegram_msg(team_name, member_names):
    now = datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')
    names = '\n'.join(f"  - {n}" for n in member_names)
    return (f"<b>Certificates Released!</b>\nTeam: <b>{team_name}</b>\nMembers:\n{names}\n{now}\n- HackTrack")


def build_marks_submitted_telegram_msg(judge_name, team_name, round_num, total):
    now = datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')
    return (f"<b>Marks Finalized - Round {round_num}</b>\nJudge: {judge_name}\nTeam: {team_name}\nScore: <b>{total} pts</b>\n{now}\n- HackTrack")


# HTML EMAIL REPORT

def build_html_report(data):
    now = datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')

    def tbl(headers, rows):
        ths = ''.join(f'<th style="padding:8px;background:#1e293b;color:#94a3b8;font-size:12px;">{h}</th>' for h in headers)
        trs = ''
        for i, row in enumerate(rows):
            bg = '#0f172a' if i % 2 == 0 else '#1e293b'
            tds = ''.join(f'<td style="padding:8px;color:#e2e8f0;font-size:12px;">{c}</td>' for c in row)
            trs += f'<tr style="background:{bg};">{tds}</tr>'
        return f'<table style="width:100%;border-collapse:collapse;margin-bottom:24px;"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>HackTrack Report</title></head>
<body style="background:#0f172a;font-family:Arial,sans-serif;padding:24px;color:#e2e8f0;">
<div style="max-width:900px;margin:0 auto;">
<h1 style="color:#38bdf8;">HackTrack - Full Event Report</h1>
<p style="color:#64748b;">Generated: {now}</p>
<div style="display:flex;gap:16px;margin-bottom:24px;">
  <div style="background:#1e293b;border-radius:8px;padding:16px;flex:1;text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#38bdf8;">{data['total_teams']}</div>
    <div style="color:#94a3b8;font-size:13px;">Total Teams</div></div>
  <div style="background:#1e293b;border-radius:8px;padding:16px;flex:1;text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#10b981;">{data['total_present']}</div>
    <div style="color:#94a3b8;font-size:13px;">Present</div></div>
  <div style="background:#1e293b;border-radius:8px;padding:16px;flex:1;text-align:center;">
    <div style="font-size:28px;font-weight:700;color:#f59e0b;">{data['certs_released']}</div>
    <div style="color:#94a3b8;font-size:13px;">Certs Released</div></div>
</div>
<h2 style="color:#38bdf8;font-size:16px;">Team Details</h2>
{tbl(['Team ID','Team Name','College','Dept','Leader','Email','Members','Attendance','Project','Domain'], data['rows_teams'])}
<h2 style="color:#38bdf8;font-size:16px;">Marks &amp; Leaderboard</h2>
{tbl(['Team ID','Team Name','College','Round 1','Round 2','Round 3','Grand Total','Rank'], data['rows_marks'])}
<h2 style="color:#38bdf8;font-size:16px;">Certificates</h2>
{tbl(['Team ID','Team Name','Student','Type','Status','Released At'], data['rows_certs'])}
<p style="color:#475569;font-size:11px;text-align:center;margin-top:24px;">Generated by HackTrack - {now}</p>
</div></body></html>"""
