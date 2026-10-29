/**
 * =========================================================================
 * Job Helper OS: 100% Serverless Cloud Sync (Google Apps Script)
 * =========================================================================
 * 
 * Runs 24/7 in Google's Cloud without needing your computer turned on.
 * Connects Gmail -> Sarvam AI (sarvam-105b) -> Notion -> Google Calendar.
 * 
 * Features:
 * 1. Hybrid Cascading: Fast LinkedIn regex + Sarvam 105b for non-typical ATS.
 * 2. Generic Filtering: Drops official .gov/.nic.in/tax/PAN/passport/2FA emails.
 * 3. Atomic Notion Sync: Writes clean records without duplicates.
 * 4. Google Calendar Scheduling: Adds interviews & test deadlines with 30-min alerts.
 * 5. One-click October 1 Backfill: Run `syncFromOctoberFirst` once to sync Oct 1 -> now.
 * 
 * -------------------------------------------------------------------------
 * SETUP INSTRUCTIONS (Takes 2 minutes)
 * -------------------------------------------------------------------------
 * 1. Open https://script.google.com and click "New project".
 * 2. Delete any boilerplate in Code.gs and paste this ENTIRE file.
 * 3. In the toolbar dropdown, select "setupScriptProperties" and click "Run".
 *    (This securely saves your Notion & Sarvam keys to Script Properties).
 * 4. In the toolbar dropdown, select "syncFromOctoberFirst" and click "Run".
 *    (This writes all job applications from October 1 to now into Notion!).
 * 5. Add the 30-Minute Recurring Trigger:
 *    - Click the clock icon (Triggers) on the left sidebar.
 *    - Click "+ Add Trigger" (bottom right).
 *    - Function to run: "runJobHelper30MinSync"
 *    - Event source: "Time-driven"
 *    - Type of trigger: "Minutes timer"
 *    - Minute interval: "Every 30 minutes" (or every 15 minutes)
 *    - Click Save.
 * =========================================================================
 */

// One-time credential initializer into Google Cloud secure storage
function setupScriptProperties() {
  PropertiesService.getScriptProperties().setProperties({
    "NOTION_TOKEN": "YOUR_NOTION_TOKEN_HERE",
    "NOTION_DATABASE_ID": "4083c29f-1b20-801d-9edb-e0a791f3c75c",
    "SARVAM_API_KEY": "YOUR_SARVAM_API_KEY_HERE"
  });
  Logger.log("✅ Credentials securely saved to Script Properties!");
}

function getConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    NOTION_TOKEN: props.getProperty("NOTION_TOKEN") || "",
    NOTION_DATABASE_ID: props.getProperty("NOTION_DATABASE_ID") || "4083c29f-1b20-801d-9edb-e0a791f3c75c",
    SARVAM_API_KEY: props.getProperty("SARVAM_API_KEY") || ""
  };
}

/**
 * Generic Sender Exclusion:
 * Filters government/statutory domains (.gov, .nic.in, .mil) and candidate's own email.
 */
function isExcludedSender(fromH) {
  const fromLow = (fromH || "").toLowerCase();
  const userEmail = Session.getActiveUser().getEmail().toLowerCase();
  
  if (userEmail && fromLow.includes(userEmail)) return true;
  if (/@(?:[a-zA-Z0-9-]+\.)*(?:gov(?:\.[a-z]{2})?|nic\.in|mil)\b/.test(fromLow)) return true;
  if (fromLow.includes("accounts.google.com") || fromLow.includes("ads-noreply") || fromLow.includes("glassdoor.com")) return true;

  return false;
}

const EXCLUDE_PATTERNS = [
  /\b(?:pan\s*card|pan\s*application|intimation\s*of\s*pan|police\s*verification|passport|income\s*tax|itr|aadhaar|form\s*16|e-filing|voter\s*id)\b/i,
  /\b(?:verification code|security code|password reset|confirm your email|sign[- ]in code|2fa|otp)\b/i,
  /\b(?:study abroad|scholarship|admissions?|degree application)\b/i,
  /\b(?:talent community|job alert|recommended jobs|weekly alert|newsletter)\b/i
];

/**
 * Scheduled Function: Runs every 30 minutes.
 * Scans recent recruitment emails since last sync run.
 */
