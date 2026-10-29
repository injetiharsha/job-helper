# Job Helper (Recruitment Lifecycle Sync & Tracker)

An autonomous hiring lifecycle sync engine that connects **Gmail**, **Applicant Tracking Systems (ATS)**, **Sarvam AI (105b)**, and **Notion** into a real-time, self-updating job application tracker.

---

## 🏗️ Architecture & Division of Labor

Job Helper runs a distributed, zero-cost cloud architecture:

```
                  ┌────────────────────────────────────────┐
                  │          Inbound Recruitment           │
                  │                 Emails                 │
                  └───────────────────┬────────────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
      [Google Apps Script Bridge]           [Daily GitHub Cron / Manual]
     Runs every 5 mins as an event        Runs daily at 09:00 AM IST or
     sensor. Triggers GitHub Actions       manually via workflow_dispatch
      via repository_dispatch webhook      with customizable --since date
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      ▼
                      ┌───────────────────────────────┐
                      │    GitHub Actions (Python)    │
                      │   Core Heavy Sync Engine      │
                      └───────────────┬───────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
[Tier 1: Fast Regex Engine]                         [Tier 2: Sarvam AI 105b]
Free, instant parsing for LinkedIn,                 Reserved purely for unstructured,
Workday, and standard portals.                      ambiguous receipts & ATS relays.
(70%–80% of volume @ ₹0.00)                         (Audited with live telemetry)
            │                                                   │
            └─────────────────────────┬─────────────────────────┘
                                      ▼
                      ┌───────────────────────────────┐
                      │    Notion Database Engine     │
                      │  Updates Status, URLs, Dates  │
                      └───────────────┬───────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
[Notion Database Views]                             [Google Apps Script Bridge]
• Active Applications (Filtered)                    syncNotionToGoogleCalendar()
• 📅 Calendar (Deadlines/Events)                    Creates native calendar events
• 🚫 Rejected Archive                               for interviews and tests.
• 📊 Pipeline (Kanban Board)
```

---

## 🌟 The Universal 7-Stage Progression Model

Job Helper maps corporate ATS platforms (Workday, Lever, Greenhouse, Ashby, SuccessFactors, custom portals) into a standardized hiring lifecycle:

```
[1. Submitted] ──► [2. Under Review] ──► [4. Assessment] ──► [3. Recruiter Screen]
                                                                        │
[7. Offer]     ◄── [6. Final Round]  ◄── [5. Technical Round]   ◄───────┘
```

1. **`Submitted`** (Stage 1): Initial application dispatched (via LinkedIn Easy Apply or company portal).
2. **`Under Review`** (Stage 2): Application passes initial ATS parsing; candidate profile under active recruiter review.
3. **`Assessment`** (Stage 4 in sequence): Coding challenges, HackerRank, Cappfinity, TestGorilla, cognitive evaluations.
4. **`Recruiter Screen`** (Stage 3 in sequence): HR intro call, phone screen, recruiter outreach.
5. **`Technical Round`** (Stage 5): Live coding, system design, case study, or AI interview.
6. **`Final Round`** (Stage 6): Director / Hiring Manager alignment and leadership interview.
7. **`Offer`** (Stage 7): Formal employment offer letter.

### Terminal Statuses:
* **`Rejected (ATS Screen)`**: Fast automated knockout (disqualification within 24–72 hours).
* **`Rejected (Review Pool)`**: Disqualification after human review ("moving forward with other candidates").
* **`Rejected`**: General consolidated rejection.
* **`No Response`**: Applications older than **30 days** without communication are automatically transitioned to `No Response` to keep the active pipeline uncluttered.

---

## 🧠 2-Tier Extraction Engine & Telemetry

To keep operational costs near zero, Job Helper enforces strict tiering:

1. **Tier 1 (Free Regex & Header Matching)**:
   * LinkedIn Easy Apply parser: Extracts role, company, and portal URL.
   * Workday generic parser: Resolves company from sender/headers and candidate home URL.
   * Universal sender domain resolver: Maps generic display names (`Human Resources <noreply@honeywell.com>`) directly to the employer domain (`Honeywell`).
   * **Cost**: **₹0.00 (0 tokens)**. Handles 75%+ of typical inbox volume.

