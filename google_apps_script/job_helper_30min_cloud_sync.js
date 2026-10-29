/**
 * =========================================================================
 * Job Helper OS: 30-Minute Serverless Cloud Sync
 * =========================================================================
 * 
 * 100% Free, Cloud-Native Google Apps Script Automation.
 * Runs on a 30-minute Time-Driven Trigger without keeping any computer turned on.
 * 
 * Capabilities:
 * 1. Scans Gmail for recruitment receipts, interviews, assessments, and rejections.
 * 2. Pre-filters security/verification noise, 2FA codes, and marketing newsletters.
 * 3. Syncs applications and updates directly with Notion REST API.
 * 4. Calls Sarvam AI (sarvam-105b) for high-accuracy entity extraction on complex/non-typical ATS.
 * 5. Automatically creates Google Calendar events + reminders for interviews & tests.
 * 6. (Optional) Generates daily Indian English audio briefing using Sarvam Bulbul:v3 into Google Drive.
 * 
 * Setup Instructions:
 * 1. Open https://script.google.com and create a new project.
 * 2. Paste this entire code into Code.gs.
 * 3. In Script Settings -> Script Properties (or fill in the constants below):
 *    - NOTION_TOKEN
 *    - NOTION_DATABASE_ID
 *    - SARVAM_API_KEY
 * 4. Click Triggers (clock icon on the left) -> Add Trigger:
 *    - Function: runJobHelper30MinSync
 *    - Event source: Time-driven
 *    - Type of based trigger: Minutes timer
 *    - Minute interval: Every 30 minutes
 *    - Save.
 */

// Configuration (Read from Script Properties or defaults)
function getConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    NOTION_TOKEN: props.getProperty("NOTION_TOKEN") || "YOUR_NOTION_TOKEN_HERE",
    NOTION_DATABASE_ID: props.getProperty("NOTION_DATABASE_ID") || "4083c29f-1b20-801d-9edb-e0a791f3c75c",
    SARVAM_API_KEY: props.getProperty("SARVAM_API_KEY") || "YOUR_SARVAM_API_KEY_HERE",
    ENABLE_AUDIO_BRIEFING: false // set true to save .wav briefings to Google Drive
  };
}

function isExcludedSender(fromH) {
  const fromLow = (fromH || "").toLowerCase();
  const userEmail = Session.getActiveUser().getEmail().toLowerCase();
  
  // 1. User's own email address (dynamically from active Google account)
  if (userEmail && fromLow.includes(userEmail)) return true;

  // 2. Official Government, Tax, Statutory TLDs (.gov, .gov.in, .nic.in, .mil)
  if (/@(?:[a-zA-Z0-9-]+\.)*(?:gov(?:\.[a-z]{2})?|nic\.in|mil)\b/.test(fromLow)) return true;

  // 3. Known infrastructure non-employers
  if (fromLow.includes("accounts.google.com") || fromLow.includes("ads-noreply") || fromLow.includes("glassdoor.com")) return true;

  return false;
}

const EXCLUDE_PATTERNS = [
  /\b(?:pan\s*card|pan\s*application|intimation\s*of\s*pan|police\s*verification|passport|income\s*tax|itr|aadhaar|form\s*16|e-filing)\b/i,
  /\b(?:verification code|security code|password reset|confirm your email|sign[- ]in code|2fa|otp)\b/i,
  /\b(?:study abroad|scholarship|admissions?|degree application)\b/i,
  /\b(?:talent community|job alert|recommended jobs|weekly alert|newsletter)\b/i
];