function runJobHelper30MinSync() {
  Logger.log("=== Starting 30-Minute Job Helper Sync ===");
  const query = 'newer_than:2d (subject:"job application" OR subject:"interview" OR subject:"assessment" OR subject:"candidacy" OR subject:"application was sent" OR subject:"acknowledgement" OR subject:"application received" OR from:jobs-noreply@linkedin.com OR from:myworkday.com OR from:ashbyhq.com OR from:greenhouse.io OR from:lever.co OR from:hackerrank.net)';
  processEmailsWithQuery(query, false);
}

/**
 * Manual / One-Time Backfill Function:
 * Syncs all recruitment emails from October 1 to now into the new database!
 */
function syncFromOctoberFirst() {
  Logger.log("=== Starting Full Backfill from October 1, 2026 to Now ===");
  const query = 'after:2026/09/30 (subject:"job application" OR subject:"interview" OR subject:"assessment" OR subject:"candidacy" OR subject:"application was sent" OR subject:"acknowledgement" OR subject:"application received" OR from:jobs-noreply@linkedin.com OR from:myworkday.com OR from:ashbyhq.com OR from:greenhouse.io OR from:lever.co OR from:hackerrank.net)';
  processEmailsWithQuery(query, true);
}

function processEmailsWithQuery(query, isFullBackfill) {
  const config = getConfig();

  // Validate configuration before starting
  if (!config.NOTION_TOKEN || config.NOTION_TOKEN.includes("YOUR_")) {
    Logger.log("❌ ERROR: NOTION_TOKEN is missing or contains placeholder! Please update setupScriptProperties() with your real Notion token and run it once.");
    return;
  }
  if (!config.SARVAM_API_KEY || config.SARVAM_API_KEY.includes("YOUR_")) {
    Logger.log("⚠️ WARNING: SARVAM_API_KEY is missing or contains placeholder! Please update setupScriptProperties() with your real Sarvam key.");
  }

  const userProps = PropertiesService.getUserProperties();
  const lastCheckMs = isFullBackfill ? 0 : parseInt(userProps.getProperty("LAST_CHECK_MS") || "0", 10);
  const nowMs = Date.now();

  const maxThreads = isFullBackfill ? 100 : 25;
  const threads = GmailApp.search(query, 0, maxThreads);
  Logger.log(`Found ${threads.length} email threads matching query.`);

  let maxMsgMs = lastCheckMs;
  const processedEmails = [];

  for (const thread of threads) {
    const messages = thread.getMessages();
    for (const msg of messages) {
      const msgDateMs = msg.getDate().getTime();
      if (!isFullBackfill && lastCheckMs > 0 && msgDateMs <= lastCheckMs) {
        continue;
      }
      if (msgDateMs > maxMsgMs) {
        maxMsgMs = msgDateMs;
      }

      const fromH = msg.getFrom();
      const subj = msg.getSubject();
      const body = msg.getPlainBody();

      if (isExcludedSender(fromH)) continue;
      if (EXCLUDE_PATTERNS.some(pat => pat.test(subj) || pat.test(body.substring(0, 300)))) continue;

      processedEmails.push({
        id: msg.getId(),
        from: fromH,
        subject: subj,
        body: body,
        date: msg.getDate()
      });
    }
  }

  Logger.log(`Ingested ${processedEmails.length} relevant candidate emails to process.`);
  if (processedEmails.length === 0) {
    userProps.setProperty("LAST_CHECK_MS", nowMs.toString());
    return;
  }

  // Fetch active companies currently in the database to prevent duplicate writes
  const activeEntries = getNotionApplications(config);
  Logger.log(`Existing database entries loaded: ${activeEntries.length}`);

  let createdCount = 0;
  let updatedCount = 0;

  for (const item of processedEmails) {
    const extracted = extractWithHybridSarvam(item, config, activeEntries);
    if (!extracted || !extracted.company) continue;

    const compNorm = normalizeString(extracted.company);
    const existing = activeEntries.find(e => normalizeString(e.company) === compNorm);

    if (!existing) {
      // 1. Create net-new application
      if (createNotionApplication(extracted, config)) {
        createdCount++;
        activeEntries.push({ company: extracted.company, id: null });
        Logger.log(`[+] Created application: ${extracted.company} | ${extracted.role}`);
      }
    } else {
      // 2. Update existing application if stage progressed
      if (extracted.stage && extracted.stage !== "Submitted" && existing.id) {
        if (updateNotionStage(existing.id, extracted, config)) {
          updatedCount++;
          Logger.log(`[*] Updated status: ${extracted.company} -> ${extracted.stage}`);
        }
      }
    }

    // 3. Schedule interview or assessment deadline on Google Calendar
    if (extracted.event_datetime || extracted.deadline_date) {
      scheduleOnGoogleCalendar(extracted);
    }
  }

  userProps.setProperty("LAST_CHECK_MS", maxMsgMs.toString());
  Logger.log(`=========================================`);
  Logger.log(`Sync Finished! Created: ${createdCount}, Updated: ${updatedCount}`);
  Logger.log(`=========================================`);
}

