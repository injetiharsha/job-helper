/**
 * =========================================================================
 * Google Apps Script: Smart Gmail -> GitHub Actions Webhook Trigger
 * =========================================================================
 *
 * How it works:
 * 1. Runs every 5 to 15 minutes on a lightweight time-driven trigger.
 * 2. Checks if ANY new recruitment email arrived since the last check.
 * 3. Uses generic filters to ignore government (.gov, .nic.in), tax, 2FA, & newsletters.
 * 4. When a new email arrives, fires GitHub Actions `repository_dispatch` webhook!
 * 5. GitHub Actions then runs the full Python Job Helper v2 engine with Sarvam 105b!
 *
 * Setup Instructions:
 * 1. Paste this into your Google Apps Script project (Code.gs).
 * 2. Fill in your GITHUB_PAT below (or save GITHUB_PAT in Script Properties).
 * 3. Click "forceTriggerGitHubAction" and run it to test triggering GitHub Actions immediately!
 * 4. Add a Time-Driven Trigger on "checkRecentEmailsAndTrigger" to run every 5-15 minutes.
 */

const GITHUB_OWNER = "injetiharsha";
const GITHUB_REPO = "job-helper";
const GITHUB_PAT = PropertiesService.getScriptProperties().getProperty("GITHUB_PAT") || "ghp_YOUR_PERSONAL_ACCESS_TOKEN_HERE";

/**
 * Generic Sender Exclusion:
 * Drops official government/statutory domains (.gov, .nic.in, .mil) and candidate's own email.
 */
function isExcludedSender(fromH) {
  const fromLow = (fromH || "").toLowerCase();
  const userEmail = Session.getActiveUser().getEmail().toLowerCase();

  // User's own email
  if (userEmail && fromLow.includes(userEmail)) return true;

  // Government, tax, official statutory TLDs (.gov, .gov.in, .nic.in, .mil)
  if (/@(?:[a-zA-Z0-9-]+\.)*(?:gov(?:\.[a-z]{2})?|nic\.in|mil)\b/.test(fromLow)) return true;

  // Generic non-employer infrastructure & aggregators
  if (fromLow.includes("accounts.google.com") || fromLow.includes("ads-noreply") || fromLow.includes("glassdoor.com")) return true;

  return false;
}

const EXCLUDE_PATTERNS = [
  /\b(?:pan\s*card|pan\s*application|intimation\s*of\s*pan|police\s*verification|passport|income\s*tax|itr|aadhaar|form\s*16|e-filing|voter\s*id)\b/i,
  /\b(?:verification code|security code|password reset|confirm your email|sign[- ]in code|2fa|otp)\b/i,
  /\b(?:study abroad|scholarship|admissions?|degree application)\b/i,
  /\b(?:talent community|job alert|recommended jobs|weekly alert|newsletter)\b/i
];

function checkRecentEmailsAndTrigger() {
  const userProps = PropertiesService.getUserProperties();
  const lastCheck = parseInt(userProps.getProperty("LAST_CHECK_MS") || "0", 10);
  const nowMs = Date.now();

  Logger.log("Checking for incoming recruitment emails...");

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

        // Generic filters
        if (isExcludedSender(fromH)) continue;
        if (EXCLUDE_PATTERNS.some(pat => pat.test(subj) || pat.test(body.substring(0, 300)))) continue;

        newEmailFound = true;
        if (msgDateMs > newestMsgMs) {
          newestMsgMs = msgDateMs;
        }
      }
    }
  }

  // Initialize timestamp on first run
  if (lastCheck === 0) {
    userProps.setProperty("LAST_CHECK_MS", nowMs.toString());
    Logger.log("Initialized last check timestamp. Webhook will fire on subsequent incoming emails.");
    return;
  }

  if (!newEmailFound) {
    Logger.log("No new recruitment emails arrived since last check. Skipping GitHub trigger.");
    return;
  }

  // Update timestamp so we don't fire duplicate actions for the same email
  userProps.setProperty("LAST_CHECK_MS", newestMsgMs.toString());

  // Fire GitHub Actions repository_dispatch
  triggerGitHubAction("gmail_webhook");
}

/**
 * Fires the GitHub repository_dispatch webhook to wake up GitHub Actions
 */
function triggerGitHubAction(source) {
  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`;
  const payload = {
    event_type: "job_application_received",
    client_payload: {
      source: source || "manual_trigger",
      timestamp: new Date().toISOString()
    }
  };

  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      "Authorization": `Bearer ${GITHUB_PAT}`,
      "Accept": "application/vnd.github+json"
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(url, options);
  const code = response.getResponseCode();
  Logger.log(`GitHub Dispatch Triggered. Response code: ${code}`);
  if (code === 204) {
    Logger.log("✅ Success! GitHub Action workflow is now running.");
  } else {
    Logger.log(`❌ Failed: ${response.getContentText()}`);
  }
}

/**
 * Manual Test Function:
 * Select "forceTriggerGitHubAction" in the dropdown and click Run to test your webhook!
 */
function forceTriggerGitHubAction() {
  Logger.log("Sending test dispatch to GitHub Actions...");
  triggerGitHubAction("manual_test");
}

function resetLastCheckTimestamp() {
  PropertiesService.getUserProperties().deleteProperty("LAST_CHECK_MS");
  Logger.log("Timestamp reset. Next run will scan recent emails.");
}
