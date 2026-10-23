import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env securely
load_dotenv(BASE_DIR / ".env")

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

# State & Thresholds
STATE_FILE = BASE_DIR / "sync_state.json"
NO_RESPONSE_DAYS = 30
LINKEDIN_DEFAULT_URL = "https://www.linkedin.com/jobs-tracker/?stage=applied"

# Verified Default Career Portal & Candidate Home URLs
COMPANY_CAREER_URLS = {
    'phonepe': 'https://www.phonepe.com/careers/',
    'sproutsai': 'https://sproutsai.dev/careers',
    'automationanywhere': 'https://www.automationanywhere.com/company/careers',
    'texasinstruments': 'https://careers.ti.com/en/sites/CX/my-profile',
    'macquariegroup': 'https://recruitment.macquarie.com/en_US/careers/ProfileJobApplications',
    'spglobal': 'https://spgi.wd5.myworkdayjobs.com/en-US/SPGI_Careers/userHome',
    'sandpglobal': 'https://spgi.wd5.myworkdayjobs.com/en-US/SPGI_Careers/userHome',
    'consiliumsafety': 'https://www.consiliumsafety.com/careers/',
    'rtx': 'https://globalhr.wd5.myworkdayjobs.com/en-GB/REC_RTX_Ext_Gateway/userHome',
    'microsoft': 'https://careers.microsoft.com/',
    'accenture': 'https://accenture.wd103.myworkdayjobs.com/en-US/AccentureCareers/userHome',
    'pg': 'https://www.pgcareers.com/',
    'lseg': 'https://lseg.wd3.myworkdayjobs.com/en-US/Careers/userHome',
    'standardchartered': 'https://www.sc.com/en/careers/',
    'citi': 'https://citi.wd5.myworkdayjobs.com/en-US/2/userHome',
    'ubisoft': 'https://www.ubisoft.com/en-us/company/careers',
    'amazon': 'https://www.amazon.jobs/',
    'sarvam': 'https://jobs.ashbyhq.com/sarvam',
    'hilti': 'https://careers.hilti.group/',
    'ikea': 'https://www.ikea.com/in/en/this-is-ikea/work-with-us/',
    'schneiderelectric': 'https://www.se.com/in/en/about-us/careers/',
    'smartstream': 'https://www.smartstream-stp.com/careers/',
    'smartstreamlimited': 'https://www.smartstream-stp.com/careers/',
    'cognizant': 'https://careers.cognizant.com/',
    'coverself': 'https://www.coverself.com/careers',
    'clickpost': 'https://www.clickpost.ai/careers',
    'fortrea': 'https://careers.fortrea.com/',
    'greif': 'https://www.greif.com/careers/',
    'mastercard': 'https://mastercard.wd1.myworkdayjobs.com/en-US/CorporateCareers/userHome?q=india',
    'thermofisherscientific': 'https://jobs.thermofisher.com/',
    'thermofisher': 'https://jobs.thermofisher.com/',
    'google': 'https://www.google.com/about/careers/applications/u/1/dashboard?hl=en_US',
    'barclays': 'https://barclays.wd3.myworkdayjobs.com/en-US/External_Career_Site_Barclays/userHome',
    'flex': 'https://flextronics.wd1.myworkdayjobs.com/Careers',
    'drmartens': 'https://www.drmartens.com/careers',
    'hackerrank': 'https://www.hackerrank.com/careers',
    'iongroup': 'https://iongroup.com/careers/',
    'yal': 'https://www.yal.ai/',
    'sarlaaviation': 'https://sarlaaviation.com/careers',
    'philips': 'https://www.careers.philips.com/',
    'bureau': 'https://www.bureau.id/careers',
    'nttdata': 'https://careers.services.global.ntt/global/en/myprofile',
    'colgatepalmolive': 'https://jobs.colgate.com/',
    'arrowelectronics': 'https://careers.arrow.com/',
    'auracloud': 'https://www.auracloud.com/careers',
    'tensorgo': 'https://tensorgo.com/careers',
    'blitzenxsolutions': 'https://blitzenx.com/',
    'elililly': 'https://careers.lilly.com/',
    'eaton': 'https://www.eaton.com/careers',
    'minimed': 'https://www.medtronic.com/careers',
    'atkinsrealis': 'https://slihrms.wd3.myworkdayjobs.com/en-US/Careers/userHome',
    'novartis': 'https://www.novartis.com/careers',
    'gokwik': 'https://www.gokwik.co/careers',
    'nestorhire': 'https://www.nestorhire.com/',
    'volvogroup': 'https://www.volvogroup.com/en/careers.html',
    'electronicarts': 'https://www.ea.com/careers',
    'electronicartsea': 'https://www.ea.com/careers',
    'ea': 'https://www.ea.com/careers',
    'blackrock': 'https://careers.blackrock.com/',
    'pwc': 'https://pwc.wd3.myworkdayjobs.com/en-US/CRM_Experienced_Careers_Site/userHome',
    'haier': 'https://www.haier.com/in/about-haier/careers.shtml',
    'hitachi': 'https://careers.hitachi.com/'
}
