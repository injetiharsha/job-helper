import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import quopri
from src.core.config import GMAIL_EMAIL, GMAIL_APP_PASSWORD, LINKEDIN_DEFAULT_URL, COMPANY_CAREER_URLS
from src.core.cleaner import clean_role_title, clean_company_name, GENERIC_COMPANY_NAMES
from src.parsers.linkedin_parser import LinkedInParser
from src.parsers.workday_parser import WorkdayParser
from src.parsers.lifecycle_classifier import LifecycleClassifier
from src.parsers.deadline_parser import DeadlineParser
from src.core.stages import HiringStage
from src.services.sarvam import SarvamClient

def is_excluded_sender(from_header: str) -> bool:
    """
    Identifies non-employer senders generically:
    1. Candidate's own email (dynamic from config).
    2. Official government, statutory, tax, or military TLDs (.gov, .gov.in, .nic.in, .mil).
    3. Non-employer security services and marketing aggregators.
    """
    from_low = from_header.lower()

    # User's own email address
    if GMAIL_EMAIL and GMAIL_EMAIL.lower() in from_low:
        return True

    # Government, official statutory, and tax TLDs (.gov, .gov.in, .nic.in, .mil)
    if re.search(r'@(?:[a-zA-Z0-9-]+\.)*(?:gov(?:\.[a-z]{2})?|nic\.in|mil)\b', from_low):
        return True

    # Generic non-employer infrastructure & aggregators
    if any(d in from_low for d in ['accounts.google.com', 'ads-noreply', 'glassdoor.com']):
        return True

    return False

# Generalized patterns that indicate non-job emails, newsletters, identity documents, or account security
EXCLUDE_PATTERNS = [
    # Statutory Government, Identity, Tax, Police Verification
    r'\b(?:pan\s*card|pan\s*application|intimation\s*of\s*pan|police\s*verification|passport\s*application|passport|income\s*tax|itr|aadhaar|form\s*16|tax\s*deduction|e-filing|voter\s*id)\b',
    
    # Academic Admissions & Study Abroad
    r'\b(?:study\s*abroad|admissions?|scholarship|degree\s*application)\b',

    # Aggregators & Marketing Alerts
    r'\b(?:job\s*alert|recommended\s*jobs|top\s*jobs\s*for\s*you|new\s*jobs\s*posted|interview\s*experiences|weekly\s*alert|talent\s*community|newsletter|apply\s*now|jobs\s*you\s*may\s*(?:like|be\s*interested)|recommended\s*for\s*you)\b',
    
    # Account & Security Verification
    r'\b(?:security\s*code|one-time-passcode|otp|verification\s*code|verify\s*your\s*email|password\s*reset|confirm\s*your\s*email|2fa|sign[- ]in\s*code)\b',
    
    # Surveys & Candidate Home setup
    r'\b(?:survey\s*request|talent\s*acquisition\s*survey|your\s*account\s*has\s*been\s*created)\b',
    
    # Application Withdrawn
    r'\b(?:withdrawn\s+your\s+.*application|withdrew\s+your\s+application)\b'
]

