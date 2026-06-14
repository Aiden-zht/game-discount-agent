import unittest

import cron_digest


class ThresholdLoadingTests(unittest.TestCase):
    def test_threshold_file_points_to_existing_business_specs_file(self):
        self.assertTrue(
            cron_digest.os.path.isfile(cron_digest._KB_THRESHOLDS_FILE),
            cron_digest._KB_THRESHOLDS_FILE,
        )

    def test_load_recommendation_thresholds_reads_business_specs_frontmatter(self):
        thresholds = cron_digest._load_recommendation_thresholds()

        self.assertEqual(thresholds["min_discount_percent"], 10)
        self.assertEqual(thresholds["min_positive_review_percent"], 40)
        self.assertEqual(thresholds["main_card_max"], 9)
        self.assertTrue(thresholds["overflow_to_text_list"])


if __name__ == "__main__":
    unittest.main()
