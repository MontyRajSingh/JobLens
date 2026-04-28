import unittest

import pandas as pd

from pipeline.data_quality import DataReadinessThresholds, evaluate_training_readiness


class TrainingReadinessTests(unittest.TestCase):
    def test_readiness_fails_for_small_scraped_dataset(self):
        df = pd.DataFrame({
            "salary_usd_numeric": [100000, None, 120000],
            "city": ["New York", "New York", "London"],
            "seniority_level": ["Senior", "Senior", "Mid"],
            "source_website": ["Indeed", "Indeed", "Indeed"],
        })

        result = evaluate_training_readiness(df)

        self.assertFalse(result["ready_for_scraped_only_training"])
        self.assertIn("salary_rows", result["checks"])
        self.assertGreater(len(result["reasons"]), 0)

    def test_readiness_passes_when_thresholds_are_met(self):
        df = pd.DataFrame({
            "salary_usd_numeric": [100000, 120000, 90000, 80000],
            "city": ["New York", "London", "Berlin", "Toronto"],
            "seniority_level": ["Senior", "Mid", "Entry", "Staff"],
            "source_website": ["Indeed", "Levels.fyi", "PayScale", "ZipRecruiter"],
        })
        thresholds = DataReadinessThresholds(
            min_salary_rows=4,
            min_salary_coverage_pct=75,
            min_cities=4,
            min_seniority_levels=4,
            max_single_source_pct=50,
        )

        result = evaluate_training_readiness(df, thresholds)

        self.assertTrue(result["ready_for_scraped_only_training"])
        self.assertEqual(result["salary_rows"], 4)


if __name__ == "__main__":
    unittest.main()
