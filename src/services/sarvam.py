import json
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.core.config import SARVAM_API_KEY, SARVAM_CHAT_MODEL, BASE_DIR

TELEMETRY_FILE = BASE_DIR / "telemetry.json"

# Sarvam 105b Effective Rates (in INR per 1,000 tokens)
RATE_INPUT_PER_1K = 0.015
RATE_CACHED_PER_1K = 0.005
RATE_OUTPUT_PER_1K = 0.060

class SarvamClient:
    """
    Client for Sarvam AI LLM (sarvam-105b):
    Used purely for text entity extraction and edge-case resolution.
    Includes built-in per-call character, token, and cost telemetry logging.
    """

    def __init__(self):
        self.api_key = SARVAM_API_KEY
        self.is_configured = bool(self.api_key and not self.api_key.startswith("your_"))
        self.session_telemetry: List[Dict[str, Any]] = []

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

    def _call_chat(self, messages: List[Dict[str, str]], action: str = "chat", context: str = "", temperature: float = 0.1) -> str:
        if not self.is_configured:
            return ""

        url = "https://api.sarvam.ai/v1/chat/completions"
        payload = {
            "model": SARVAM_CHAT_MODEL,
            "messages": messages,
            "temperature": temperature
        }

        # Calculate input characters across all messages
        input_chars = sum(len(m.get("content", "")) for m in messages)

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
                
                # Extract output content
                content = ""
                choices = data.get("choices") or []
                if choices and isinstance(choices, list):
                    msg = choices[0].get("message") or {}
                    raw_c = msg.get("content")
                    if raw_c is not None:
                        content = str(raw_c).strip()

                output_chars = len(content)

                # Extract exact usage telemetry returned by Sarvam API
                usage = data.get("usage") or {}
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

                p_details = usage.get("prompt_tokens_details") or {}
                cached_tokens = p_details.get("cached_tokens", 0) or 0

                c_details = usage.get("completion_tokens_details") or {}
                reasoning_tokens = c_details.get("reasoning_tokens", 0) or 0

                # Compute cost in INR
                uncached_prompt = max(0, prompt_tokens - cached_tokens)
                cost_inr = (
                    (uncached_prompt * RATE_INPUT_PER_1K / 1000.0) +
                    (cached_tokens * RATE_CACHED_PER_1K / 1000.0) +
                    (completion_tokens * RATE_OUTPUT_PER_1K / 1000.0)
                )

                record = {
                    "timestamp": datetime.now().isoformat(),
                    "action": action,
                    "context": context[:80],
                    "input_chars": input_chars,
                    "output_chars": output_chars,
                    "prompt_tokens": prompt_tokens,
                    "cached_tokens": cached_tokens,
                    "completion_tokens": completion_tokens,
                    "reasoning_tokens": reasoning_tokens,
                    "total_tokens": total_tokens,
                    "cost_inr": round(cost_inr, 5)
                }

                self.session_telemetry.append(record)
                self._save_telemetry_record(record)

                return content
        except Exception as e:
            print(f"[Sarvam Chat Error]: {e}")
            return ""

    def _save_telemetry_record(self, record: Dict[str, Any]):
        """Persists telemetry records to telemetry.json."""
        try:
            records = []
            if TELEMETRY_FILE.exists():
                try:
                    with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                        records = json.load(f)
                except Exception:
                    records = []
            records.append(record)
            with open(TELEMETRY_FILE, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception:
            pass

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Calculates aggregated telemetry for current run."""
        total_calls = len(self.session_telemetry)
        total_prompt_tokens = sum(r["prompt_tokens"] for r in self.session_telemetry)
        total_cached_tokens = sum(r["cached_tokens"] for r in self.session_telemetry)
        total_completion_tokens = sum(r["completion_tokens"] for r in self.session_telemetry)
        total_tokens = sum(r["total_tokens"] for r in self.session_telemetry)
        total_cost_inr = sum(r["cost_inr"] for r in self.session_telemetry)
        total_input_chars = sum(r["input_chars"] for r in self.session_telemetry)
        total_output_chars = sum(r["output_chars"] for r in self.session_telemetry)

        return {
            "total_calls": total_calls,
            "total_input_chars": total_input_chars,
            "total_output_chars": total_output_chars,
            "total_prompt_tokens": total_prompt_tokens,
            "total_cached_tokens": total_cached_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_cost_inr": round(total_cost_inr, 4),
            "calls": self.session_telemetry
        }

    def print_telemetry_report(self):
        """Prints a clean tabular telemetry audit."""
        summary = self.get_telemetry_summary()
        if summary["total_calls"] == 0:
            print("\n📊 Sarvam Telemetry: 0 API calls required for this cycle (All resolved by Tier 1 regex). Cost: ₹0.00")
            return

        print("\n" + "="*80)
        print("📊 Sarvam AI 105b Per-Call Telemetry & Cost Audit")
        print("="*80)
        for idx, call in enumerate(summary["calls"], 1):
            ctx = f" [{call['context'][:40]}]" if call['context'] else ""
            print(f"Call #{idx:02d} | Action: {call['action']}{ctx}")
            print(f"  • Chars:  Input={call['input_chars']} chars | Output={call['output_chars']} chars")
            cached_info = f" (cached: {call['cached_tokens']})" if call['cached_tokens'] else ""
            reasoning_info = f" (reasoning: {call['reasoning_tokens']})" if call['reasoning_tokens'] else ""
            print(f"  • Tokens: In={call['prompt_tokens']}{cached_info} | Out={call['completion_tokens']}{reasoning_info} | Total={call['total_tokens']}")
            print(f"  • Cost:   ₹{call['cost_inr']:.4f}")
            print("-" * 80)

        print(f"TOTALS:")
        print(f"  • Total API Calls Made:   {summary['total_calls']}")
        print(f"  • Total Characters:       {summary['total_input_chars']} input, {summary['total_output_chars']} output")
        print(f"  • Total Tokens Consumed:  {summary['total_tokens']} tokens ({summary['total_prompt_tokens']} prompt, {summary['total_completion_tokens']} completion)")
        print(f"  • Total Cycle Cost:       ₹{summary['total_cost_inr']:.4f} INR")
        print("="*80)

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

        raw = self._call_chat(
            [
                {"role": "system", "content": "You are a precise JSON extractor. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            action="resolve_application_details",
            context=subject
        )

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

        raw = self._call_chat(
            [
                {"role": "system", "content": "You are a precise JSON extractor for recruitment workflows. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            action="resolve_stage_event",
            context=subject
        )

        return self._clean_json_response(raw)
