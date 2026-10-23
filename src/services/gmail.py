import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
from src.core.config import GMAIL_EMAIL, GMAIL_APP_PASSWORD, LINKEDIN_DEFAULT_URL, COMPANY_CAREER_URLS
from src.core.cleaner import clean_role_title, clean_company_name
from src.parsers.linkedin_parser import LinkedInParser
from src.parsers.workday_parser import WorkdayParser
from src.parsers.lifecycle_classifier import LifecycleClassifier
from src.parsers.deadline_parser import DeadlineParser
from src.core.stages import HiringStage

EXCLUDE_PATTERNS = [
    r'security code', r'one-time-passcode', r'verification code', r'verify your',
    r'password reset', r'new job opportunities', r'jobs at ', r'job alert',
    r'recommended jobs', r'pending tasks', r'complete your application',
    r'survey request', r'talent acquisition survey', r'confirm your email', r'2fa',
    r'top jobs', r'job search', r'job suggestions', r'is hiring', r'potential match',
    r'jobs applied by your', r'your account has been created', r'sign in code',
    r'digital talent newsletter', r'newsletter', r'experience at ntt',
    r'have you completed your candidate home', r'new jobs posted from',
    r'invitation to join', r'status they never', r'talent community',
    r'nvidia x ytu', r'join our talent community', r'weekly alert', r'sign-in code'
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
                    body_text = item[1].decode('utf-8', errors='replace')
                    if not curr_headers:
                        continue

                    subj = curr_headers.get('subject', '').strip()
                    from_h = curr_headers.get('from', '').strip()
                    date_raw = curr_headers.get('date', '')

                    # Skip newsletters and security codes
                    if any(re.search(pat, subj, re.I) for pat in EXCLUDE_PATTERNS):
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

                    if not parsed['company']:
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
