import re
import quopri

# Standard preambles to remove from role titles
STRIP_PREFIXES = [
    r'^(?:Thank you for applying for|Thank you for applying to|Thanks for applying to)\s*:?\s*',
    r'^(?:Thanks for your application to|Thanks for applying|An update on your application for)\s*:?\s*',
    r'^(?:An update on your application with|Your application for the position of|Your application for)\s*:?\s*',
    r'^(?:Your application to|Regarding Your Application|Application received for|Application received:?)\s*:?\s*',
    r'^(?:Thank you for your interest in|Your recent job application for|Job Application Acknowledgement -)\s*:?\s*',
    r'^(?:You have successfully applied for|It’s great that you’re interested in|Welcome to the|Welcome to)\s*:?\s*',
    r'^(?:the job:|the position of|the)\s*:?\s*',
    r'^(?:Exciting News: We have received your Application \|\|)\s*'
]

# Tracking IDs and trailing metadata to remove from role titles
STRIP_SUFFIXES = [
    r'\s+at\s+.*$',                          # "... at Company Name"
    r'\s*\(Req ID \d+\).*$',                 # Requisition IDs
    r'\s*\(#\s*\d+\).*$',                    # SuccessFactors job numbers
    r'\s*-\s*[A-Z0-9]{5,}.*$',               # Internal alphanumeric codes (e.g. - 25017217)
    r'\s+received,?\s*Thank you.*$',         # Polite acknowledgments
    r'\s*\(Fill Date:.*$',                   # ATS internal fill dates
    r'\s*\|\s*.*$',                          # Pipe-delimited trailing notes
]

# Generic department, system, and ATS suffixes to strip from company names
GENERIC_COMPANY_SUFFIXES = [
    r'\s+(?:Human Resources|HR|Talent Acquisition|Recruitment|Recruiting|Careers|Career Team|Hiring Team|Team)$',
    r'\s+(?:Workday Notifications|Workday System|Workday)$',
    r'^(?:Workday at|Careers at)\s+',
    r',?\s+(?:Inc\.?|Ltd\.?|LLC|Pvt\.?\s*Ltd\.?|GmbH)$'
]

def clean_role_title(role_str: str) -> str:
    """Removes email preambles, requisition tags, and encoding artifacts from role titles."""
    if not role_str:
        return ""

    # Decode quoted-printable if present
    try:
        if '=E2' in role_str or '=' in role_str:
            role_str = quopri.decodestring(role_str.encode()).decode('utf-8', errors='replace')
    except Exception:
        pass

    clean = role_str.strip()
    clean = re.sub(r'[\"\'!]', '', clean).strip()

    for pat in STRIP_PREFIXES:
        clean = re.sub(pat, '', clean, flags=re.I).strip()

    for pat in STRIP_SUFFIXES:
        clean = re.sub(pat, '', clean, flags=re.I).strip()

    # Normalize punctuation and dashes
    clean = clean.replace('\u2013', '-').replace('\u2014', '-').replace('=E2=80=93', '-').strip()
    clean = re.sub(r'\s+', ' ', clean)
    return clean

def clean_company_name(comp_str: str) -> str:
    """Removes ATS/system noise from company names without relying on brittle hardcoded lists."""
    if not comp_str:
        return ""
    clean = comp_str.strip()
    clean = re.sub(r'[\"\'!]', '', clean).strip()

    for suff in GENERIC_COMPANY_SUFFIXES:
        clean = re.sub(suff, '', clean, flags=re.I).strip()

    clean = re.sub(r'\s+', ' ', clean)
    return clean
