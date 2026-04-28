import unittest

from api.schemas.request import OfferAnalyzeRequest
from api.schemas.response import OfferAnalyzeResponse, PredictResponse
from api.routes.predict import (
    _coerce_experience_years,
    _infer_job_title_from_resume,
    _seniority_from_experience,
)


class ApiContractTests(unittest.TestCase):
    def test_prediction_response_exposes_raw_and_adjusted_values(self):
        response = PredictResponse(
            predicted_salary_usd=130000,
            model_prediction_usd=120000,
            adjusted_prediction_usd=130000,
            base_prediction_usd=110000,
            confidence_low=110500,
            confidence_high=149500,
            confidence_method="heuristic_percentage_band_after_adjustments",
            percentile=75,
            adjustments={
                "skill_market_premium": 12000,
                "company_tier_bonus": 0,
                "academic_bonus": 0,
                "is_heuristic_adjusted": True,
            },
            model_name="XGBoost",
        )

        payload = response.model_dump()

        self.assertEqual(payload["model_prediction_usd"], 120000)
        self.assertEqual(payload["adjusted_prediction_usd"], 130000)
        self.assertTrue(payload["adjustments"]["is_heuristic_adjusted"])

    def test_resume_experience_defaults_and_seniority_mapping(self):
        self.assertEqual(_coerce_experience_years(None), 0)
        self.assertEqual(_coerce_experience_years("not mentioned"), 0)
        self.assertEqual(_coerce_experience_years("3-5 years"), 4)
        self.assertEqual(_seniority_from_experience(0), "Entry Level (0-2 years)")
        self.assertEqual(_seniority_from_experience(2), "Associate (1-3 years)")
        self.assertEqual(_seniority_from_experience(4), "Mid-Level (2-5 years)")
        self.assertEqual(_seniority_from_experience(6), "Senior (5+ years)")

    def test_resume_job_title_fallback(self):
        self.assertEqual(
            _infer_job_title_from_resume("Built React and Node.js applications", []),
            "Full Stack Developer",
        )
        self.assertEqual(
            _infer_job_title_from_resume("", ["PyTorch", "NLP"]),
            "Machine Learning Engineer",
        )
        self.assertEqual(_infer_job_title_from_resume("", []), "Software Engineer")

    def test_offer_analyzer_contract(self):
        request = OfferAnalyzeRequest(
            job_title="Data Scientist",
            city="New York, NY, USA",
            seniority_level="Mid-Level (2-5 years)",
            base_salary_usd=120000,
            annual_bonus_usd=10000,
            annual_equity_usd=15000,
        )
        response = OfferAnalyzeResponse(
            total_comp_usd=145000,
            market_reference_usd=135000,
            difference_usd=10000,
            difference_pct=7.4,
            verdict="fair",
            recommendation="Close to market.",
            evidence_count=12,
            predicted_salary_usd=132000,
        )

        self.assertEqual(request.base_salary_usd, 120000)
        self.assertEqual(response.total_comp_usd, 145000)
        self.assertEqual(response.verdict, "fair")


if __name__ == "__main__":
    unittest.main()
