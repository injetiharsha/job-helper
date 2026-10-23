/**
 * Google Apps Script: Instant Gmail to GitHub Action Webhook Trigger
 *
 * Setup:
 * 1. Go to https://script.google.com/ and create a new project.
 * 2. Paste this code.
 * 3. Replace YOUR_GITHUB_PAT with a GitHub Personal Access Token (with 'repo' scope).
 * 4. In Apps Script, click Triggers (clock icon) -> Add Trigger:
 *    - Function: checkRecentEmailsAndTrigger
 *    - Event Source: Time-driven -> Every 5 minutes or 10 minutes.
 */

const GITHUB_OWNER = "injetiharsha";
const GITHUB_REPO = "job-helper";
const GITHUB_PAT = "ghp_YOUR_PERSONAL_ACCESS_TOKEN_HERE";

function checkRecentEmailsAndTrigger() {
  // Search for application or interview emails in the last 15 minutes
  const query = 'newer_than:1d (subject:application OR subject:interview OR subject:assessment OR from:jobs-noreply@linkedin.com)';
  const threads = GmailApp.search(query, 0, 10);

  if (threads.length === 0) {
    Logger.log("No new recruitment emails detected.");
    return;
  }

  // Trigger GitHub Actions repository_dispatch
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
  Logger.log(`GitHub Dispatch Triggered. Response code: ${response.getResponseCode()}`);
}
