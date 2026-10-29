import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from src.core.config import SARVAM_API_KEY, SARVAM_CHAT_MODEL

class SarvamClient:
    """
    Client for Sarvam AI LLM (sarvam-105b):
    Used purely for text entity extraction and edge-case resolution.
    """

    def __init__(self):
        self.api_key = SARVAM_API_KEY
        self.is_configured = bool(self.api_key and not self.api_key.startswith("your_"))

    def _clean_json_response(self, text: str) -> Dict[str, Any]:
        """Strips markdown fences and parses JSON safely."""
        if not text:
            return {}
        text = str(text).strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        try:
            return json.loads(text)
        except Exception:
            # Fallback regex extraction of JSON object
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            return {}

    def _call_chat(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        if not self.is_configured:
            return ""

        url = "https://api.sarvam.ai/v1/chat/completions"
        payload = {
            "model": SARVAM_CHAT_MODEL,
            "messages": messages,
            "temperature": temperature
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": self.api_key
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices") or []
                if choices and isinstance(choices, list):
                    msg = choices[0].get("message") or {}
                    content = msg.get("content")
                    if content is not None:
                        return str(content).strip()
                return ""
        except Exception as e:
            print(f"[Sarvam Chat Error]: {e}")
            return ""

    def resolve_application_details(self, subject: str, body_text: str, from_header: str) -> Dict[str, Any]:
        """
        Resolves missed or messy application receipts (e.g. Valeo, custom enterprise portals)
        where standard regex fails.
        """
        if not self.is_configured:
            return {}

        prompt = (
            "You are a recruitment data extractor. Analyze this job application acknowledgment email.\n"
            "Extract the exact Company Name and the Job Title/Role.\n"
            "Guidelines:\n"
            "1. Company should be the actual hiring organization (e.g., 'Valeo', 'Novartis', 'GE HealthCare').\n"
            "2. Do NOT use ATS vendor names like 'Workday', 'SuccessFactors', 'MyWorkdayJobs', 'LinkedIn'.\n"
            "3. If this email is NOT a job application confirmation, set is_application to false.\n\n"
            f"Sender: {from_header}\n"
            f"Subject: {subject}\n"
            f"Email snippet:\n{body_text[:1800]}\n\n"
            "Return ONLY a valid JSON object matching:\n"
            "{\n"
            '  "is_application": true,\n'
            '  "company": "Company Name",\n'
            '  "role": "Role Title"\n'
            "}"
        )

        raw = self._call_chat([
            {"role": "system", "content": "You are a precise JSON extractor. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ])

        return self._clean_json_response(raw)

    def resolve_stage_event(
        self,
        subject: str,
        body_text: str,
        from_header: str,
        date_str: str,
        active_companies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extracts interview dates, assessments, or rejections from unstructured emails or relay ATS domains.
        """
        if not self.is_configured:
            return {}

        companies_hint = ""
        if active_companies:
            companies_hint = f"\nCandidate previously applied to these companies:\n{', '.join(active_companies[:80])}\n"

        prompt = (
            "Analyze this recruitment email. Identify if it represents a hiring lifecycle event:\n"
            "- Assessment Invitation (HackerRank, Codility, TestGorilla, etc.)\n"
            "- Recruiter Screen / Interview Invitation / Reschedule\n"
            "- Rejection Notice\n"
            "- General Update / Under Review\n\n"
            f"Sender: {from_header}\n"
            f"Subject: {subject}\n"
            f"Email Date: {date_str}\n"
            f"{companies_hint}\n"
            f"Email content:\n{body_text[:2200]}\n\n"
            "Classify stage into exactly one of:\n"
            '["Assessment", "Recruiter Screen", "Technical Round", "Final Round", "Offer", "Rejected", "Under Review", "None"]\n\n'
            "Return ONLY a valid JSON object matching:\n"
            "{\n"
            '  "is_lifecycle_event": true,\n'
            '  "company": "Hiring Company Name",\n'
            '  "role": "Role Title or null",\n'
            '  "stage": "Stage Name",\n'
            '  "event_datetime": "ISO-8601 string like 2026-11-04T15:00:00 or null",\n'
            '  "deadline_date": "YYYY-MM-DD string or null",\n'
            '  "meeting_link": "Google Meet / MS Teams / Zoom URL or null",\n'
            '  "requires_user_reply": false\n'
            "}"
        )

        raw = self._call_chat([
            {"role": "system", "content": "You are a precise JSON extractor for recruitment workflows. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ])

        return self._clean_json_response(raw)
