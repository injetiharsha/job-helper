import re
from datetime import datetime, timedelta

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

class DeadlineParser:
    """
    Extracts explicit deadlines, assessment expiration dates,
    and scheduled interview dates from recruitment email texts.
    """
    @staticmethod
    def extract_deadline(body_text, email_date_str):
        if not body_text or not email_date_str:
            return None

        try:
            base_date = datetime.strptime(email_date_str[:10], '%Y-%m-%d').date()
        except Exception:
            base_date = datetime.today().date()

        text = body_text.lower()

        # 1. "scheduled for today" / "scheduled for tomorrow"
        if re.search(r'scheduled for\s+(?:\*+)?today', text):
            return base_date.strftime('%Y-%m-%d')
        if re.search(r'scheduled for\s+(?:\*+)?tomorrow', text):
            return (base_date + timedelta(days=1)).strftime('%Y-%m-%d')

        # 2. Relative day intervals: "within 5 days", "expire after 7 days", "valid for 3 days"
        rel_match = re.search(r'(?:within|after|for|in)\s+(\d+)\s*(?:business |working )?days', text)
        if rel_match:
            days = int(rel_match.group(1))
            return (base_date + timedelta(days=days)).strftime('%Y-%m-%d')

        if re.search(r'within\s+(?:the\s+next\s+)?week', text):
            return (base_date + timedelta(days=7)).strftime('%Y-%m-%d')

        if re.search(r'within\s+48\s*hours', text):
            return (base_date + timedelta(days=2)).strftime('%Y-%m-%d')
        if re.search(r'within\s+72\s*hours', text):
            return (base_date + timedelta(days=3)).strftime('%Y-%m-%d')
        if re.search(r'within\s+24\s*hours', text):
            return (base_date + timedelta(days=1)).strftime('%Y-%m-%d')

        # 3. Explicit Calendar Dates (e.g. "by 12th October", "scheduled for 15 Oct 2026")
        # Pattern A: DD Month [YYYY]
        d_match = re.search(
            r'(?:scheduled for|by|before|on|due|deadline:?)\s+(?:today,\s*)?(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})(?:\s*,?\s*(\d{4}))?',
            text
        )
        if d_match:
            day = int(d_match.group(1))
            month_str = d_match.group(2)[:3]
            year = int(d_match.group(3)) if d_match.group(3) else base_date.year
            if month_str in MONTHS:
                month = MONTHS[month_str]
                try:
                    return datetime(year, month, day).strftime('%Y-%m-%d')
                except ValueError:
                    pass

        # Pattern B: Month DD [YYYY]
        m_match = re.search(
            r'(?:scheduled for|by|before|on|due|deadline:?)\s+(?:today,\s*)?([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?',
            text
        )
        if m_match:
            month_str = m_match.group(1)[:3]
            day = int(m_match.group(2))
            year = int(m_match.group(3)) if m_match.group(3) else base_date.year
            if month_str in MONTHS:
                month = MONTHS[month_str]
                try:
                    return datetime(year, month, day).strftime('%Y-%m-%d')
                except ValueError:
                    pass

        return None
