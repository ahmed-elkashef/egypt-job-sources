"""Public-export behavior: broad defaults and local cache, using synthetic data."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from egypt_job_sources import capture, wuzzuf
from egypt_job_sources.boards import board_page_url, validate_board_url
from egypt_job_sources.sources import page_url, parse_page


class PublicPackageTests(unittest.TestCase):
    def test_country_default_does_not_apply_candidate_employment_preferences(self):
        params = parse_qs(urlsplit(page_url("himalayas", 2)).query)
        self.assertEqual(params, {"country": ["EG"], "sort": ["recent"], "page": ["2"]})
        self.assertEqual(wuzzuf.search_body(1)["searchFilters"], {"country": ["Egypt"]})

    def test_full_time_is_a_verified_optional_public_partition(self):
        self.assertEqual(
            wuzzuf.search_body(2, "full_time")["searchFilters"],
            {"country": ["Egypt"], "job_types": ["full_time"]},
        )
        url = board_page_url("wuzzuf", 2, "full_time")
        self.assertEqual(url, wuzzuf.public_page_url(2, "full_time"))
        self.assertEqual(validate_board_url("wuzzuf", url), url)

    def test_default_capture_cache_is_under_user_home_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(capture.Path, "home", return_value=home),
            ):
                self.assertEqual(
                    capture.capture_directory(),
                    home / ".cache/egypt-job-sources/public-captures",
                )
                self.assertEqual(list(home.iterdir()), [])

    def test_capture_env_override_is_local_and_blank_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            explicit = Path(directory) / "chosen-cache"
            with patch.dict(os.environ, {"EGYPT_JOBS_CAPTURE_DIR": str(explicit)}):
                self.assertEqual(capture.capture_directory(), explicit.resolve())
                self.assertFalse(explicit.exists())
            with patch.dict(os.environ, {"EGYPT_JOBS_CAPTURE_DIR": " "}):
                with self.assertRaises(ValueError):
                    capture.capture_directory()

    def test_default_save_uses_only_explicit_cache_and_is_retrievable(self):
        example = {
            "url": board_page_url("wuzzuf"),
            "kind": "page",
            "captured_at": "2025-01-01T12:00:00Z",
            "html": '<div><div><h2><a href="/jobs/p/abcdefghijkl-example-egypt">Example</a></h2></div></div>',
        }
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"EGYPT_JOBS_CAPTURE_DIR": directory}):
                result = capture.save_capture("wuzzuf", example)
                restored = capture.read_capture(result["receipt_id"])
            self.assertEqual(restored["receipt_id"], result["receipt_id"])
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
            self.assertFalse(restored["coverage_complete"])

    def test_feed_terms_are_explicit_even_for_empty_valid_response(self):
        jobicy = parse_page("jobicy", '{"jobs":[],"hasMore":false}', "")
        self.assertTrue(any("hourly" in limit for limit in jobicy["limits"]))
        himalayas = parse_page("himalayas", '{"jobs":[]}', "")
        self.assertTrue(any("attribution" in limit for limit in himalayas["limits"]))


if __name__ == "__main__":
    unittest.main()
