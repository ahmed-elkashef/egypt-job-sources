"""Independent safety and incomplete-coverage checks for Egypt acquisition."""

import copy
import http.client
import json
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import Request

from egypt_job_sources.boards import (
    board_page_url,
    parse_board_page,
    source_id,
    validate_board_url,
)
from egypt_job_sources.capture import handler_for, read_capture, save_capture
from egypt_job_sources.sources import (
    SameHostRedirects,
    SourceFailure,
    crawl_board,
    detail_url,
    parse_browser_capture,
    parse_detail,
    query,
)
from egypt_job_sources.wuzzuf import (
    canonical_detail_url,
    search_body,
)
from egypt_job_sources.wuzzuf import (
    parse_page as parse_wuzzuf_api_page,
)
from egypt_job_sources.wuzzuf import (
    read_json as read_wuzzuf_json,
)


class EgyptBoardReviewTests(unittest.TestCase):
    def test_forasna_encoded_title_slash_keeps_both_page_records(self):
        # Synthetic Arabic title with an encoded slash in one URL segment.
        cashier = "https://forasna.com/job/p/%D8%A7%D8%AE%D8%AA%D8%A8%D8%A7%D8%B1-%2F-%D9%85%D8%AB%D8%A7%D9%84-100001"
        purchasing = "https://forasna.com/job/p/example-%2F-other-100002"
        body = f"""<div class="item-details"><div><h2 class="job-title">
            <a href="{cashier}">اختبار / مثال</a></h2></div><a>نصف يوم</a></div>
            <div class="item-details"><div><h2 class="job-title">
            <a href="{purchasing}">Example / other</a></h2></div><a>عمل حر</a></div>
            <a href="?start=60">التالى</a>"""
        observed = board_page_url("forasna") + "?start=30"
        result = parse_board_page("forasna", body, observed)
        self.assertEqual([x["id"] for x in result["listings"]], ["100001", "100002"])
        self.assertEqual(result["listings"][0]["url"], cashier)
        self.assertIn("%2F", result["listings"][1]["url"])
        self.assertEqual(
            result["observed_next_control_href"], board_page_url("forasna") + "?start=60"
        )
        self.assertEqual(result["observed_forward_href"], board_page_url("forasna") + "?start=60")
        self.assertIsNone(result["next_url"])
        self.assertEqual(source_id("forasna", cashier), "100001")
        for invalid in [
            cashier.replace("%2F", "/"),
            cashier.replace("https://forasna.com", "https://evil.test"),
            cashier + "?token=secret",
            cashier.rsplit("-", 1)[0] + "-missing-id",
        ]:
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                validate_board_url("forasna", invalid, detail=True)

    def test_forasna_pagination_requires_observed_browser_controls(self):
        base = board_page_url("forasna")
        for inferred_page in [2, 3, 100]:
            with self.subTest(page=inferred_page), self.assertRaises(ValueError):
                board_page_url("forasna", inferred_page)
        current = base + "?start=60"
        body = """<div class="item-details"><div><h2 class="job-title">
            <a href="https://forasna.com/job/p/example-100001">Example</a></h2></div></div>
            <ul><li class="pag-current"><span>3</span></li>
            <li><a href="?start=90">4</a></li><li><a href="?start=60">التالى</a></li></ul>"""
        result = parse_browser_capture(
            "forasna",
            {
                "kind": "page",
                "url": current,
                "html": body,
                "captured_at": "2026-10-09T23:00:00+02:00",
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rendered_page_number"], 3)
        self.assertEqual(result["url_pagination_position"], 60)
        self.assertEqual(result["observed_next_control_href"], current)
        self.assertEqual(result["observed_forward_href"], base + "?start=90")
        self.assertIsNone(result["next_url"])
        self.assertTrue(result["next_browser_action"])

    def test_full_description_keeps_words_separated_across_html_blocks(self):
        body = """<h1>Example role</h1>
            <div><h2>Job Description</h2><p>Coordinate<br>events</p></div>
            <div><h2>Job Requirements</h2><ul><li>Python</li><li>SQL</li></ul></div>"""
        result = parse_detail("wuzzuf", body)
        self.assertIn("Coordinate events", result["sections"]["Job Description"]["text"])
        self.assertIn("Python SQL", result["sections"]["Job Requirements"]["text"])
        self.assertIn("<li>Python</li>", result["sections"]["Job Requirements"]["html"])

    def test_sparse_source_description_is_evidence_without_invented_content(self):
        body = """<h1>Example role</h1>
            <div class="panel-heading">Job Description</div><div>.</div>
            <div><div class="panel-heading">Job Requirements</div><p>Any</p></div>"""
        result = parse_detail("arabjobs", body)
        self.assertEqual(result["sections"]["Job Description"]["text"], ".")
        self.assertEqual(result["source_description_quality"], "sparse")
        self.assertEqual(result["availability_status"], "not_verified")

    def test_empty_username_still_counts_as_userinfo(self):
        for url in [
            "https://:secret@www.bayt.com/en/egypt/jobs/example-123/",
            "https://@www.bayt.com/en/egypt/jobs/example-123/",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                detail_url("bayt", url)
        with self.assertRaises(ValueError):
            validate_board_url(
                "wuzzuf", "https://@wuzzuf.net/search/jobs?filters%5Bcountry%5D%5B0%5D=Egypt"
            )

    def test_browser_capture_is_a_parser_and_never_fetches(self):
        capture = {
            "url": board_page_url("wuzzuf", work_model="part_time"),
            "kind": "page",
            "captured_at": "2026-10-09T22:00:00+02:00",
            "html": """<div><div><h2><a href="/jobs/p/abcdefghijkl-example-egypt">Example</a></h2></div>
                <a>Part Time</a></div>""",
        }
        with patch("egypt_job_sources.sources.read") as network:
            result = parse_browser_capture("wuzzuf", capture)
        network.assert_not_called()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["listings"][0]["employment_models"], ["part_time"])
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(result["reviewed_by_model"])
        self.assertEqual(result["provenance"], "operator_supplied_capture")

    def test_bad_capture_cannot_look_like_zero_supply(self):
        base = {
            "url": board_page_url("forasna"),
            "kind": "page",
            "captured_at": "2026-10-09T20:00:00Z",
            "html": "<h1>Access denied</h1>",
        }
        for replacement in [
            {},
            {"captured_at": "2026-10-09T20:00:00"},
            {"url": "https://evil.test/"},
        ]:
            with self.subTest(replacement=replacement):
                result = parse_browser_capture("forasna", base | replacement)
                self.assertEqual(result["status"], "source_limited")
                self.assertNotIn("listings", result)
                self.assertFalse(result["coverage_complete"])

    def test_native_pagination_does_not_accept_keyword_or_account_scope(self):
        invalid = [
            ("wuzzuf", board_page_url("wuzzuf") + "&q=developer"),
            ("forasna", board_page_url("forasna") + "?keyword=student"),
            ("arabjobs", board_page_url("arabjobs") + "&filterJobTitle=engineer"),
            ("wuzzuf", "https://wuzzuf.net/login"),
            ("forasna", "https://u:p@forasna.com/"),
        ]
        for source, url in invalid:
            with self.subTest(source=source, url=url), self.assertRaises(ValueError):
                validate_board_url(source, url)

    def test_overlap_is_deduplicated_without_completion_claim(self):
        first = board_page_url("forasna")
        # Explicitly observed continuation; never infer its offset from a page number.
        second = first + "?start=30"
        pages = {
            first: self.response(first, ["1", "2"], "first", second),
            second: self.response(second, ["2", "3"], "second", None),
        }
        result = crawl_board("forasna", max_pages=3, fetch=pages.__getitem__, delay=0)
        self.assertEqual(result["unique_count"], 3)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stop_reason"], "no_observed_continuation_operator_must_reconcile")
        self.assertFalse(result["coverage_complete"])

    def test_repeated_page_is_a_limit_not_exhausted_supply(self):
        first = board_page_url("wuzzuf")
        second = board_page_url("wuzzuf", 2)
        pages = {
            first: self.response(first, ["1", "2"], "same", second),
            second: self.response(second, ["1", "2"], "same", None),
        }
        result = crawl_board("wuzzuf", max_pages=3, fetch=pages.__getitem__, delay=0)
        self.assertEqual(result["status"], "source_limited")
        self.assertEqual(result["stop_reason"], "repeated_or_unverified_page")
        self.assertFalse(result["coverage_complete"])

    def test_wuzzuf_terminal_requires_stable_total_and_complete_unique_inventory(self):
        first = board_page_url("wuzzuf", work_model="part_time")
        second = board_page_url("wuzzuf", 2, work_model="part_time")
        cases = [
            ("total_changed", 31, range(16, 31), "source_total_drift", False),
            ("overlap_hides_missing_job", 30, range(15, 30), "terminal_count_mismatch", False),
            ("consistent_terminal", 30, range(16, 31), "source_terminal_count_verified", True),
        ]
        for name, second_total, second_ids, stop_reason, verified in cases:
            with self.subTest(case=name):
                pages = {
                    first: self.response(first, [str(x) for x in range(1, 16)], "first", second)
                    | {"reported_total": 30, "has_more": True},
                    second: self.response(second, [str(x) for x in second_ids], "second", None)
                    | {"reported_total": second_total, "has_more": False},
                }
                result = crawl_board(
                    "wuzzuf", max_pages=3, work_model="part_time", fetch=pages.__getitem__, delay=0
                )
                self.assertEqual(result["source_totals_by_page"], [30, second_total])
                self.assertEqual(result["stop_reason"], stop_reason)
                self.assertEqual(result["native_partition_pagination_verified"], verified)
                self.assertEqual(result["status"], "partial" if verified else "source_limited")
                self.assertFalse(result["coverage_complete"])
                self.assertFalse(result["reviewed_by_model"])
                if name == "overlap_hides_missing_job":
                    self.assertEqual(result["unique_count"], 29)
                    self.assertEqual(result["duplicate_count"], 1)
                elif verified:
                    self.assertEqual(result["unique_count"], 30)

    def test_filter_drift_stops_before_second_request(self):
        first = board_page_url("wuzzuf", work_model="part_time")
        wrong = board_page_url("wuzzuf", 2, work_model="freelance")
        calls = []

        def fetch(url):
            calls.append(url)
            return self.response(url, ["1"], "first", wrong)

        result = crawl_board("wuzzuf", max_pages=3, work_model="part_time", fetch=fetch, delay=0)
        self.assertEqual(calls, [first])
        self.assertEqual(result["status"], "source_limited")
        self.assertEqual(result["stop_reason"], "filter_drift")

    @staticmethod
    def response(url, ids, fingerprint, next_url):
        return {
            "status": "ok",
            "requested_url": url,
            "listings": [{"id": job_id} for job_id in ids],
            "page_fingerprint": fingerprint,
            "next_url": next_url,
        }


class EgyptCaptureReceiverReviewTests(unittest.TestCase):
    @staticmethod
    def capture():
        return {
            "url": board_page_url("wuzzuf", work_model="part_time"),
            "kind": "page",
            "captured_at": "2026-10-09T22:00:00+02:00",
            "html": """<div><div><h2><a href="/jobs/p/abcdefghijkl-example-egypt">Example</a></h2></div>
                <a>Part Time</a></div>""",
        }

    def test_save_is_idempotent_and_does_not_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("egypt_job_sources.sources.read") as network:
                first = save_capture("wuzzuf", self.capture(), directory)
                second = save_capture("wuzzuf", self.capture(), directory)
            network.assert_not_called()
            self.assertEqual(first["receipt_id"], second["receipt_id"])
            self.assertEqual(first["received_at"], second["received_at"])
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
            self.assertFalse(first["coverage_complete"])
            self.assertFalse(first["reviewed_by_model"])
            self.assertIn("operator_capture_unregistered_supply", first["evidence_purpose"])

    def test_modified_original_fails_digest_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            result = save_capture("wuzzuf", self.capture(), directory)
            path = Path(directory) / (result["receipt_id"] + ".json")
            receipt = json.loads(path.read_text())
            receipt["payload"]["capture"]["html"] += "<p>Tampered</p>"
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                read_capture(result["receipt_id"], directory)

    def test_checkpoint_cannot_follow_traversal_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            for invalid in ["../secret", "A" * 64, "b" * 63, "b" * 65]:
                with self.subTest(receipt_id=invalid), self.assertRaises(ValueError):
                    read_capture(invalid, directory)
            target = Path(directory) / ("a" * 64 + ".json")
            outside = Path(directory) / "outside.json"
            outside.write_text("{}")
            target.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "Invalid capture checkpoint"):
                read_capture("a" * 64, directory)

    def test_unknown_capture_fields_are_not_persisted(self):
        capture = copy.deepcopy(self.capture())
        capture["cookies"] = "unrelated authentication data"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_capture("wuzzuf", capture, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_http_origin_boundary_and_valid_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            server = HTTPServer(("127.0.0.1", 0), handler_for(directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            body = urlencode({"source": "wuzzuf", "capture": json.dumps(self.capture())})

            def post(extra_headers):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                try:
                    connection.request(
                        "POST",
                        "/capture",
                        body,
                        {"Content-Type": "application/x-www-form-urlencoded"} | extra_headers,
                    )
                    response = connection.getresponse()
                    return response.status, response.read().decode()
                finally:
                    connection.close()

            try:
                for headers in [
                    {},
                    {"Origin": "null"},
                    {"Origin": "https://evil.test"},
                    {"Origin": origin, "Host": "evil.test"},
                ]:
                    with self.subTest(headers=headers):
                        self.assertEqual(post(headers)[0], 403)
                self.assertEqual(list(Path(directory).iterdir()), [])
                status, response = post({"Origin": origin})
                self.assertEqual(status, 200)
                self.assertIn("Coverage remains incomplete", response)
                self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


class WuzzufAPIReviewTests(unittest.TestCase):
    API_ID = "123e4567-e89b-12d3-a456-426614174000"
    SECOND_ID = "123e4567-e89b-12d3-a456-426614174001"

    @classmethod
    def resource(cls, api_id=None):
        return {
            "type": "job",
            "id": api_id or cls.API_ID,
            "attributes": {
                "title": "Example role",
                "uri": "jobs/p/abcdefghijkl-example-role-egypt",
                "description": "<p>Maintain Open<b>CV</b><br>and Python.</p>",
                "requirements": "<ul><li><p></p></li></ul>",
                "location": {"country": {"code": "EG", "name": "Egypt"}},
                "workTypes": [{"name": "part_time"}, {"name": "freelance_project"}],
                "status": "active",
                "postedAt": "10/07/2026 14:14:56",
                "hideSalary": True,
                "insights": {"applied": 99},
            },
        }

    @classmethod
    def search(cls, ids=None):
        ids = ids if ids is not None else [cls.API_ID]
        return {
            "meta": {"totalResultsCount": len(ids)},
            "data": [{"id": api_id, "type": "talentSearch", "attributes": {}} for api_id in ids],
        }

    def test_native_body_is_egypt_only_without_title_or_keyword_query(self):
        body = search_body(2, "freelance")
        self.assertEqual(
            body["searchFilters"], {"country": ["Egypt"], "job_types": ["freelance_project"]}
        )
        self.assertEqual(body["query"], "")
        self.assertEqual(body["startIndex"], 15)
        self.assertEqual(body["pageSize"], 15)
        for invalid_page in [True, "2", 0, 10001]:
            with self.subTest(page=invalid_page), self.assertRaises(ValueError):
                search_body(invalid_page)

    def test_main_query_routes_observed_continuation_to_native_api_partition(self):
        continuation = board_page_url("wuzzuf", 3, "freelance")
        acquired = {"status": "ok", "coverage_complete": False, "reviewed_by_model": False}
        with patch(
            "egypt_job_sources.sources.wuzzuf_api.query_page", return_value=acquired.copy()
        ) as api:
            with patch("egypt_job_sources.sources.read") as generic_transport:
                result = query("wuzzuf", continuation_url=continuation, work_model="freelance")
        api.assert_called_once_with(3, "freelance_project")
        generic_transport.assert_not_called()
        self.assertEqual(result["requested_url"], continuation)
        self.assertFalse(result["coverage_complete"])
        with patch("egypt_job_sources.sources.wuzzuf_api.query_page") as api:
            with self.assertRaises(ValueError):
                query("wuzzuf", continuation_url=continuation, work_model="part_time")
            api.assert_not_called()

    def test_existing_public_identity_survives_api_hydration(self):
        result = parse_wuzzuf_api_page(self.search(), {"data": [self.resource()]}, 1, "part_time")
        self.assertEqual(result["status"], "ok")
        job = result["listings"][0]
        self.assertEqual(job["id"], "abcdefghijkl")
        self.assertEqual(job["api_id"], self.API_ID)
        self.assertTrue(job["requirements_source_empty"])
        self.assertIn("OpenCV", job["sections"]["Job Description"]["text"])
        self.assertEqual(job["posted_at_raw"], "10/07/2026 14:14:56")
        self.assertNotIn("insights", job["source_attributes"])
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(job["reviewed_by_model"])

    def test_missing_hydration_retains_ids_and_pending_evidence(self):
        result = parse_wuzzuf_api_page(
            self.search([self.API_ID, self.SECOND_ID]), {"data": [self.resource()]}, 1, "part_time"
        )
        self.assertEqual(result["status"], "source_limited")
        self.assertEqual(result["search_ids"], [self.API_ID, self.SECOND_ID])
        self.assertEqual(result["missing_detail_ids"], [self.SECOND_ID])
        self.assertEqual(len(result["listings"]), 2)
        self.assertEqual(result["listings"][1]["detail_status"], "missing_or_invalid")

    def test_country_and_model_contradictions_are_explicit_limits(self):
        for attr, value in [
            ("location", {"country": {"code": "US", "name": "United States"}}),
            ("workTypes", [{"name": "full_time"}]),
        ]:
            resource = self.resource()
            resource["attributes"][attr] = value
            result = parse_wuzzuf_api_page(self.search(), {"data": [resource]}, 1, "part_time")
            with self.subTest(attr=attr):
                self.assertEqual(result["status"], "source_limited")
                self.assertTrue(result["issues"])
                self.assertEqual(len(result["listings"]), 1)

    def test_api_cannot_fetch_other_hosts_or_mutation_paths(self):
        for url, kwargs in [
            ("http://wuzzuf.net/api/job", {}),
            ("https://evil.test/api/job", {}),
            ("https://wuzzuf.net:443/api/job", {}),
            ("https://:secret@wuzzuf.net/api/job", {}),
            ("https://wuzzuf.net/api/application", {}),
            ("https://wuzzuf.net/api/job", {"method": "POST", "body": {}}),
            ("https://wuzzuf.net/api/search/job", {"method": "DELETE"}),
        ]:
            with (
                self.subTest(url=url, kwargs=kwargs),
                patch("urllib.request.build_opener") as opener,
            ):
                with self.assertRaises(ValueError):
                    read_wuzzuf_json(url, **kwargs)
                opener.assert_not_called()
        with self.assertRaises(ValueError):
            canonical_detail_url("https://wuzzuf.net/jobs/p/abcdefghijkl-example?token=secret")


class SourceRedirectReviewTests(unittest.TestCase):
    def test_arabjobs_canonical_detail_redirect_preserves_same_public_id(self):
        before = "https://www.arabjobs.com/en/jobs/j/old-title/egypt/12345"
        after = "https://www.arabjobs.com/en/jobs/j/current-title/eg/12345"
        handler = SameHostRedirects()
        result = handler.redirect_request(Request(before), None, 302, "Found", {}, after)
        self.assertEqual(result.full_url, after)

    def test_redirect_cannot_change_country_query_page_or_detail_identity(self):
        before = "https://www.arabjobs.com/en/jobs/j/old-title/egypt/12345"
        destinations = [
            "https://www.arabjobs.com/en/jobs/j/current-title/eg/12346",
            "https://evil.test/en/jobs/j/current-title/eg/12345",
            "https://www.arabjobs.com/en/jobs/j/current-title/eg/12345?token=secret",
            "https://www.arabjobs.com/login",
        ]
        handler = SameHostRedirects()
        for after in destinations:
            with self.subTest(after=after), self.assertRaises(SourceFailure):
                handler.redirect_request(Request(before), None, 302, "Found", {}, after)
        page = board_page_url("arabjobs")
        with self.assertRaises(SourceFailure):
            handler.redirect_request(
                Request(page), None, 302, "Found", {}, page.replace("EG", "US")
            )


if __name__ == "__main__":
    unittest.main()
