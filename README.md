# Job Helper (Recruitment Lifecycle Sync & Tracker)

An autonomous hiring lifecycle sync engine that connects **Gmail**, **Applicant Tracking Systems (ATS)**, and **Notion** into a real-time, self-updating job application tracker.

---

## 🌟 The Universal 7-Stage Progression Model

Job Helper maps all corporate ATS platforms (Workday, Lever, Teamtailor, SuccessFactors, custom portals) into a standardized 7-stage hiring lifecycle:

```
[1. Submitted] ──► [2. Under Review] ──► [4. Assessment] ──► [3. Recruiter Screen]
                                                                        │
[7. Offer]     ◄── [6. Final Round]  ◄── [5. Technical Round]   ◄───────┘
```

1. **`Submitted`** (Stage 1): Initial application dispatched (via LinkedIn Easy Apply or company portal).
2. **`Under Review`** (Stage 2): Application passes initial ATS parsing; recruiter verification queue assigned.
3. **`Assessment`** (Stage 4 in sequence): Coding challenge, HackerRank, Cappfinity, cognitive assessment.
4. **`Recruiter Screen`** (Stage 3 in sequence): HR intro call, phone screen, recruiter outreach.
5. **`Technical Round`** (Stage 5): Live technical interview, system design, case study, or AI interview.
6. **`Final Round`** (Stage 6): Director / Hiring Manager alignment and leadership interview.
7. **`Offer`** (Stage 7): Formal employment offer letter.

### Terminal Statuses:
* **`Rejected (ATS Screen)`**: Fast automated knockout (disqualification within 24–72 hours).
* **`Rejected (Review Pool)`**: Disqualification after human review ("moving forward with other candidates").
* **`No Response`**: Applications older than **30 days** without communication are automatically transitioned to `No Response` (grouped under completed/archived).

---

## 🛡️ Security & Privacy First

* **Zero Credential Leaks**: `.env` and `sync_state.json` are strictly `.gitignore`d.
* **Restricted Ingestion Scope**: The IMAP client explicitly filters by job application sender domains and subjects. It **never** scans or stores personal, banking, or sensitive emails.
* **Encrypted Cloud Secrets**: When deployed to GitHub Actions, credentials live in encrypted **GitHub Repository Secrets**.

---

## 🚀 Quickstart (Local)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Credentials**:
   Copy `.env.example` to `.env` and fill in:
   ```env
   GMAIL_EMAIL="your-email@gmail.com"
   GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
   NOTION_TOKEN="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   NOTION_DATABASE_ID="your_notion_database_id_here"
   ```

3. **Run Manual Sync**:
   ```bash
   python run_sync.py
   ```

4. **Register Daily Windows Task (e.g. 09:00 AM)**:
   ```bash
   python setup_scheduler.py 09:00
   ```

---

## ☁️ Zero-Server Cloud Automation (GitHub Action + Webhook)

This project runs 100% serverless in the cloud for free:

### 1. Add Secrets to GitHub:
Go to your GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**:
* `GMAIL_EMAIL`
* `GMAIL_APP_PASSWORD`
* `NOTION_TOKEN`
* `NOTION_DATABASE_ID`

### 2. Set Up the Instant Gmail Webhook (Google Apps Script):
1. Visit [script.google.com](https://script.google.com/) and create a new project.
2. Copy the code from `google_apps_script/gmail_webhook.js`.
3. Add your GitHub Personal Access Token (PAT).
4. Add a trigger to run `checkRecentEmailsAndTrigger` every 5 or 10 minutes.

Whenever a job email arrives in Gmail, Google Apps Script sends an HTTP POST request to GitHub's `repository_dispatch` webhook, waking up GitHub Actions to sync Notion in real time.
