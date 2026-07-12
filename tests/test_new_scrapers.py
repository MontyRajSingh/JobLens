import unittest
import pandas as pd
import numpy as np
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrapers.naukri_scraper import NaukriScraper
from scrapers.instahyre_scraper import InstahyreScraper
from scrapers.wellfound_scraper import WellfoundScraper
from pipeline.data_cleaner import DataCleaner
from pipeline.preprocessing import FeatureBuilder

class TestNewScrapers(unittest.TestCase):
    def test_scraper_sources(self):
        self.assertEqual(NaukriScraper.SOURCE, "Naukri")
        self.assertEqual(InstahyreScraper.SOURCE, "Instahyre")
        self.assertEqual(WellfoundScraper.SOURCE, "Wellfound")

    def test_cleaner_with_new_sources(self):
        test_jobs = [
            {
                "job_title": "Software Engineer",
                "company_name": "Naukri Startup",
                "city": "Bengaluru, India",
                "location": "Bengaluru, India",
                "salary": "$20,000 USD/yr",
                "salary_currency": "INR",
                "seniority_level": "Mid-Level (2-5 years)",
                "experience_required": None,
                "employment_type": "Full-time",
                "remote_type": "On-site",
                "skills_required": "Python",
                "job_description": "A startup job description.",
                "job_link": "http://naukri-link",
                "job_id": "n1",
                "source_website": "Naukri",
                "dedup_key": "key1",
                "is_faang": 0,
                "cost_of_living_index": 28,
                "currency": "INR",
            },
            {
                "job_title": "Machine Learning Engineer",
                "company_name": "Instahyre Co",
                "city": "Pune, India",
                "location": "Pune, India",
                "salary": None,
                "salary_currency": "INR",
                "seniority_level": None,
                "experience_required": None,
                "employment_type": None,
                "remote_type": None,
                "skills_required": None,
                "job_description": "We need machine learning remote talent.",
                "job_link": "http://instahyre-link",
                "job_id": "i1",
                "source_website": "Instahyre",
                "dedup_key": "key2",
                "is_faang": 0,
                "cost_of_living_index": 25,
                "currency": "INR",
            },
            {
                "job_title": "Remote React Developer",
                "company_name": "Wellfound Tech",
                "city": "New York, NY, USA",
                "location": "New York, NY",
                "salary": "$120,000 USD/yr",
                "salary_currency": "USD",
                "seniority_level": None,
                "experience_required": None,
                "employment_type": None,
                "remote_type": "On-site", # should be overridden to Remote
                "skills_required": None,
                "job_description": "React remote job listing.",
                "job_link": "http://wellfound-link",
                "job_id": "w1",
                "source_website": "Wellfound",
                "dedup_key": "key3",
                "is_faang": 0,
                "cost_of_living_index": 100,
                "currency": "USD",
            }
        ]

        df = pd.DataFrame(test_jobs)
        cleaner = DataCleaner()
        df_clean = cleaner.clean(df)

        # Verify all 3 records processed successfully
        self.assertEqual(len(df_clean), 3)
        
        # Verify Instahyre row backfilled skills and remote
        i_row = df_clean[df_clean["job_id"] == "i1"].iloc[0]
        self.assertEqual(i_row["skills_required"], "Python, Machine Learning, Deep Learning")
        self.assertEqual(i_row["remote_type"], "Remote")
        self.assertTrue(i_row["has_remote_benefits"])

        # Verify Wellfound row remote override from title
        w_row = df_clean[df_clean["job_id"] == "w1"].iloc[0]
        self.assertEqual(w_row["remote_type"], "Remote")
        self.assertTrue(w_row["has_remote_benefits"])

    def test_feature_builder_compatibility(self):
        # Verify that preprocessing one-hot encoder doesn't crash on new source values
        # and retains the source_glassdoor column with value 0.
        test_jobs = [
            {
                "job_title": "Software Engineer",
                "company_name": "Naukri Startup",
                "city": "Bengaluru, India",
                "location": "Bengaluru, India",
                "salary_usd_numeric": 20000.0,
                "seniority_level": "Mid-Level (2-5 years)",
                "experience_required": "2-5 years",
                "employment_type": "Full-time",
                "remote_type": "On-site",
                "skills_required": "Python",
                "source_website": "Naukri",
                "is_faang": 0,
                "cost_of_living_index": 28,
            },
            {
                "job_title": "Developer",
                "company_name": "Acme",
                "city": "New York, NY, USA",
                "location": "New York, NY",
                "salary_usd_numeric": 100000.0,
                "seniority_level": "Mid-Level (2-5 years)",
                "experience_required": "2-5 years",
                "employment_type": "Full-time",
                "remote_type": "Remote",
                "skills_required": "React",
                "source_website": "Wellfound",
                "is_faang": 0,
                "cost_of_living_index": 100,
            }
        ]
        df = pd.DataFrame(test_jobs)
        
        # Build features
        builder = FeatureBuilder()
        features = builder._build_source_features(df)
        
        # Must contain all three source columns
        self.assertIn("source_linkedin", features.columns)
        self.assertIn("source_indeed", features.columns)
        self.assertIn("source_glassdoor", features.columns)
        
        # All rows should have 0 for all source columns since they are Naukri and Wellfound
        self.assertEqual(features["source_linkedin"].sum(), 0)
        self.assertEqual(features["source_indeed"].sum(), 0)
        self.assertEqual(features["source_glassdoor"].sum(), 0)

if __name__ == "__main__":
    unittest.main()
