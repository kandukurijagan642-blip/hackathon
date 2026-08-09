# 🏁 HackTrack — Hackathon Portal

A production-ready, feature-rich hackathon administration and judging platform. HackTrack simplifies the entire lifecycle of a hackathon, including team registration, live QR attendance checking, project submission tracking, multi-round judging, real-time leaderboards, automated certificate generation, and webhook notifications.

---

## 🚀 Key Features

*   **👥 Team & Roster Management:** Complete registration workflow supporting both manual and bulk upload via Excel.
*   **📡 QR-Code Attendance Scan:** Instant check-in/out scanning system using high-entropy dynamic team QR codes.
*   **📝 Phase-Locked Submissions:** Custom controls for releasing and locking problem statement submissions.
*   **⚖️ 3-Round Jury Evaluation:** Decoupled scoring for Judges (Round 1: Innovation, Round 2: Build, Round 3: Scale) with draft/finalization locking mechanisms.
*   **🏆 Real-Time Leaderboard:** Ranks teams dynamically based strictly on finalized (submitted) scores.
*   **📜 Automated Certificate Engine:** Generates on-the-fly customized PDF certificates with unique verification tokens and links.
*   **📧 Automated Email Delivery:** Delivers fresh certificate PDFs directly to team leader emails via SMTP.
*   **🤖 Integrations & Exports:** Real-time Telegram alerts, automated Google Sheets population via webhooks, and full HTML report generation.

---

## 🛠️ Architecture & Tech Stack

*   **Backend:** Python 3 + Flask (MVC architecture, Blueprint routing)
*   **Database:** SQLite / PostgreSQL / MySQL (handled seamlessly via SQLAlchemy ORM depending on environment variables)
*   **Styling & UI:** HTML5 + Custom CSS3 Design System with a premium Dark/Light glassmomorphic theme and custom toast alerts.
*   **External APIs:** Telegram Bot API (updates), Google Apps Script Web App (automated sheets entry), and SMTP mail server (live delivery).

---

## 🛡️ Hardened Production Security Measures

*   **🛡️ CSRF Protection:** Strict cross-site request forgery prevention via Flask-WTF. All state-changing POST forms (submissions, evaluations, settings, admin functions) require a valid cryptographic `csrf_token`.
*   **🔒 Secure Session Termination:** Logout endpoint is protected by a POST-only method containing CSRF token verification, preventing malicious sites from force-logging users out.
*   **🔑 Concurrency-Safe Entropy IDs:** Custom Team IDs (`HT2026-XXXXXX`) and Certificate IDs (`HC2026-XXXXXXXX`) use high-entropy random identifiers (`secrets.token_hex`), completely eliminating database PK collision race conditions under concurrent loads.
*   **🔐 Auth-Gated QR Code Shortcuts:** QR shortcut access uses secure signed URL tokens via `URLSafeSerializer` allowing passwordless logins for team leaders while locking out unauthorized access.
*   **🩺 Privacy-Preserving Health Checks:** System check endpoints conceal raw database engine parameters and SQL query traceback outputs to prevent information disclosure.
*   **💾 Database-Enforced Data Integrity:** Unique schema constraints prevent duplicate team attendance (`uq_attendance_team`) and duplicate judge-round markings (`uq_rX_team_judge`).
*   **⚠️ Fail-Fast Configuration Safeguards:** Startup validation aborts deployment in hosting environments if critical secrets (`SECRET_KEY`, `DATABASE_URL`) are unconfigured.

---

## 📦 Setting Up the Project

### 1. Installation
Clone the repository and install requirements:
```bash
pip install -r requirements.txt
```

### 2. Run Locally
The app defaults to a local MySQL or SQLite database:
```bash
python hacktrack/app.py
```
Open your browser at `http://localhost:5000`.

### 3. Deploy to Railway
Railway automatically detects the `Procfile` and builds the Python environment:
1. Create a new service from your Git repository.
2. Spin up a **PostgreSQL** database in your Railway project.
3. Railway automatically binds the `DATABASE_URL` variable to your web app.
4. Add your Telegram Bot Token and Gmail App credentials to the service's environment variables.

---

## 🔑 Default Seeded Accounts (For Hackathon Demo)
If the database is empty, the app automatically seeds the following demo roles:

*   **Super Admin:** `admin@hacktrack.com` / `Admin@123`
*   **Event Organizer:** `organizer@hacktrack.com` / `Organizer@123`
*   **Jury Judge 1:** `judge1@hacktrack.com` / `Judge@123`
*   **Jury Judge 2:** `judge2@hacktrack.com` / `Judge@123`