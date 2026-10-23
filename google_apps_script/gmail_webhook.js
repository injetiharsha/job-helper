/**
 * Google Apps Script: Smart Gmail to GitHub Action Webhook Trigger
 *
 * How it works:
 * 1. Runs every 5 minutes on a lightweight time-driven trigger.
 * 2. Checks if ANY new recruitment email arrived since the last check.
 * 3. ONLY fires the GitHub webhook when a NEW email actually arrives!
 *    (If no new email arrived, it exits immediately without triggering GitHub).
 */

const GITHUB_OWNER = "injetiharsha";
const GITHUB_REPO = "job-helper";
const GITHUB_PAT = "ghp_YOUR_PERSONAL_ACCESS_TOKEN_HERE";

function checkRecentEmailsAndTrigger() {
  const userProps = PropertiesService.getUserProperties();
  const lastCheck = parseInt(userProps.getProperty("LAST_CHECK_MS") || "0", 10);
  const nowMs = Date.now();

  // Search recruitment emails from the last 1 day, explicitly excluding non-job documents
  const query = 'newer_than:1d (subject:"job application" OR subject:"interview" OR subject:"assessment" OR subject:"candidacy" OR subject:"application was sent" OR from:jobs-noreply@linkedin.com OR from:myworkday.com) -subject:PAN -subject:Passport -subject:Verification -subject:"Study Abroad" -subject:"IIT Madras" -from:glassdoor.com';
  const threads = GmailApp.search(query, 0, 15);

  let newEmailFound = false;
  let newestMsgMs = lastCheck;

  for (const thread of threads) {
    const messages = thread.getMessages();
    for (const msg of messages) {
      const msgDateMs = msg.getDate().getTime();
      // If message arrived after our last check timestamp
      if (msgDateMs > lastCheck) {
        newEmailFound = true;
        if (msgDateMs > newestMsgMs) {
          newestMsgMs = msgDateMs;
        }
      }
    }
  }

  // If this is the very first time the script runs, initialize timestamp to current time
  if (lastCheck === 0) {
    userProps.setProperty("LAST_CHECK_MS", nowMs.toString());
    Logger.log("Initialized last check timestamp. Webhook will fire on subsequent new incoming emails.");
    return;
  }

  // If no new emails arrived since last check, exit without triggering GitHub
  if (!newEmailFound) {
    Logger.log("No new recruitment emails arrived since last check. Skipping GitHub trigger.");
    return;
  }

  // Update last seen timestamp so we don't trigger again for the same email
  userProps.setProperty("LAST_CHECK_MS", newestMsgMs.toString());

  // Fire GitHub Actions repository_dispatch
  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`;
  const payload = {
    event_type: "job_application_received",
    client_payload: {
      source: "gmail_webhook",
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
  Logger.log(`New recruitment email detected! GitHub Dispatch Triggered. Response code: ${response.getResponseCode()}`);
}

/**
 * Helper to reset timestamp if you ever want to force a re-trigger test
 */
function resetLastCheckTimestamp() {
  PropertiesService.getUserProperties().deleteProperty("LAST_CHECK_MS");
  Logger.log("Timestamp reset. Next run will scan recent emails.");
}
