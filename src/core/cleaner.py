import re
import quopri

# Courtesy and marketing preambles to remove from role titles
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

# Tracking IDs and polite suffixes to remove
STRIP_SUFFIXES = [
    r'\s+at\s+.*$',                          # "... at Company Name"
    r'\s*\(Req ID \d+\).*$',                 # Requisition IDs
    r'\s*\(#\s*\d+\).*$',                    # SuccessFactors job numbers
    r'\s*-\s*[A-Z0-9]{5,}.*$',               # Internal alphanumeric codes (e.g. - 25017217)
    r'\s+received,?\s*Thank you.*$',         # Polite acknowledgments
    r'\s*\(Fill Date:.*$',                   # ATS internal fill dates
    r'\s*\|\s*.*$',                          # Pipe-delimited trailing notes
]

# Company name noise suffixes to strip
COMPANY_SUFFIXES = [
    r'\s+Commerce Solutions.*$', r'\s+Human Resources.*$',
    r'^Katarina Wanderydz -\s*', r'\s+Hiring.*$',
    r'\s+Careers$', r'\s+Talent Acquisition$', r'\s+Recruitment$',
    r'\s+Team$', r'\s+Workday Notifications$', r'\s+Workday System$',
    r'\s+Workday$', r'^Workday at\s+'
]

def clean_role_title(role_str):
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

    # Apply prefix stripping
    for pat in STRIP_PREFIXES:
        clean = re.sub(pat, '', clean, flags=re.I).strip()

    # Apply suffix stripping
    for pat in STRIP_SUFFIXES:
        clean = re.sub(pat, '', clean, flags=re.I).strip()

    # Normalize punctuation and dashes
    clean = clean.replace('\u2013', '-').replace('\u2014', '-').replace('=E2=80=93', '-').strip()
    clean = re.sub(r'\s+', ' ', clean)
    return clean

def clean_company_name(comp_str):
    if not comp_str:
        return ""
    clean = comp_str.strip()
    clean = re.sub(r'[\"\'!]', '', clean).strip()

    for suff in COMPANY_SUFFIXES:
        clean = re.sub(suff, '', clean, flags=re.I).strip()

    # Brand aliases
    c_low = clean.lower()
    if 'gokwik' in c_low: return "GoKwik"
    if 'consilium' in c_low: return "Consilium Safety"
    if 'convin' in c_low: return "Convin.AI"
    if 'nestor' in c_low: return "Nestor Hire"
    if 'volvo' in c_low: return "Volvo Group"
    if 'electronic arts' in c_low or c_low == 'ea': return "Electronic Arts (EA)"
    if 'amex' in c_low or 'american express' in c_low: return "Amex"
    if 'novartis' in c_low: return "Novartis"
    if 'pwc' in c_low: return "PwC"
    if 'phonepe' in c_low: return "PhonePe"
    if 'atkins' in c_low: return "AtkinsRealis"
    if 'spgi' in c_low or 's&p global' in c_low: return "S&P Global"
    if 'macquarie' in c_low: return "Macquarie Group"
    if 'microsoft' in c_low: return "Microsoft"
    if 'thermo fisher' in c_low: return "Thermo Fisher Scientific"
    if 'hitachi' in c_low: return "Hitachi"

    return clean
