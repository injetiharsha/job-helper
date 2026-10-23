import re
from src.core.cleaner import clean_role_title, clean_company_name
from src.core.config import LINKEDIN_DEFAULT_URL

class LinkedInParser:
    @staticmethod
    def is_linkedin_email(from_hdr):
        return 'linkedin' in from_hdr.lower()

    @staticmethod
    def parse(from_hdr, subject, body_text):
        """
        In LinkedIn Easy Apply emails, the role is on line 1 of the body
        directly underneath 'Your application was sent to <Company>'.
        """
        company = None
        role = None

        subj_clean = subject.strip()
        m_comp = re.search(r'your application was sent to\s+(.+)', subj_clean, re.I)
        if m_comp:
            company = clean_company_name(m_comp.group(1))
        else:
            m_sub = re.search(r'application to\s+(.+?)\s+(?:at|was sent to)\s+(.+)', subj_clean, re.I)
            if m_sub:
                role = clean_role_title(m_sub.group(1))
                company = clean_company_name(m_sub.group(2))

        # Extract role from line 1 of body if not in subject
        if not role and body_text:
            lines = [l.strip() for l in body_text.splitlines() if l.strip()]
            for idx, line in enumerate(lines):
                if 'your application was sent to' in line.lower():
                    if idx + 1 < len(lines):
                        cand = lines[idx + 1]
                        if not cand.startswith('http') and len(cand) < 80:
                            role = clean_role_title(cand)
                            break

        if not role:
            role = "Software Engineer / Intern"

        return {
            'company': company,
            'role': role,
            'portal': 'Linkedin',
            'url': LINKEDIN_DEFAULT_URL
        }
