import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import quopri
from src.core.config import GMAIL_EMAIL, GMAIL_APP_PASSWORD, LINKEDIN_DEFAULT_URL, COMPANY_CAREER_URLS
from src.core.cleaner import clean_role_title, clean_company_name
from src.parsers.linkedin_parser import LinkedInParser
from src.parsers.workday_parser import WorkdayParser
from src.parsers.lifecycle_classifier import LifecycleClassifier
from src.parsers.deadline_parser import DeadlineParser
from src.core.stages import HiringStage

# Senders and domains that must NEVER be ingested as employers
EXCLUDE_DOMAINS = [
    'passportindia.gov.in', 'proteantech.in', 'protean', 'incometax.gov.in',
    'uidai.gov.in', 'glassdoor.com', 'glassdoor', 'galvanize', 'cdac.in',
    'mail.amazon.jobs', 'amazon.jobs', 'accounts.google.com', 'ads-noreply@google.com',
    'udayaharsha13@gmail.com'
]

# Patterns in Subject or From that indicate non-job emails, newsletters, identity documents, or security
EXCLUDE_PATTERNS = [
    # Government, Identity, Tax, Police Verification
    r'pan\s+application', r'intimation\s+of\s+pan', r'police\s+verification',
    r'passport\s+application', r'passportindia', r'income\s+tax', r'aadhaar',
    r'protean', r'form\s+16',
    
    # Academic, College, Study Abroad
    r'study\s+abroad', r'bs\s+degree', r'degree\s+application', r'iit\s+madras',
    r'galvanize\s+global', r'admissions?', r'scholarship',

    # Aggregators, Alerts, Newsletters, Marketing
    r'glassdoor', r'job\s+alert', r'saved\s+job', r'recommended\s+jobs',
    r'top\s+jobs\s+for\s+you', r'new\s+jobs\s+posted', r'interview\s+experiences',
    r'newsletter', r'digital\s+talent', r'weekly\s+alert', r'talent\s+community',
    r'join\s+our\s+talent', r'is\s+hiring', r'potential\s+match', r'jobs\s+at\s+',
    r'job\s+suggestions', r'job\s+search', r'experience\s+at\s+ntt',
    
    # Account & Security verification
    r'security\s+code', r'one-time-passcode', r'verification\s+code', r'verify\s+your',
    r'password\s+reset', r'confirm\s+your\s+email', r'2fa', r'sign[- ]in\s+code',
    r'survey\s+request', r'talent\s+acquisition\s+survey', r'your\s+account\s+has\s+been\s+created',
    r'have\s+you\s+completed\s+your\s+candidate\s+home',
    
    # Application Withdrawn
    r'withdrawn\s+your\s+.*application', r'withdrew\s+your\s+application'
]

class GmailClient:
    def __init__(self):
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            raise ValueError("Gmail credentials missing in .env")
        self.mail = imaplib.IMAP4_SSL("imap.gmail.com")
        self.mail.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        self.mail.select('"[Gmail]/All Mail"')

    def _decode_header(self, raw_hdr):
        if not raw_hdr: return ""
        res = []
        for frag, enc in decode_header(raw_hdr):
            if isinstance(frag, bytes):
                res.append(frag.decode(enc or 'utf-8', errors='replace'))
            else:
                res.append(str(frag))
        return "".join(res)

    def fetch_recruitment_events(self, since_date_str):
        """
        Scans for application submissions and lifecycle progression updates.
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
                    clean_b = re.sub(r'<[^>]+>', ' ', raw_b)
                    clean_b = re.sub(r'[ \t]+', ' ', clean_b)
                    body_text = re.sub(r'\n\s*\n+', '\n', clean_b).strip()

                    subj = curr_headers.get('subject', '').strip()
                    from_h = curr_headers.get('from', '').strip()
                    date_raw = curr_headers.get('date', '')

                    # 1. Skip if sender is blacklisted or user's own email
                    from_low = from_h.lower()
                    if any(d in from_low for d in EXCLUDE_DOMAINS):
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

                    # 2. Extract Company & Role
                    if LinkedInParser.is_linkedin_email(from_h):
                        parsed = LinkedInParser.parse(from_h, subj, body_text)
                    elif WorkdayParser.is_workday_email(from_h, body_text):
                        parsed = WorkdayParser.parse(from_h, subj, body_text)
                    else:
                        # General Enterprise Portal
                        comp = clean_company_name(from_h.split('<')[0])
                        # If sender is generic (e.g. test vendor or recruiter), inspect subject
                        for known in ["Google", "LSEG", "Banao Technologies", "TensorGo", "P&G", "Infosys", "United Airlines", "HSBC", "Swiss Re", "McKinsey", "Barclays", "Micron Technology", "ZoomRx", "Qualcomm", "ION Group", "Flex", "Colgate-Palmolive", "Accenture", "Aura Cloud", "Microsoft", "Novartis", "Electronic Arts (EA)"]:
                            if re.search(r'\b' + re.escape(known) + r'\b', subj, re.I):
                                comp = known
                                break

                        role = clean_role_title(subj)
                        c_norm = re.sub(r'[^a-zA-Z0-9]', '', comp.lower())
                        parsed = {
                            'company': comp,
                            'role': role or "Software Engineer / Intern",
                            'portal': 'Career Portal',
                            'url': COMPANY_CAREER_URLS.get(c_norm, f"https://www.{c_norm}.com/careers")
                        }

                    comp_clean = (parsed.get('company') or '').strip()
                    comp_low = comp_clean.lower()
                    if (
                        not comp_clean
                        or len(comp_clean) <= 1
                        or 'harsha' in comp_low
                        or 'injeti' in comp_low
                        or any(d in comp_low for d in EXCLUDE_DOMAINS)
                        or any(re.search(pat, comp_low, re.I) for pat in EXCLUDE_PATTERNS)
                    ):
                        curr_headers = {}
                        continue

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
