/**
 * =========================================================================
 * Job Helper OS: Distributed Cloud Bridge (Google Apps Script)
 * =========================================================================
 * 
 * Part of the Distributed Architecture:
 * 1. Inbound Sensor: Watches Gmail -> pings GitHub Actions (Python + Sarvam 105b).
 * 2. Outbound Calendar Sync: Reads deadlines/interviews from Notion -> creates
 *    Google Calendar events natively with 0 OAuth complexity!
 * 
 * -------------------------------------------------------------------------
 * SETUP INSTRUCTIONS (Takes 2 minutes)
 * -------------------------------------------------------------------------
 * 1. Open https://script.google.com and open/create your project.
 * 2. Paste this entire code into Code.gs.
 * 3. Update the credentials in setupScriptProperties() below and click "Run".
 * 4. Add Triggers (Clock icon on left sidebar):
 *    - Trigger 1: "checkRecentEmailsAndTrigger" -> Time-driven -> Every 5 to 15 minutes.
 *    - Trigger 2: "syncNotionToGoogleCalendar"  -> Time-driven -> Every 30 to 60 minutes.
 * =========================================================================
 */

const GITHUB_OWNER = "injetiharsha";
const GITHUB_REPO = "job-helper";

function getConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    GITHUB_PAT: props.getProperty("GITHUB_PAT") || "YOUR_GITHUB_PAT_HERE",
    NOTION_TOKEN: props.getProperty("NOTION_TOKEN") || "YOUR_NOTION_TOKEN_HERE",
    NOTION_DATABASE_ID: props.getProperty("NOTION_DATABASE_ID") || "4083c29f-1b20-801d-9edb-e0a791f3c75c"
  };
}

/**
 * One-time credential saver into Google Cloud secure storage
 */
function setupScriptProperties() {
  PropertiesService.getScriptProperties().setProperties({
    "GITHUB_PAT": "ghp_YOUR_PERSONAL_ACCESS_TOKEN_HERE",
    "NOTION_TOKEN": "YOUR_NOTION_TOKEN_HERE",
    "NOTION_DATABASE_ID": "4083c29f-1b20-801d-9edb-e0a791f3c75c"
  });
  Logger.log("✅ Credentials securely saved to Script Properties!");
}

// -------------------------------------------------------------------------
// PART 1: INBOUND GMAIL SENSOR -> GITHUB ACTIONS TRIGGER
// -------------------------------------------------------------------------

function isExcludedSender(fromH) {
  const fromLow = (fromH || "").toLowerCase();
  const userEmail = Session.getActiveUser().getEmail().toLowerCase();

  if (userEmail && fromLow.includes(userEmail)) return true;
  if (/@(?:[a-zA-Z0-9-]+\.)*(?:gov(?:\.[a-z]{2})?|nic\.in|mil)\b/.test(fromLow)) return true;
  if (fromLow.includes("accounts.google.com") || fromLow.includes("ads-noreply") || fromLow.includes("glassdoor.com")) return true;

  return false;
}

const EXCLUDE_PATTERNS = [
  /\b(?:pan\s*card|pan\s*application|intimation\s*of\s*pan|passport|income\s*tax|itr|aadhaar|form\s*16|e-filing)\b/i,
  /\b(?:verification code|security code|password reset|confirm your email|sign[- ]in code|2fa|otp)\b/i,
  /\b(?:study abroad|scholarship|admissions?|degree application)\b/i,
  /\b(?:talent community|job alert|recommended jobs|weekly alert|newsletter)\b/i
];

function checkRecentEmailsAndTrigger() {
  const config = getConfig();
  const userProps = PropertiesService.getUserProperties();
  const lastCheck = parseInt(userProps.getProperty("LAST_CHECK_MS") || "0", 10);
  const nowMs = Date.now();

  Logger.log("Checking Gmail for new recruitment emails...");

  const query = 'newer_than:1d (subject:"job application" OR subject:"interview" OR subject:"assessment" OR subject:"candidacy" OR subject:"application was sent" OR subject:"acknowledgement" OR subject:"application received" OR from:jobs-noreply@linkedin.com OR from:myworkday.com OR from:ashbyhq.com OR from:greenhouse.io OR from:lever.co OR from:hackerrank.net)';
  const threads = GmailApp.search(query, 0, 20);

  let newEmailFound = false;
  let newestMsgMs = lastCheck;

  for (const thread of threads) {
    const messages = thread.getMessages();
    for (const msg of messages) {
      const msgDateMs = msg.getDate().getTime();
      if (msgDateMs > lastCheck) {
        const fromH = msg.getFrom();
        const subj = msg.getSubject();
        const body = msg.getPlainBody();

        if (isExcludedSender(fromH)) continue;
        if (EXCLUDE_PATTERNS.some(pat => pat.test(subj) || pat.test(body.substring(0, 300)))) continue;

        newEmailFound = true;
        if (msgDateMs > newestMsgMs) {
          newestMsgMs = msgDateMs;
        }
      }
    }
  }

  if (lastCheck === 0) {
    userProps.setProperty("LAST_CHECK_MS", nowMs.toString());
    Logger.log("Initialized last check timestamp. Will trigger GitHub Actions on subsequent emails.");
    return;
  }

  if (!newEmailFound) {
    Logger.log("No new recruitment emails found since last check. Skipping GitHub trigger.");
    return;
  }

  userProps.setProperty("LAST_CHECK_MS", newestMsgMs.toString());
  triggerGitHubAction("gmail_sensor", config);
}

