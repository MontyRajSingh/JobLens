import unittest

import pandas as pd

from pipeline.data_cleaner import DataCleaner
from utils.salary_utils import parse_salary_numeric_usd


class SalaryPipelineTests(unittest.TestCase):
    def test_shared_salary_parser_handles_common_formats(self):
        self.assertEqual(parse_salary_numeric_usd("$100k - $120k"), 110000)
        self.assertEqual(parse_salary_numeric_usd("$50/hr"), 104000)
        self.assertEqual(parse_salary_numeric_usd("12 LPA", usd_rate=0.012), 14400)

    def test_cleaner_preserves_existing_numeric_salary(self):
        df = pd.DataFrame([{
            "job_title": "Data Scientist",
            "company_name": "Acme Inc.",
            "city": "New York, NY, USA",
            "salary": "$10/hr",
            "salary_usd_numeric": 123456,
            "dedup_key": "abc",
            "seniority_level": "Mid-Level (2-5 years)",
            "employment_type": "Full-time",
            "remote_type": "On-site",
            "industry": None,
            "education_required": None,
            "has_equity": 0,
            "has_bonus": 0,
            "job_description": "",
            "source_website": "Indeed",
        }])

        cleaned = DataCleaner().clean(df)

        self.assertEqual(cleaned.loc[0, "salary_usd_numeric"], 123456)
        self.assertEqual(cleaned.loc[0, "company_name"], "Acme")

    def test_cleaner_uses_shared_parser_when_numeric_missing(self):
        df = pd.DataFrame([{
            "job_title": "Software Engineer",
            "company_name": "Acme",
            "city": "New York, NY, USA",
            "salary": "$80k - $120k",
            "salary_usd_numeric": None,
            "dedup_key": "def",
            "seniority_level": "Mid-Level (2-5 years)",
            "employment_type": "Full-time",
            "remote_type": "Remote",
            "industry": None,
            "education_required": None,
            "has_equity": 0,
            "has_bonus": 0,
            "job_description": "",
            "source_website": "Indeed",
        }])

        cleaned = DataCleaner().clean(df)

        self.assertEqual(cleaned.loc[0, "salary_usd_numeric"], 100000)


if __name__ == "__main__":
    unittest.main()
