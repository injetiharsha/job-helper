import re
from src.core.cleaner import clean_role_title, clean_company_name

class WorkdayParser:
    @staticmethod
    def is_workday_email(from_hdr, body_text):
        f = from_hdr.lower()
        return 'myworkday' in f or 'myworkdayjobs.com' in body_text

    @staticmethod
    def parse(from_hdr, subject, body_text):
        f = from_hdr.lower()
        s = subject.strip()

        company = None
        role = None

        # Check Novartis special patterns
        if 'novartis' in f or 'intern ddit apd d&a' in s.lower():
            company = "Novartis"
            m_nov = re.search(r'Your Application to\s+(.+)', s, re.I)
            role = clean_role_title(m_nov.group(1)) if m_nov else "DDIT APD D&A Intern"
        elif 'pwc' in f or 'pwc' in s.lower():
            company = "PwC"
            role = clean_role_title(s)
        elif 'lseg' in f or 'lseg' in s.lower():
            company = "LSEG"
            role = clean_role_title(s)
        elif 'blackrock' in f or 'blackrock' in s.lower():
            company = "BlackRock"
            m_br = re.search(r'applying for\s+(.+?)\s+at\s+BlackRock', s, re.I)
            role = clean_role_title(m_br.group(1)) if m_br else "Analyst, Data Management"
        else:
            # General Workday pattern
            patterns = [
                r'application for (?:the position of\s+)?(.+?)\s+at\s+(.+)',
                r'applying for\s+(.+?)\s+at\s+(.+)',
                r'application received:?\s*(.+?)\s+at\s+(.+)',
                r'application:\s+(.+?)\s+at\s+(.+)',
                r'your application for\s+(.+)',
                r'your application to\s+(.+)'
            ]
            for pat in patterns:
                m = re.search(pat, s, re.I)
                if m:
                    if len(m.groups()) == 2:
                        role = clean_role_title(m.group(1))
                        company = clean_company_name(m.group(2))
                    else:
                        role = clean_role_title(m.group(1))
                    break

        # Fallback sender for company
        if not company:
            name_part = from_hdr.split('<')[0].replace('"', '').strip()
            if '@' in name_part or not name_part or 'workday' in name_part.lower():
                m_dom = re.search(r'([a-zA-Z0-9.-]+)@(?:[a-zA-Z0-9.-]*\.)?myworkday\.com', from_hdr, re.I)
                name_part = m_dom.group(1).capitalize() if m_dom else "Workday Company"
            company = clean_company_name(name_part)

        # Extract Candidate Home URL if present in body
        url = None
        ats_urls = re.findall(r'https?://[a-zA-Z0-9.-]*myworkdayjobs\.com/[^\s"\'<>]+', body_text)
        if ats_urls:
            url = ats_urls[0].rstrip('.,;()[]')

        return {
            'company': company,
            'role': role or clean_role_title(s),
            'portal': 'Career Portal',
            'url': url
        }