2. **Tier 2 (Sarvam AI 105b LLM Fallback)**:
   * Invoked **only** when the hiring company is missing, ambiguous, or when relay ATS domains (Ashby, Greenhouse) send unstructured lifecycle progression notices.
   * Includes built-in **Telemetry & Cost Auditing** (`telemetry.json`):
     * Character count tracking (input vs. output).
     * Exact token breakdown (prompt tokens, cached prompt tokens, completion tokens, reasoning tokens).
     * Exact INR cost calculation logged per call.

### Typical Unit Economics:
* **Input Tokens**: $\approx$ 450 tokens (billed at ₹0.015 / 1K tokens with automatic 66% prompt caching discount).
* **Output / Reasoning Tokens**: $\approx$ 500 – 1,800 internal reasoning tokens (billed at ₹0.06 / 1K tokens).
* **Average Cost per Tricky Call**: $\approx$ **₹0.04 to ₹0.09 (4 to 9 paise)**.
* **Blended Cost for 100 Applications**: $\approx$ **₹0.20 to ₹0.30 (20 to 30 paise total)**.

---

## 📊 Pre-Configured Notion Database Views

The database (`JOB Helper`) includes 4 dedicated views accessible via top tabs:

| View Name | Layout | Filter / Grouping | Purpose |
| :--- | :---: | :--- | :--- |
| **Active Applications** | `Table` | `Updated Status` does not equal `Rejected` or `No Response` | Clean view of live, in-flight job applications. |
| **Calendar** | `Calendar` | Grouped by `Deadline / Event Date` | Monthly visual schedule of assessment deadlines & interviews. |
| **Rejected** | `Table` | `Updated Status` equals `Rejected` or `No Response` | Isolated archive of closed and rejected applications. |
| **Pipeline** | `Board` | Grouped by `Updated Status` | Drag-and-drop Kanban board across stages. |

---

## 🚀 Setup & Deployment

### 1. Configure Local Environment (`.env`)

Copy `.env.example` to `.env`:

```env
GMAIL_EMAIL="your-email@gmail.com"
GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
NOTION_TOKEN="secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
NOTION_DATABASE_ID="4083c29f1b20801d9edbe0a791f3c75c"
SARVAM_API_KEY="sk_xxxxxxx"
```

* **Gmail App Password**: Generated via [Google Account Security](https://myaccount.google.com/apppasswords).
* **Notion Integration Token**: Generated via [Notion Integrations](https://www.notion.so/my-integrations). Make sure your database is shared with the integration.
* **Sarvam API Key**: Generated via [Sarvam AI Dashboard](https://dashboard.sarvam.ai/).

### 2. Run Local Sync

```bash
# Incremental daily run (defaults to last synced date or 3-day lookback)
python run_sync.py

# Full backfill from a specific date
python run_sync.py --since 01-Oct-2026
```

---

## ☁️ Serverless Automation (GitHub Actions + Google Apps Script)

### 1. Add Repository Secrets in GitHub
Navigate to **Repository Settings** $\to$ **Secrets and variables** $\to$ **Actions** $\to$ **New repository secret**:
* `GMAIL_EMAIL`
* `GMAIL_APP_PASSWORD`
* `NOTION_TOKEN`
* `NOTION_DATABASE_ID`
* `SARVAM_API_KEY`

### 2. Configure Google Apps Script (`job_helper_cloud_bridge.js`)
1. Open [script.google.com](https://script.google.com/) and create a new project.
2. Paste the contents of [`google_apps_script/job_helper_cloud_bridge.js`](google_apps_script/job_helper_cloud_bridge.js).
3. Run `setupScriptProperties()` once to store your `GITHUB_PAT`, `GITHUB_REPO`, `NOTION_TOKEN`, and `NOTION_DATABASE_ID`.
4. Add two time-driven triggers:
   * `checkRecentEmailsAndTrigger`: Runs every **5 minutes** (inbound webhook sensor).
   * `syncNotionToGoogleCalendar`: Runs every **hour** or **day** (outbound native calendar creator).

### 3. Manual Workflow Dispatch & Telemetry Artifacts
* You can trigger runs on demand from the **Actions** tab on GitHub with an optional `--since` input (e.g. `01-Oct-2026`).
* After each run, the full `telemetry.json` audit report is attached under the **Artifacts** section of the run summary.

---

## 🔮 Upcoming Features
* **Telegram Notification Pusher**: Real-time push alerts to your Telegram chat whenever an interview is scheduled, an assessment is received, or an application status is updated.
* **Automated Calendar Reminders**: Auto-injecting reminder alerts 2 hours prior to assessment deadlines.
