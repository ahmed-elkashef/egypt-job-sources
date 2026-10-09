import unittest
from unittest.mock import patch

from egypt_job_sources.sources import detail_url, page_url, parse_page, query


class EgyptSourceTests(unittest.TestCase):
    def test_country_only_and_opaque_cursor(self):
        self.assertIn("country=EG", page_url("himalayas", 2))
        self.assertIn("cursor=a%2Bb%26c", page_url("jobicy", cursor="a+b&c"))
        with self.assertRaises(ValueError):
            page_url("jobicy", 2)

    def test_blocked_page_is_not_zero_results(self):
        with patch("egypt_job_sources.sources.read", side_effect=RuntimeError("HTTP 403")):
            result = query("bayt")
        self.assertEqual(result["status"], "source_limited")
        self.assertNotIn("listings", result)
        with self.assertRaises(ValueError):
            parse_page("bayt", "<html>Access denied</html>", "https://www.bayt.com/en/egypt/jobs/")

    def test_more_results_require_cursor_and_keep_restrictions(self):
        with self.assertRaises(ValueError):
            parse_page("jobicy", '{"jobs":[],"hasMore":true}', "")
        result = parse_page(
            "himalayas",
            '{"jobs":[{"locationRestrictions":["Egypt"],"description":"<p>Full</p>"}],"totalCount":21}',
            "",
        )
        self.assertEqual(result["listings"][0]["locationRestrictions"], ["Egypt"])
        self.assertEqual(result["reported_total"], 21)

    def test_detail_cannot_fetch_credentials_or_arbitrary_hosts(self):
        for url in [
            "https://evil.test/en/egypt/jobs/example-123/",
            "https://u:p@www.bayt.com/en/egypt/jobs/example-123/",
            "https://www.bayt.com/en/egypt/jobs/example-123/?token=secret",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                detail_url("bayt", url)


if __name__ == "__main__":
    unittest.main()
