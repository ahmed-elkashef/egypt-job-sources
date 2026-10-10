import json
import unittest
from unittest.mock import patch

from egypt_job_sources.public_apis import endpoint, parse_page, read, validate_endpoint


class PublicAPITests(unittest.TestCase):
    def muse(self, page=0, page_count=2):
        return {
            "page": page,
            "page_count": page_count,
            "results": [
                {
                    "id": 42,
                    "name": "Role",
                    "contents": "<p>" + "x" * 12000 + "</p>",
                    "publication_date": "2026-10-03T10:00:00Z",
                    "refs": {"landing_page": "https://www.themuse.com/jobs/company/role"},
                }
            ],
        }

    def arbeit(self):
        return {
            "data": [
                {
                    "slug": "role-42",
                    "title": "Role",
                    "description": "x" * 12000,
                    "url": "https://www.arbeitnow.com/jobs/companies/company/role-42",
                }
            ],
            "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=2"},
            "meta": {"current_page": 1},
        }

    def test_muse_zero_page_and_unclipped_body(self):
        raw = self.muse()
        page = parse_page("themuse", json.dumps(raw), endpoint("themuse", 0))
        self.assertEqual(page["page"], 0)
        self.assertEqual(page["listings"][0]["description"], raw["results"][0]["contents"])
        self.assertEqual(page["next_url"], endpoint("themuse", 1))
        self.assertFalse(page["coverage_complete"])
        self.assertFalse(page["reviewed_by_model"])

    def test_native_fields_reconstruct_exactly_without_duplicate_long_body(self):
        for source, raw, field in [
            ("themuse", self.muse(), "contents"),
            ("arbeitnow", self.arbeit(), "description"),
        ]:
            native = raw["results" if source == "themuse" else "data"][0]
            native[field] = "x" * 600000
            parsed = parse_page(source, json.dumps(raw), endpoint(source))["listings"][0]
            self.assertNotIn(field, parsed["source_data"])
            self.assertEqual(parsed["source_description_field"], field)
            self.assertEqual({**parsed["source_data"], field: parsed["description"]}, native)
            self.assertEqual(json.dumps(parsed).count("x" * 600000), 1)

    def test_muse_clamped_response_rejected(self):
        with self.assertRaises(ValueError):
            parse_page("themuse", json.dumps(self.muse(page=1)), endpoint("themuse", 0))

    def test_muse_terminal_and_out_of_range_empty(self):
        self.assertFalse(
            parse_page("themuse", json.dumps(self.muse(page=1)), endpoint("themuse", 1))["has_more"]
        )
        raw = {"page": 2, "page_count": 2, "results": []}
        self.assertFalse(parse_page("themuse", json.dumps(raw), endpoint("themuse", 2))["has_more"])

    def test_muse_empty_nonterminal_not_false_exhaustion(self):
        with self.assertRaises(ValueError):
            parse_page(
                "themuse",
                json.dumps({"page": 0, "page_count": 2, "results": []}),
                endpoint("themuse", 0),
            )

    def test_arbetnow_exact_continuation_and_unclipped_body(self):
        raw = self.arbeit()
        page = parse_page("arbeitnow", json.dumps(raw), endpoint("arbeitnow", 1))
        self.assertEqual(page["next_url"], raw["links"]["next"])
        self.assertEqual(page["listings"][0]["description"], raw["data"][0]["description"])

    def test_arbetnow_terminal_null_required(self):
        raw = self.arbeit()
        raw["links"]["next"] = None
        self.assertFalse(
            parse_page("arbeitnow", json.dumps(raw), endpoint("arbeitnow", 1))["has_more"]
        )
        del raw["links"]["next"]
        with self.assertRaises(ValueError):
            parse_page("arbeitnow", json.dumps(raw), endpoint("arbeitnow", 1))

    def test_arbeitnow_official_sister_posting_hosts(self):
        for host in ["www.arbeitnow.co.uk", "www.arbeitnow.fr", "www.arbeitnow.ch"]:
            raw = self.arbeit()
            raw["data"][0]["url"] = f"https://{host}/jobs/companies/company/role-42"
            page = parse_page("arbeitnow", json.dumps(raw), endpoint("arbeitnow", 1))
            self.assertEqual(page["listings"][0]["url"], raw["data"][0]["url"])

    def test_continuation_scope_and_stall(self):
        for url in [
            "https://evil.test/api/job-board-api?page=2",
            "https://www.arbeitnow.com/api/job-board-api?page=1",
            "https://www.arbeitnow.com/api/job-board-api?page=2&query=role",
        ]:
            raw = self.arbeit()
            raw["links"]["next"] = url
            with self.assertRaises(ValueError):
                parse_page("arbeitnow", json.dumps(raw), endpoint("arbeitnow", 1))

    def test_invalid_page_bool_negative_extra_query_credentials(self):
        for value in [True, -1]:
            with self.assertRaises(ValueError):
                endpoint("themuse", value)
        for url in [
            endpoint("themuse", 0) + "&api_key=secret",
            "https://user:secret@www.themuse.com/api/public/jobs?page=0",
        ]:
            with self.assertRaises(ValueError):
                validate_endpoint("themuse", url)

    def test_muse_registration_gate_precedes_network(self):
        with patch("egypt_job_sources.public_apis.build_opener") as opener:
            with self.assertRaises(ValueError):
                read("themuse", endpoint("themuse", 0))
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