function runJobHelper30MinSync() {
  const config = getConfig();
  const userProps = PropertiesService.getUserProperties();
  const lastCheckMs = parseInt(userProps.getProperty("LAST_CHECK_MS") || "0", 10);
  const nowMs = Date.now();

  Logger.log("Starting Job Helper 30-Minute Cloud Sync Cycle...");

  // Search recruitment emails from the last 2 days
  const query = 'newer_than:2d (subject:"job application" OR subject:"interview" OR subject:"assessment" OR subject:"candidacy" OR subject:"application was sent" OR subject:"acknowledgement" OR subject:"application received" OR from:jobs-noreply@linkedin.com OR from:myworkday.com OR from:ashbyhq.com OR from:greenhouse.io OR from:lever.co OR from:hackerrank.net)';
  const threads = GmailApp.search(query, 0, 25);

  let maxMsgMs = lastCheckMs;
  const processedEmails = [];

  for (const thread of threads) {
    const messages = thread.getMessages();
    for (const msg of messages) {
      const msgDateMs = msg.getDate().getTime();
      if (lastCheckMs > 0 && msgDateMs <= lastCheckMs) {
        continue;
      }
      if (msgDateMs > maxMsgMs) {
        maxMsgMs = msgDateMs;
      }

      const fromH = msg.getFrom();
      const subj = msg.getSubject();
      const body = msg.getPlainBody();

      // Check exclusions (government, tax, self-email, verification codes)
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

  Logger.log(`Found ${processedEmails.length} new candidate emails to process.`);
  if (processedEmails.length === 0) {
    userProps.setProperty("LAST_CHECK_MS", nowMs.toString());
    return;
  }

  // 1. Fetch current active companies from Notion for reverse matching
  const activeCompanies = getNotionCompanies(config);
  Logger.log(`Loaded ${activeCompanies.length} active companies from Notion.`);

  let createdCount = 0;
  let updatedCount = 0;

  for (const item of processedEmails) {
    // 2. Extract using Hybrid Regex / Sarvam AI
    const extracted = extractWithHybridSarvam(item, config, activeCompanies);
    if (!extracted || !extracted.company) continue;

    const compNorm = normalizeString(extracted.company);
    const existingRow = activeCompanies.find(c => normalizeString(c.company) === compNorm);

    if (!existingRow) {
      // Net-new application
      if (createNotionApplication(extracted, config)) {
        createdCount++;
        activeCompanies.push({ company: extracted.company, id: null });
      }
    } else {
      // Existing application update
      if (extracted.stage && extracted.stage !== "Submitted") {
        if (updateNotionStage(existingRow.id, extracted, config)) {
          updatedCount++;
        }
      }
    }

    // 3. If interview or assessment with deadline -> Schedule on Google Calendar
    if (extracted.event_datetime || extracted.deadline_date) {
      scheduleOnGoogleCalendar(extracted);
    }
  }

  // Update check timestamp
  userProps.setProperty("LAST_CHECK_MS", maxMsgMs.toString());
  Logger.log(`Sync complete. Created: ${createdCount}, Updated: ${updatedCount}`);

  // 4. (Optional) Sarvam Audio Briefing
  if (config.ENABLE_AUDIO_BRIEFING && (createdCount > 0 || updatedCount > 0)) {
    generateSarvamDriveBriefing(createdCount, updatedCount, config);
  }
}

// Normalize strings for reliable deduplication
function normalizeString(str) {
  return (str || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

// Hybrid Extractor: Fast regex + Sarvam 105b fallback
function extractWithHybridSarvam(item, config, activeCompanies) {
  const fromH = item.from;
  const subj = item.subject;
  const body = item.body;
  const dateStr = Utilities.formatDate(item.date, Session.getScriptTimeZone(), "yyyy-MM-dd");

  let company = "";
  let role = "Software Engineer / Intern";
  let stage = "Submitted";

  // A. Fast LinkedIn Match
  if (fromH.toLowerCase().includes("linkedin")) {
    const m = subj.match(/your application was sent to\s+(.+)/i);
    if (m) {
      company = m[1].trim();
      return { company, role, stage, dateStr };
    }
  }

  // B. Relay ATS / Non-typical ATS / Complex Invitations -> Route to Sarvam 105b
  const isRelay = /ashby|greenhouse|lever|hackerrank|codility|smartrecruiters|oraclecloud|taleo|icims/i.test(fromH);
  const isStageEvent = /interview|assessment|candidacy|update on your|test|rejection|shortlist/i.test(subj);
  const isGenericReceipt = /acknowledgement|candidate home|application received|application update|thank you for applying/i.test(subj);

  if ((isRelay || isStageEvent || isGenericReceipt || !company) && config.SARVAM_API_KEY) {
    const compList = activeCompanies.map(c => c.company).slice(0, 50).join(", ");
    const prompt = `Analyze this job application email.
Extract the company name, role, and lifecycle stage.
Applied companies reference list: [${compList}]

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
  "meeting_link": "URL or null"
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
      let text = resJson.choices[0].message.content.trim();
      if (text.includes("```json")) text = text.split("```json")[1].split("```")[0].trim();
      else if (text.includes("```")) text = text.split("```")[1].split("```")[0].trim();
      
      const parsed = JSON.parse(text);
      parsed.dateStr = dateStr;
      return parsed;
    } catch (e) {
      Logger.log("Sarvam extraction fallback error: " + e.message);
    }
  }

  // Basic fallback
  return {
    company: fromH.split("<")[0].replace(/\"/g, "").trim(),
    role: subj.substring(0, 50),
    stage: "Submitted",
    dateStr: dateStr
  };
}

// Fetch active companies from Notion database
function getNotionCompanies(config) {
  const url = `https://api.notion.com/v1/databases/${config.NOTION_DATABASE_ID}/query`;
  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      "Authorization": `Bearer ${config.NOTION_TOKEN}`,
      "Notion-Version": "2022-06-28"
    },
    payload: JSON.stringify({ page_size: 100 }),
    muteHttpExceptions: true
  };

  const list = [];
  try {
    const res = UrlFetchApp.fetch(url, options);
    const data = JSON.parse(res.getContentText());
    for (const p of data.results || []) {
      const titles = (p.properties.Company || {}).title || [];
      const name = titles.length > 0 ? titles[0].plain_text : "";
      if (name) list.push({ company: name, id: p.id });
    }
  } catch (e) {
    Logger.log("Notion query error: " + e.message);
  }
  return list;
}

// Create new Notion row
function createNotionApplication(data, config) {
  const url = "https://api.notion.com/v1/pages";
  const payload = {
    parent: { database_id: config.NOTION_DATABASE_ID },
    properties: {
      "Company": { title: [{ text: { content: data.company } }] },
      "Role": { rich_text: [{ text: { content: data.role || "Software Engineer / Intern" } }] },
      "Applied Date": { date: { start: data.dateStr } },
      "Portal": { select: { name: "Career Portal" } },
      "Status": { status: { name: "Submitted" } }
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
    return resp.getResponseCode() === 200;
  } catch (e) {
    Logger.log("Notion create error: " + e.message);
    return false;
  }
}

// Update existing Notion page
function updateNotionStage(pageId, data, config) {
  const url = `https://api.notion.com/v1/pages/${pageId}`;
  const props = {
    "Updated Status": { status: { name: data.stage } },
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
    return resp.getResponseCode() === 200;
  } catch (e) {
    Logger.log("Notion update error: " + e.message);
    return false;
  }
}

// Schedule Interview or Assessment deadline on Google Calendar
function scheduleOnGoogleCalendar(data) {
  try {
    const cal = CalendarApp.getDefaultCalendar();
    const title = `[Interview] ${data.company} - ${data.role || "Discussion"}`;
    const desc = `Stage: ${data.stage}\nMeeting Link: ${data.meeting_link || "Check email details"}`;

    if (data.event_datetime) {
      const start = new Date(data.event_datetime);
      const end = new Date(start.getTime() + 45 * 60 * 1000); // 45-min default
      const event = cal.createEvent(title, start, end, { description: desc });
      event.addPopupReminder(30);
      Logger.log(`Created Calendar Event: ${title} at ${start}`);
    } else if (data.deadline_date) {
      const d = new Date(data.deadline_date);
      const event = cal.createAllDayEvent(`[Deadline] ${data.company} Assessment`, d, { description: desc });
      Logger.log(`Created All-Day Calendar Event for deadline: ${d}`);
    }
  } catch (e) {
    Logger.log("Calendar scheduling error: " + e.message);
  }
}

// Optional: Sarvam Bulbul:v3 audio brief to Google Drive
function generateSarvamDriveBriefing(created, updated, config) {
  try {
    const summary = `Hello Harsha. Job Helper cloud sync finished. Added ${created} new applications and updated ${updated} stage transitions.`;
    const resp = UrlFetchApp.fetch("https://api.sarvam.ai/text-to-speech", {
      method: "post",
      contentType: "application/json",
      headers: { "api-subscription-key": config.SARVAM_API_KEY },
      payload: JSON.stringify({
        inputs: [summary],
        target_language_code: "en-IN",
        speaker: "kavya",
        model: "bulbul:v3"
      }),
      muteHttpExceptions: true
    });

    const json = JSON.parse(resp.getContentText());
    if (json.audios && json.audios.length > 0) {
      const blob = Utilities.newBlob(Utilities.base64Decode(json.audios[0]), "audio/wav", `job_sync_${Date.now()}.wav`);
      const folder = DriveApp.getFoldersByName("JobHelper_Briefings").hasNext()
        ? DriveApp.getFoldersByName("JobHelper_Briefings").next()
        : DriveApp.createFolder("JobHelper_Briefings");
      folder.createFile(blob);
      Logger.log("Saved Sarvam audio briefing to Google Drive folder 'JobHelper_Briefings'");
    }
  } catch (e) {
    Logger.log("Sarvam TTS error: " + e.message);
  }
}
