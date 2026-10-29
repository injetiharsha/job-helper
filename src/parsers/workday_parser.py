import re
from src.core.cleaner import clean_role_title, clean_company_name

class WorkdayParser:
    @staticmethod
    def is_workday_email(from_hdr: str, body_text: str) -> bool:
        f = from_hdr.lower()
        return 'myworkday' in f or 'myworkdayjobs.com' in body_text

    @staticmethod
    def parse(from_hdr: str, subject: str, body_text: str):
        s = subject.strip()
        company = None
        role = None

        # Generic structural Workday subject patterns
        patterns = [
            r'application for (?:the position of\s+)?(.+?)\s+at\s+(.+)',
            r'applying for\s+(.+?)\s+at\s+(.+)',
            r'application received:?\s*(.+?)\s+at\s+(.+)',
            r'application:\s+(.+?)\s+at\s+(.+)',
            r'your application to\s+(.+?)(?:\s+for\s+(.+))?$',
            r'your application for\s+(.+?)(?:\s+at\s+(.+))?$'
        ]
        
        for pat in patterns:
            m = re.search(pat, s, re.I)
            if m:
                groups = [g.strip() for g in m.groups() if g]
                if len(groups) == 2:
                    # Pattern 1-4: group(1)=role, group(2)=company (or vice versa for "to <comp> for <role>")
                    if 'to ' in pat:
                        company = clean_company_name(groups[0])
                        role = clean_role_title(groups[1])
                    else:
                        role = clean_role_title(groups[0])
                        company = clean_company_name(groups[1])
                elif len(groups) == 1:
                    role = clean_role_title(groups[0])
                break

        # Fallback sender parsing for company name
        if not company:
            name_part = from_hdr.split('<')[0].replace('"', '').strip()
            if '@' in name_part or not name_part or 'workday' in name_part.lower():
                m_dom = re.search(r'([a-zA-Z0-9.-]+)@(?:[a-zA-Z0-9.-]*\.)?myworkday\.com', from_hdr, re.I)
                name_part = m_dom.group(1).capitalize() if m_dom else None
            if name_part:
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
