import re
from src.core.stages import HiringStage, STAGE_KEYWORDS, REJECTION_FORMULAS

class LifecycleClassifier:
    @staticmethod
    def classify_email(subject, body_text):
        """
        Classifies incoming recruitment email into one of the 7 stages
        or a rejection sub-type.
        """
        s_low = subject.lower()
        b_low = body_text.lower()
        combined = f"{s_low} {b_low}"
        combined = re.sub(r'\s+', ' ', combined)

        # 1. Check for Rejections first
        for rej_stage, patterns in REJECTION_FORMULAS.items():
            for pat in patterns:
                if re.search(pat, combined):
                    return rej_stage

        # 2. Check for Stage 7: Offer
        for pat in STAGE_KEYWORDS[HiringStage.STAGE_7_OFFER]:
            if re.search(pat, combined):
                return HiringStage.STAGE_7_OFFER

        # 3. Check for Stage 6: Final Round
        for pat in STAGE_KEYWORDS[HiringStage.STAGE_6_FINAL_ROUND]:
            if re.search(pat, combined):
                return HiringStage.STAGE_6_FINAL_ROUND

        # 4. Check for Stage 5: Technical Round
        for pat in STAGE_KEYWORDS[HiringStage.STAGE_5_TECHNICAL_ROUND]:
            if re.search(pat, combined):
                return HiringStage.STAGE_5_TECHNICAL_ROUND

        # 5. Check for Stage 4: Assessment (User's #3)
        for pat in STAGE_KEYWORDS[HiringStage.STAGE_4_ASSESSMENT]:
            if re.search(pat, combined):
                return HiringStage.STAGE_4_ASSESSMENT

        # 6. Check for Stage 3: Recruiter Screen (User's #4)
        for pat in STAGE_KEYWORDS[HiringStage.STAGE_3_RECRUITER_SCREEN]:
            if re.search(pat, combined):
                return HiringStage.STAGE_3_RECRUITER_SCREEN

        # 7. Check for Stage 2: Under Review
        for pat in STAGE_KEYWORDS[HiringStage.STAGE_2_UNDER_REVIEW]:
            if re.search(pat, combined):
                return HiringStage.STAGE_2_UNDER_REVIEW

        # 8. Check for Stage 1: Submitted
        for pat in STAGE_KEYWORDS[HiringStage.STAGE_1_SUBMITTED]:
            if re.search(pat, combined):
                return HiringStage.STAGE_1_SUBMITTED

        return HiringStage.STAGE_1_SUBMITTED