class GmailClient:
    def __init__(self, sarvam_client=None):
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            raise ValueError("Gmail credentials missing in .env")
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.mail.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        self.mail.select('"[Gmail]/All Mail"')
        self.sarvam = sarvam_client or SarvamClient()

    def _decode_header(self, raw_hdr):
        if not raw_hdr: return ""
        res = []
        for frag, enc in decode_header(raw_hdr):
            if isinstance(frag, bytes):
                res.append(frag.decode(enc or 'utf-8', errors='replace'))
            else:
                res.append(str(frag))
        return "".join(res)

    def fetch_recruitment_events(self, since_date_str, active_companies=None):
        """
        Scans for application submissions and lifecycle progression updates.
        Supports active_companies context for resolving 3rd-party ATS relay domains (Ashby, Greenhouse, etc.).
        """
        query = f'(SINCE "{since_date_str}" OR (SUBJECT "interview") (OR (SUBJECT "assessment") (OR (SUBJECT "application") (FROM "jobs-noreply@linkedin.com"))))'
        typ, data = self.mail.search(None, query)
        if typ != 'OK' or not data[0]:
            return [], []

        uids = data[0].split()
        new_applications = []
        status_updates = []

        # Batch fetch 30 UIDs at a time for fast network roundtrips
        batch_size = 30
        for start in range(0, len(uids), batch_size):
            chunk = uids[start:start+batch_size]
            typ, msg_data = self.mail.fetch(b','.join(chunk), '(BODY.PEEK[1] BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            if typ != 'OK':
                continue

            curr_headers = {}
            for item in msg_data:
                if isinstance(item, tuple) and b'HEADER.FIELDS' in item[0]:
                    h = email.message_from_bytes(item[1])
                    curr_headers = {
                        'subject': self._decode_header(h.get('Subject', '')),
                        'from': self._decode_header(h.get('From', '')),
                        'date': h.get('Date', '')
                    }
                elif isinstance(item, tuple) and b'BODY[1]' in item[0]:
                    if not curr_headers:
                        continue
                    raw_b = item[1].decode('utf-8', errors='replace')
                    raw_b = re.sub(r'=\r?\n', '', raw_b)
                    try:
                        raw_b = quopri.decodestring(raw_b.encode('utf-8')).decode('utf-8', errors='replace')
                    except Exception:
                        pass
                    clean_b = re.sub(r'<style[^>]*>.*?</style>', ' ', raw_b, flags=re.DOTALL | re.I)
                    clean_b = re.sub(r'<script[^>]*>.*?</script>', ' ', clean_b, flags=re.DOTALL | re.I)
                    clean_b = re.sub(r'<[^>]+>', ' ', clean_b)
                    clean_b = re.sub(r'[ \t]+', ' ', clean_b)
                    body_text = re.sub(r'\n\s*\n+', '\n', clean_b).strip()

                    subj = curr_headers.get('subject', '').strip()
                    from_h = curr_headers.get('from', '').strip()
                    date_raw = curr_headers.get('date', '')

                    # 1. Skip if sender is blacklisted or user's own email
                    from_low = from_h.lower()
                    if is_excluded_sender(from_h):
                        curr_headers = {}
                        continue

                    # 2. Skip if subject or sender matches non-job exclusion patterns
                    subj_low = subj.lower()
                    combined_headers = f"{subj_low} {from_low}"
                    if any(re.search(pat, combined_headers, re.I) for pat in EXCLUDE_PATTERNS):
                        curr_headers = {}
                        continue

                    # Parse date
                    try:
                        dt = parsedate_to_datetime(date_raw)
                        d_str = dt.strftime('%Y-%m-%d')
                    except Exception:
                        d_str = date_raw[:10]

                    # 1. Classify Hiring Stage
                    stage = LifecycleClassifier.classify_email(subj, body_text)

                    # 2. Extract Company & Role (Tier 1: Fast Regex)
                    if LinkedInParser.is_linkedin_email(from_h):
                        parsed = LinkedInParser.parse(from_h, subj, body_text)
                    elif WorkdayParser.is_workday_email(from_h, body_text):
                        parsed = WorkdayParser.parse(from_h, subj, body_text)
                    else:
                        # General Enterprise Portal
                        comp = clean_company_name(from_h.split('<')[0])
                        # Generic pattern: "Regarding your <Company> Application"
                        m_reg = re.search(r'regarding your\s+([A-Za-z0-9&.\s]+?)\s+application', subj, re.I)
                        if m_reg:
                            c_cand = clean_company_name(m_reg.group(1))
                            if c_cand:
                                comp = c_cand

                        # Domain extraction fallback for generic sender display names (e.g. "Human Resources <...>")
                        if not comp:
                            m_dom = re.search(r'@(?:[a-zA-Z0-9-]+\.)*([a-zA-Z0-9-]+)\.[a-z]{2,}', from_h)
                            if m_dom:
                                dom_cand = m_dom.group(1).lower()
                                if dom_cand not in ['gmail', 'yahoo', 'outlook', 'hotmail', 'myworkday', 'linkedin', 'googlemail', 'tikkodesk']:
                                    comp = clean_company_name(dom_cand.capitalize())
                                elif dom_cand == 'tikkodesk':
                                    comp = 'Tikko Desk'

                        # Dynamic match against candidate's active companies from Notion if sender is generic
                        if not comp and active_companies:
                            for ac in active_companies:
                                if len(ac) > 2 and re.search(r'\b' + re.escape(ac) + r'\b', subj, re.I):
                                    comp = ac
                                    break

                        role = clean_role_title(subj)
                        c_norm = re.sub(r'[^a-zA-Z0-9]', '', (comp or '').lower())
                        parsed = {
                            'company': comp,
                            'role': role or "Software Engineer / Intern",
                            'portal': 'Career Portal',
                            'url': COMPANY_CAREER_URLS.get(c_norm, f"https://www.{c_norm}.com/careers")
                        }

                    # Tier 2: Sarvam AI Resolver Fallback for edge cases (ONLY if company is truly unknown or generic)
                    comp_name = (parsed.get('company') or '').strip()
                    comp_low = comp_name.lower()
                    is_generic_name = (
                        not comp_name
                        or len(comp_name) <= 2
                        or comp_low in GENERIC_COMPANY_NAMES
                        or comp_low in ['careers', 'career', 'jobs', 'application', 'candidate home', 'notifications', 'talent acquisition', 'recruitment', 'team', 'hr', 'workday', 'no-reply', 'noreply', 'applicant', 'recruiting', 'human resources', 'talent', 'hiring team', 'people team']
                    )

                    if is_generic_name and self.sarvam.is_configured:
                        ai_res = self.sarvam.resolve_application_details(subj, body_text, from_h)
                        if ai_res.get('is_application') and ai_res.get('company'):
                            parsed['company'] = clean_company_name(ai_res['company'])
                            if ai_res.get('role'):
                                parsed['role'] = clean_role_title(ai_res['role'])
                            c_norm = re.sub(r'[^a-zA-Z0-9]', '', (parsed.get('company') or '').lower())
                            parsed['url'] = COMPANY_CAREER_URLS.get(c_norm, f"https://www.{c_norm}.com/careers")

                    # Tier 2: Downstream Stage & Relay ATS Resolver (Ashby, Greenhouse, Lever, HackerRank, Codility)
                    is_relay_sender = any(rd in from_low for rd in ['ashby', 'greenhouse', 'lever', 'smartrecruiters', 'hackerrank', 'codility', 'testgorilla', 'hirevue'])
                    is_downstream_stage = stage in [
                        HiringStage.STAGE_3_RECRUITER_SCREEN,
                        HiringStage.STAGE_4_ASSESSMENT,
                        HiringStage.STAGE_5_TECHNICAL_ROUND,
                        HiringStage.STAGE_6_FINAL_ROUND,
                        HiringStage.STAGE_7_OFFER
                    ] or ('reject' in str(stage).lower() and is_relay_sender)

                    has_date_or_link_cues = any(w in body_text.lower() for w in ['zoom', 'teams', 'meet', 'calendar', 'deadline', 'complete by', 'scheduled for'])
                    if (is_relay_sender or (is_downstream_stage and has_date_or_link_cues)) and self.sarvam.is_configured:
                        stage_event = self.sarvam.resolve_stage_event(subj, body_text, from_h, d_str, active_companies)
                        if stage_event.get('is_lifecycle_event'):
                            if stage_event.get('company'):
                                parsed['company'] = clean_company_name(stage_event['company'])
                            if stage_event.get('role'):
                                parsed['role'] = clean_role_title(stage_event['role'])
                            if stage_event.get('deadline_date'):
                                parsed['deadline'] = stage_event['deadline_date']
                            elif stage_event.get('event_datetime'):
                                parsed['deadline'] = stage_event['event_datetime'][:10]
                            if stage_event.get('meeting_link'):
                                parsed['meeting_link'] = stage_event['meeting_link']

                            # Map stage if recognized
                            st_map = {
                                'assessment': HiringStage.STAGE_4_ASSESSMENT,
                                'recruiter screen': HiringStage.STAGE_3_RECRUITER_SCREEN,
                                'technical round': HiringStage.STAGE_5_TECHNICAL_ROUND,
                                'final round': HiringStage.STAGE_6_FINAL_ROUND,
                                'offer': HiringStage.STAGE_7_OFFER,
                                'rejected': HiringStage.REJECTED_GENERIC,
                                'under review': HiringStage.STAGE_2_UNDER_REVIEW
                            }
                            st_key = (stage_event.get('stage') or '').strip().lower()
                            if st_key in st_map:
                                stage = st_map[st_key]

                    comp_clean = (parsed.get('company') or '').strip()
                    comp_low = comp_clean.lower()
                    if (
                        not comp_clean
                        or len(comp_clean) <= 1
                        or 'harsha' in comp_low
                        or 'injeti' in comp_low
                        or is_excluded_sender(comp_clean)
                        or any(re.search(pat, comp_low, re.I) for pat in EXCLUDE_PATTERNS)
                    ):
                        curr_headers = {}
                        continue

                    parsed['company'] = comp_clean
                    parsed['role'] = (parsed.get('role') or 'Software Engineer / Intern').strip()
                    parsed['date'] = d_str
                    parsed['stage'] = stage
                    parsed['deadline'] = DeadlineParser.extract_deadline(body_text, d_str)

                    # Separate into new submissions vs status transitions
                    if stage == HiringStage.STAGE_1_SUBMITTED:
                        new_applications.append(parsed)
                    else:
                        status_updates.append(parsed)

                    curr_headers = {}

        return new_applications, status_updates

    def close(self):
        try:
            self.mail.close()
            self.mail.logout()
        except Exception:
            pass