function triggerGitHubAction(source, config) {
  if (!config) config = getConfig();
  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`;
  const payload = {
    event_type: "job_application_received",
    client_payload: {
      source: source || "cloud_bridge",
      timestamp: new Date().toISOString()
    }
  };

  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      "Authorization": `Bearer ${config.GITHUB_PAT}`,
      "Accept": "application/vnd.github+json"
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(url, options);
  const code = response.getResponseCode();
  if (code === 204) {
    Logger.log("✅ Success! GitHub Actions workflow triggered.");
  } else {
    Logger.log(`❌ GitHub Dispatch failed (${code}): ${response.getContentText()}`);
  }
}

function forceTriggerGitHubAction() {
  Logger.log("Sending manual test dispatch to GitHub Actions...");
  triggerGitHubAction("manual_test", getConfig());
}

// -------------------------------------------------------------------------
// PART 2: OUTBOUND NOTION -> GOOGLE CALENDAR SYNC (Native CalendarApp)
// -------------------------------------------------------------------------

function syncNotionToGoogleCalendar() {
  const config = getConfig();
  Logger.log("Checking Notion for upcoming interviews & deadlines to sync to Calendar...");

  const url = `https://api.notion.com/v1/databases/${config.NOTION_DATABASE_ID}/query`;
  const payload = {
    page_size: 100,
    filter: {
      property: "Deadline / Event Date",
      date: { is_not_empty: true }
    }
  };

  let rows = [];
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
    const data = JSON.parse(resp.getContentText());
    rows = data.results || [];
  } catch (e) {
    Logger.log("Notion query error: " + e.message);
    return;
  }

  Logger.log(`Found ${rows.length} rows with deadlines/event dates.`);
  const cal = CalendarApp.getDefaultCalendar();
  let syncedCount = 0;

  for (const page of rows) {
    const props = page.properties;
    const titleArr = (props.Company || {}).title || [];
    const company = titleArr.length > 0 ? titleArr[0].plain_text : "Job Interview";

    const roleArr = (props.Role || {}).rich_text || [];
    const role = roleArr.length > 0 ? roleArr[0].plain_text : "Discussion";

    const deadlineObj = (props["Deadline / Event Date"] || {}).date || {};
    const deadlineStr = deadlineObj.start;
    if (!deadlineStr) continue;

    const statusObj = props["Updated Status"] || props["Status"] || {};
    const stage = (statusObj.select || statusObj.status || {}).name || "Interview";

    // Read JSON metadata to check if already synced
    const jsonArr = (props.JSON || {}).rich_text || [];
    const jsonRaw = jsonArr.length > 0 ? jsonArr[0].plain_text : "";
    let meta = {};
    if (jsonRaw) {
      try { meta = JSON.parse(jsonRaw); } catch (e) { }
    }

    if (meta.calendar_synced === true) {
      continue; // Already scheduled
    }

    const meetingLink = meta.meeting_link || "Check email details";
    const title = `[${stage}] ${company} - ${role}`;
    const desc = `Stage: ${stage}\nCompany: ${company}\nRole: ${role}\nMeeting Link: ${meetingLink}`;

    try {
      let createdEvent;
      if (deadlineStr.length > 10) {
        // Specific time (ISO-8601: YYYY-MM-DDTHH:MM:SS)
        const start = new Date(deadlineStr);
        const end = new Date(start.getTime() + 45 * 60 * 1000); // 45-min default
        createdEvent = cal.createEvent(title, start, end, { description: desc });
        createdEvent.addPopupReminder(30);
      } else {
        // Date only (YYYY-MM-DD) -> All-Day Event
        const d = new Date(deadlineStr);
        createdEvent = cal.createAllDayEvent(`[Deadline] ${company} - ${role}`, d, { description: desc });
      }

      meta.calendar_synced = true;
      meta.calendar_event_id = createdEvent.getId();

      // Update Notion row with calendar_synced flag
      updateNotionMetadata(page.id, meta, config);
      syncedCount++;
      Logger.log(`📅 Created Calendar Event: ${title} (${deadlineStr})`);
    } catch (e) {
      Logger.log(`Calendar error for ${company}: ${e.message}`);
    }
  }

  Logger.log(`Calendar sync finished. Newly scheduled: ${syncedCount}`);
}

function updateNotionMetadata(pageId, meta, config) {
  const url = `https://api.notion.com/v1/pages/${pageId}`;
  UrlFetchApp.fetch(url, {
    method: "patch",
    contentType: "application/json",
    headers: {
      "Authorization": `Bearer ${config.NOTION_TOKEN}`,
      "Notion-Version": "2022-06-28"
    },
    payload: JSON.stringify({
      properties: {
        "JSON": { rich_text: [{ text: { content: JSON.stringify(meta) } }] }
      }
    }),
    muteHttpExceptions: true
  });
}