function normalizeString(str) {
  return (str || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

/**
 * Hybrid Extractor:
 * 1. Fast regex for 90% of predictable emails (LinkedIn Easy Apply).
 * 2. Cascades to Sarvam 105b for unstructured receipts, ATS relays, and interviews.
 */
function extractWithHybridSarvam(item, config, activeEntries) {
  const fromH = item.from;
  const subj = item.subject;
  const body = item.body;
  const dateStr = Utilities.formatDate(item.date, Session.getScriptTimeZone(), "yyyy-MM-dd");

  let company = "";
  let role = "Software Engineer / Intern";
  let stage = "Submitted";

  // Tier 1: Fast LinkedIn match
  if (fromH.toLowerCase().includes("linkedin")) {
    const m = subj.match(/your application was sent to\s+(.+)/i);
    if (m) {
      company = cleanCompanyName(m[1]);
      return { company, role, stage, dateStr };
    }
  }

  // Tier 2: Complex ATS / Relay domain / Stage event -> Sarvam 105b
  const isRelay = /ashby|greenhouse|lever|hackerrank|codility|smartrecruiters|oraclecloud|taleo|icims/i.test(fromH);
  const isStageEvent = /interview|assessment|candidacy|update on your|test|rejection|shortlist/i.test(subj);
  const isReceipt = /acknowledgement|candidate home|application received|application update|thank you for applying/i.test(subj);

  if ((isRelay || isStageEvent || isReceipt || !company) && config.SARVAM_API_KEY) {
    const compList = activeEntries.map(e => e.company).filter(Boolean).slice(0, 60).join(", ");
    const prompt = `Analyze this job application email.
Extract the company name, role title, and hiring stage.
Candidate active companies list: [${compList}]

Sender: ${fromH}
Subject: ${subj}
Date: ${dateStr}
Body:
${body.substring(0, 1800)}

Classify stage into: ["Submitted", "Under Review", "Assessment", "Recruiter Screen", "Technical Round", "Final Round", "Offer", "Rejected"]

Return JSON only:
{
  "company": "Company Name",
  "role": "Role Title",
  "stage": "Stage Name",
  "event_datetime": "ISO-8601 string or null",
  "deadline_date": "YYYY-MM-DD or null",
  "meeting_link": "Google Meet or MS Teams or Zoom URL or null"
}`;

    try {
      const resp = UrlFetchApp.fetch("https://api.sarvam.ai/v1/chat/completions", {
        method: "post",
        contentType: "application/json",
        headers: { "api-subscription-key": config.SARVAM_API_KEY },
        payload: JSON.stringify({
          model: "sarvam-105b",
          messages: [{ role: "user", content: prompt }],
          temperature: 0.1
        }),
        muteHttpExceptions: true
      });

      const resJson = JSON.parse(resp.getContentText());
      if (resJson.choices && resJson.choices.length > 0) {
        let text = resJson.choices[0].message.content.trim();
        if (text.includes("```json")) text = text.split("```json")[1].split("```")[0].trim();
        else if (text.includes("```")) text = text.split("```")[1].split("```")[0].trim();
        
        const parsed = JSON.parse(text);
        parsed.company = cleanCompanyName(parsed.company);
        parsed.dateStr = dateStr;
        return parsed;
      } else {
        const errMsg = resJson.error ? resJson.error.message : resp.getContentText();
        Logger.log("Sarvam API error: " + errMsg);
      }
    } catch (e) {
      Logger.log("Sarvam extraction exception: " + e.message);
    }
  }

  return {
    company: cleanCompanyName(fromH.split("<")[0]),
    role: subj.substring(0, 50),
    stage: "Submitted",
    dateStr: dateStr
  };
}

function cleanCompanyName(name) {
  if (!name) return "";
  let clean = name.replace(/[\"\'!]/g, "").trim();
  clean = clean.replace(/\s+(?:Human Resources|HR|Talent Acquisition|Recruitment|Recruiting|Careers|Team|Workday)$/i, "");
  return clean.trim();
}

/**
 * Notion Database Operations (Adapted for select & status properties)
 */
function getNotionApplications(config) {
  const url = `https://api.notion.com/v1/databases/${config.NOTION_DATABASE_ID}/query`;
  const list = [];
  let hasMore = true;
  let startCursor = null;

  while (hasMore) {
    const payload = { page_size: 100 };
    if (startCursor) payload.start_cursor = startCursor;

    const options = {
      method: "post",
      contentType: "application/json",
      headers: {
        "Authorization": `Bearer ${config.NOTION_TOKEN}`,
        "Notion-Version": "2022-06-28"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    try {
      const res = UrlFetchApp.fetch(url, options);
      const data = JSON.parse(res.getContentText());
      for (const p of data.results || []) {
        const titles = (p.properties.Company || {}).title || [];
        const name = titles.length > 0 ? titles[0].plain_text : "";
        if (name) list.push({ company: name, id: p.id });
      }
      hasMore = data.has_more;
      startCursor = data.next_cursor;
    } catch (e) {
      Logger.log("Notion query error: " + e.message);
      break;
    }
  }
  return list;
}

function createNotionApplication(data, config) {
  const url = "https://api.notion.com/v1/pages";
  const payload = {
    parent: { database_id: config.NOTION_DATABASE_ID },
    properties: {
      "Company": { title: [{ text: { content: data.company } }] },
      "Role": { rich_text: [{ text: { content: data.role || "Software Engineer / Intern" } }] },
      "Applied Date": { date: { start: data.dateStr } },
      "Portal": { select: { name: "Career Portal" } },
      "Status": { select: { name: "Submitted" } }
    }
  };

  try {
    const resp = UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      headers: {
        "Authorization": `Bearer ${config.NOTION_TOKEN}`,
        "Notion-Version": "2022-06-28"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    if (resp.getResponseCode() === 200) {
      return true;
    } else {
      Logger.log(`Notion create failed (${resp.getResponseCode()}): ${resp.getContentText()}`);
      return false;
    }
  } catch (e) {
    Logger.log("Notion create error: " + e.message);
    return false;
  }
}

function updateNotionStage(pageId, data, config) {
  const url = `https://api.notion.com/v1/pages/${pageId}`;
  const props = {
    "Updated Status": { select: { name: data.stage } },
    "Updated Date": { date: { start: data.dateStr } }
  };
  if (data.deadline_date || data.event_datetime) {
    props["Deadline / Event Date"] = { date: { start: (data.deadline_date || data.event_datetime).substring(0, 10) } };
  }
  if (data.meeting_link) {
    props["JSON"] = { rich_text: [{ text: { content: JSON.stringify({ meeting_link: data.meeting_link }) } }] };
  }

  try {
    const resp = UrlFetchApp.fetch(url, {
      method: "patch",
      contentType: "application/json",
      headers: {
        "Authorization": `Bearer ${config.NOTION_TOKEN}`,
        "Notion-Version": "2022-06-28"
      },
      payload: JSON.stringify({ properties: props }),
      muteHttpExceptions: true
    });
    if (resp.getResponseCode() === 200) {
      return true;
    } else {
      Logger.log(`Notion update failed (${resp.getResponseCode()}): ${resp.getContentText()}`);
      return false;
    }
  } catch (e) {
    Logger.log("Notion update error: " + e.message);
    return false;
  }
}

function scheduleOnGoogleCalendar(data) {
  try {
    const cal = CalendarApp.getDefaultCalendar();
    const title = `[Interview] ${data.company} - ${data.role || "Discussion"}`;
    const desc = `Stage: ${data.stage}\nMeeting Link: ${data.meeting_link || "Check email details"}`;

    if (data.event_datetime) {
      const start = new Date(data.event_datetime);
      const end = new Date(start.getTime() + 45 * 60 * 1000);
      const event = cal.createEvent(title, start, end, { description: desc });
      event.addPopupReminder(30);
      Logger.log(`Created Calendar Event: ${title} at ${start}`);
    } else if (data.deadline_date) {
      const d = new Date(data.deadline_date);
      cal.createAllDayEvent(`[Deadline] ${data.company} Assessment`, d, { description: desc });
      Logger.log(`Created All-Day Calendar Event for deadline: ${d}`);
    }
  } catch (e) {
    Logger.log("Calendar scheduling error: " + e.message);
  }
}
