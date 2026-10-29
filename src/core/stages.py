from enum import Enum

class HiringStage(Enum):
    """
    Universal 7-Stage Hiring Progression Pipeline:
    1 -> 2 -> 4 -> 3 -> 5 -> 6 -> 7
    """
    # 1. Application Submitted (Sent via LinkedIn or initial Career Portal submit)
    STAGE_1_SUBMITTED = "Submitted"

    # 2. Under Review (ATS pass, candidate home account generated, under review)
    STAGE_2_UNDER_REVIEW = "Under Review"

    # 3 (User's #4). Recruiter / HR Screening (Initial recruiter outreach, phone screen, HR verification)
    STAGE_3_RECRUITER_SCREEN = "Recruiter Screen"

    # 4 (User's #3). Assessment / Online Test (HackerRank, Cappfinity, coding challenge, cognitive test)
    STAGE_4_ASSESSMENT = "Assessment"

    # 5. Technical Round(s) (1st/2nd round technical interview, live coding, case study, AI interview)
    STAGE_5_TECHNICAL_ROUND = "Technical Round"

    # 6. Final / Leadership Round (Director / Hiring Manager interview, final HR alignment)
    STAGE_6_FINAL_ROUND = "Final Round"

    # 7. Offer / Hired (Formal offer letter, compensation review)
    STAGE_7_OFFER = "Offer"

    # Terminal Statuses
    REJECTED_ATS = "Rejected (ATS Screen)"
    REJECTED_REVIEW = "Rejected (Review Pool)"
    REJECTED_GENERIC = "Rejected"
    NO_RESPONSE = "No Response"

STAGE_ORDER = [
    HiringStage.STAGE_1_SUBMITTED,
    HiringStage.STAGE_2_UNDER_REVIEW,
    HiringStage.STAGE_4_ASSESSMENT,
    HiringStage.STAGE_3_RECRUITER_SCREEN,
    HiringStage.STAGE_5_TECHNICAL_ROUND,
    HiringStage.STAGE_6_FINAL_ROUND,
    HiringStage.STAGE_7_OFFER,
]

# Detection Keywords for each stage
STAGE_KEYWORDS = {
    HiringStage.STAGE_7_OFFER: [
        r'offer letter', r'pleased to offer', r'congratulations on your offer',
        r'offer of employment', r'formal job offer'
    ],
    HiringStage.STAGE_6_FINAL_ROUND: [
        r'final round', r'final interview', r'leadership round',
        r'director interview', r'hiring manager round'
    ],
    HiringStage.STAGE_5_TECHNICAL_ROUND: [
        r'technical round', r'technical interview', r'live coding',
        r'system design interview', r'case study interview',
        r'round 1 interview', r'round 2 interview'
    ],
    HiringStage.STAGE_4_ASSESSMENT: [
        r'assessment', r'coding challenge', r'hackerrank', r'codility',
        r'cappassessments', r'immersive online assessment', r'online test',
        r'test invitation', r'hirevue'
    ],
    HiringStage.STAGE_3_RECRUITER_SCREEN: [
        r'initial interview process', r'screening call', r'recruiter call',
        r'phone screen', r'introductory call', r'brief chat',
        r'speak with our recruiter', r'connect with our recruiting team'
    ],
    HiringStage.STAGE_2_UNDER_REVIEW: [
        r'we have received your application', r'application received',
        r'under review', r'in review', r'application acknowledgement',
        r'reviewing your profile'
    ],
    HiringStage.STAGE_1_SUBMITTED: [
        r'your application was sent to', r'thank you for applying',
        r'thanks for applying', r'confirming your.*job application',
        r'application submitted'
    ]
}

# Rejection Linguistic Formulas
REJECTION_FORMULAS = {
    # Formula A: Fast Disqualification / Automated Knockout
    HiringStage.REJECTED_ATS: [
        r'not\s+to\s+move\s+forward\s+with\s+your\s+application',
        r'will\s+not\s+be\s+moving\s+forward\s+with\s+your\s+application',
        r'not\s+moving\s+forward\s+with\s+your\s+candidacy',
        r'unable\s+to\s+consider\s+it\s+further\s+at\s+this\s+time',
        r'(?:decided|chosen)\s+not\s+to\s+proceed\s+with\s+your\s+application',
        r'not\s+to\s+proceed\s+with\s+your\s+application',
        r'not\s+to\s+proceed\s+with\s+your\s+candidacy',
        r'not\s+be\s+progressing\s+with\s+your\s+candidacy',
        r'will\s+not\s+be\s+progressing\s+with\s+your',
        r'unable\s+to\s+offer\s+you\s+an\s+interview',
    ],
    # Formula B: Competitive Review Pool
    HiringStage.REJECTED_REVIEW: [
        r'other\s+candidates\s+whose\s+qualifications\s+more\s+closely\s+match',
        r'moving\s+forward\s+with\s+other\s+candidates',
        r'decided\s+to\s+pursue\s+other\s+candidates',
        r'decided\s+to\s+move\s+forward\s+with\s+another\s+candidate',
        r'large\s+number\s+of\s+applications.*(?:other\s+candidates|another\s+candidate)'
    ],
    # General fallback
    HiringStage.REJECTED_GENERIC: [
        r'regret\s+to\s+inform\s+you',
        r'regret\s+that\s+we\s+cannot',
        r'unfortunately.*(?:not\s+selected|cannot\s+offer|will\s+not\s+be|unable\s+to)',
        r'not\s+selected\s+for\s+(?:this\s+)?(?:position|role|interview)',
        r'unsuccessful\s+in\s+this\s+process',
        r'cannot\s+offer\s+you\s+(?:an\s+)?interview'
    ]
}
