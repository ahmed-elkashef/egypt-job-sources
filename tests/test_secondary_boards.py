"""Constructed public markup only: no captured jobs, identities or live calls."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from egypt_job_sources import capture
from egypt_job_sources.boards import board_page_url, filter_signature, source_id, validate_board_url
from egypt_job_sources.sources import (
    crawl_board,
    parse_browser_capture,
    parse_detail,
    parse_page,
    query,
)


def tanqeeb_page(
    *, model="2", title="Constructed role", jobtype="Part Time", country="Egypt", next_url=None
):
    filters = f'<section data-public-native-filters data-country="{country}"><span data-filter-name="refine[job_types][]" data-filter-value="{model}">Constructed native label</span><span data-filter-name="refine[order_by]" data-filter-value="most_recent">Most Recent</span></section>'
    card = f'<div id="jobs_list"><article data-job-id="100001" data-job-type="{jobtype}" data-job-closed="0"><h2><a href="/jobs-in-egypt/all/jobs/0100001.html">{title}</a></h2><span class="search-job-date">Yesterday</span><span class="search-job-workplace-location">Egypt</span></article></div>'
    pager = (
        f'<nav aria-label="Search Results Navigation"><a href="{next_url}">Next</a></nav>'
        if next_url
        else ""
    )
    return filters + card + pager


def akhtaboot_empty(
    *, country="Egypt", breadcrumb="Jobs in Egypt", message="Sorry, no results found"
):
    return f'<li id="current_page">{breadcrumb}</li><form id="filter_form"><input name="search[cp_country_name][vals][]" value="{country}"></form><p class="error_message">{message}</p>'


class SecondaryBoardTests(unittest.TestCase):
    def test_tanqeeb_scope_and_identity_reject_query_or_host_drift(self):
        url = board_page_url("tanqeeb")
        self.assertEqual(validate_board_url("tanqeeb", url), url)
        for wrong in [
            url.replace("country=213", "country=113"),
            url + "&keywords=developer",
            url + "&company=Constructed",
            url.replace("most_recent", "oldest"),
            url.replace("https://", "https://user:secret@"),
            url + "#fragment",
        ]:
            with self.subTest(url=wrong), self.assertRaises(ValueError):
                validate_board_url("tanqeeb", wrong)
        self.assertEqual(
            source_id(
                "tanqeeb", "https://egypt.tanqeeb.com/jobs-in-middle-east/all/jobs/0100001.html"
            ),
            "100001",
        )

    def test_native_tanqeeb_state_is_required_and_survives_next_omitting_it(self):
        first, second = (
            board_page_url("tanqeeb"),
            board_page_url("tanqeeb", 2).replace("&order_by=most_recent", ""),
        )
        result = parse_page("tanqeeb", tanqeeb_page(next_url=second), first)
        again = parse_page("tanqeeb", tanqeeb_page(), second)
        self.assertEqual(result["source_filters"], again["source_filters"])
        self.assertIsNone(result["next_url"])
        self.assertEqual(result["observed_next_control_href"], second)
        self.assertEqual(
            result["next_browser_action"]["expected_native_filter_signature"],
            result["source_filters"]["native_filter_signature"],
        )
        self.assertEqual(result["listings"][0]["employment_type_raw"], "Part Time")
        self.assertFalse(result["native_partition_pagination_verified"])
        for body in [
            tanqeeb_page(country="Jordan"),
            tanqeeb_page(model="99"),
            tanqeeb_page().replace("data-public-native-filters", "data-unverified"),
        ]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_page("tanqeeb", body, first)

    def test_native_card_contradictions_and_unknowns_are_not_filtered_by_public_adapter(self):
        for jobtype in ["Full Time", "Full Time / Part Time", "New native label"]:
            result = parse_page(
                "tanqeeb",
                tanqeeb_page(title="Constructed part-time role", jobtype=jobtype),
                board_page_url("tanqeeb"),
            )
            row = result["listings"][0]
            self.assertEqual(row["employment_type_raw"], jobtype)
            self.assertIn("part-time", row["card_text"])
        with self.assertRaises(ValueError):
            board_page_url("tanqeeb", work_model="part_time")

    def test_native_next_scope_and_identity_must_match(self):
        first = board_page_url("tanqeeb")
        for wrong in [board_page_url("tanqeeb", 2).replace("country=213", "country=113"), first]:
            with self.subTest(url=wrong), self.assertRaises(ValueError):
                parse_page("tanqeeb", tanqeeb_page(next_url=wrong), first)
        with self.assertRaises(ValueError):
            parse_page(
                "tanqeeb",
                tanqeeb_page().replace('data-job-id="100001"', 'data-job-id="100002"'),
                first,
            )

    def test_tanqeeb_canonical_detail_preserves_full_text_and_narrow_structured_fields(self):
        url = "https://egypt.tanqeeb.com/jobs-in-egypt/all/jobs/0100001.html"
        posting = {
            "@type": "JobPosting",
            "url": url,
            "datePosted": "2026-01-01T12:00:00+03:00",
            "employmentType": "PART_TIME",
            "applicantLocationRequirements": {
                "@type": "Country",
                "name": "Egypt",
                "privateEmail": "excluded",
            },
            "contact": "excluded",
        }
        body = (
            '<h1>Constructed role</h1><section data-public-job-description><p>Coordinate records.</p><p>Part-time students welcome.</p></section><script type="application/ld+json">'
            + json.dumps(posting)
            + "</script>"
        )
        result = parse_detail("tanqeeb", body, url)
        self.assertIn("Coordinate records.", result["description_text"])
        self.assertEqual(result["source_date_raw"], posting["datePosted"])
        self.assertNotIn("contact", result["source_jobposting"])
        self.assertNotIn(
            "privateEmail", result["source_jobposting"]["applicantLocationRequirements"]
        )
        for wrong in [
            body.replace("/0100001.html", "/0100002.html"),
            body.replace("data-public-job-description", "data-missing"),
        ]:
            with self.subTest(body=wrong), self.assertRaises(ValueError):
                parse_detail("tanqeeb", wrong, url)

    def test_akhtaboot_scoped_empty_is_distinct_from_challenge_or_shell(self):
        url = board_page_url("akhtaboot")
        result = parse_page("akhtaboot", akhtaboot_empty(), url)
        self.assertEqual(result["listings"], [])
        self.assertTrue(result["native_empty_state_verified"])
        self.assertEqual(result["reported_total"], 0)
        for body in [
            "",
            "<p>Checking your browser</p>",
            akhtaboot_empty(country="Jordan"),
            akhtaboot_empty(breadcrumb="Jobs in Jordan"),
            akhtaboot_empty(message="Loading"),
            akhtaboot_empty()
            + '<div class="pagination"><a rel="next" href="?page=2">Next</a></div>',
        ]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_page("akhtaboot", body, url)

    def test_akhtaboot_http_zero_and_failures_preserve_truthful_states(self):
        with patch("egypt_job_sources.sources.read", return_value=akhtaboot_empty()):
            result = query("akhtaboot")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["coverage_complete"])
        with patch("egypt_job_sources.sources.read", side_effect=OSError("403")):
            result = query("akhtaboot")
        self.assertEqual(result["status"], "source_limited")
        self.assertNotIn("listings", result)
        with self.assertRaises(ValueError):
            validate_board_url(
                "akhtaboot",
                "https://www.akhtaboot.com/en/jordan/jobs/amman/100001-constructed",
                detail=True,
            )

    def test_akhtaboot_full_native_card_detail_identity_and_worker_fields(self):
        url = "https://www.akhtaboot.com/en/egypt/jobs/cairo/100001-constructed-role"
        card = (
            '<div class="row"><small>Ref. Number: 100001<br>Date Posted: 01-01-2026</small><div class="col-md-9"><a class="job-link" href="'
            + url
            + '"><h4>Constructed role</h4></a><p class="no-margin">Constructed company — Cairo, Egypt</p></div></div>'
        )
        page = akhtaboot_empty().replace(
            '<p class="error_message">Sorry, no results found</p>', card
        )
        parsed = parse_page("akhtaboot", page, board_page_url("akhtaboot"))
        self.assertEqual(parsed["listings"][0]["id"], "100001")
        self.assertFalse(parsed["native_empty_state_verified"])
        body = '<h1>Constructed role</h1><dl><dt>Ref. Number:</dt><dd>100001</dd><dt>Residence Country</dt><dd>Egypt</dd><dt>Citizenships</dt><dd>Egypt</dd><dt>Private field</dt><dd>excluded</dd></dl><div class="description-list"><dl><dt>Job Description and Requirements</dt><dd><p>Coordinate records.</p><p>Students welcome.</p></dd></dl></div>'
        detail = parse_detail("akhtaboot", body, url)
        self.assertIn("Students welcome.", detail["description_text"])
        self.assertEqual(detail["applicant_residence_country_raw"], "Egypt")
        self.assertNotIn("Private field", detail["source_metadata"])
        with self.assertRaises(ValueError):
            parse_detail("akhtaboot", body.replace("<dd>100001</dd>", "<dd>100002</dd>"), url)

    def test_capture_round_trip_reparses_new_source_without_fetch(self):
        obj = {
            "url": board_page_url("tanqeeb"),
            "kind": "page",
            "captured_at": "2026-01-01T12:00:00Z",
            "html": tanqeeb_page(),
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("egypt_job_sources.sources.read") as reader,
        ):
            receipt = capture.save_capture("tanqeeb", obj, Path(directory))
            restored = capture.read_capture(receipt["receipt_id"], Path(directory))
            self.assertEqual(receipt["listings"], restored["listings"])
            reader.assert_not_called()

    def test_akhtaboot_explicit_empty_crawl_retains_only_current_partition_claim(self):
        url = board_page_url("akhtaboot")
        response = {
            "status": "ok",
            "requested_url": url,
            **parse_page("akhtaboot", akhtaboot_empty(), url),
        }
        result = crawl_board("akhtaboot", max_pages=2, fetch=lambda _: response, delay=0)
        self.assertTrue(result["native_partition_pagination_verified"])
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(result["stop_reason"], "source_scoped_empty_state_verified")

    def test_arabjobs_verified_model_filters_and_continuation(self):
        for model, native in {
            "full_time": "1",
            "part_time": "2",
            "contract_temp": "3",
            "consultant": "4",
            "freelance": "5",
        }.items():
            first, second = (
                board_page_url("arabjobs", 1, model),
                board_page_url("arabjobs", 2, model),
            )
            self.assertIn("filterJobType=" + native, first)
            self.assertEqual(
                filter_signature("arabjobs", first), filter_signature("arabjobs", second)
            )
            self.assertEqual(validate_board_url("arabjobs", second), second)
        with patch("egypt_job_sources.sources.read") as reader:
            with self.assertRaises(ValueError):
                query(
                    "arabjobs",
                    work_model="part_time",
                    continuation_url=board_page_url("arabjobs", 2, "full_time"),
                )
            reader.assert_not_called()
        for invalid in [
            board_page_url("arabjobs") + "&filterJobType=99",
            board_page_url("arabjobs") + "&filterJobType=2&filterJobType=1",
        ]:
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                validate_board_url("arabjobs", invalid)

    def test_arabjobs_native_javascript_next_keeps_selected_model(self):
        first = board_page_url("arabjobs", 1, "part_time")
        body = '<div><h3><a href="/en/jobs/j/constructed/egypt/100001">Constructed role</a></h3><h5><span>Job Type:</span>Part Time</h5></div><a href="javascript:PagerGo(2)">Next</a>'
        page = parse_page("arabjobs", body, first)
        self.assertIn("filterJobType=2", page["next_url"])
        self.assertEqual(
            filter_signature("arabjobs", first), filter_signature("arabjobs", page["next_url"])
        )

    def test_forasna_missing_actual_duties_does_not_pass_as_full_description(self):
        body = '<h1>Constructed role</h1><section><div><h3>تفاصيل الوظيفة</h3></div><ul><li>Category metadata</li></ul><div class="job-more-info descri"><p class="job-bio"> </p></div></section><section><div><h3>متطلبات الوظيفة</h3></div><p>Student welcome</p></section>'
        result = parse_browser_capture(
            "forasna",
            {
                "url": "https://forasna.com/job/p/constructed-100001",
                "kind": "detail",
                "captured_at": "2026-01-01T12:00:00Z",
                "html": body,
            },
        )
        self.assertEqual(result["status"], "source_limited")
        self.assertIn("full task description is missing", result["error"])

    def test_forasna_native_half_day_requires_exact_Egypt_and_keeps_continuation_scope(self):
        from urllib.parse import parse_qs, urlsplit

        first = board_page_url("forasna", work_model="part_time")
        self.assertEqual(
            parse_qs(urlsplit(first).query),
            {"filters[country][0]": ["مصر"], "filters[jobType][0]": ["نصف يوم"]},
        )
        self.assertEqual(validate_board_url("forasna", first), first)
        second = first + "&start=30"
        self.assertEqual(filter_signature("forasna", first), filter_signature("forasna", second))
        for wrong in [
            first.replace("jobType", "jobtype"),
            first.replace("%D9%85%D8%B5%D8%B1", "Jordan"),
            first.replace("filters%5Bcountry%5D%5B0%5D=%D9%85%D8%B5%D8%B1&", ""),
        ]:
            with self.subTest(url=wrong), self.assertRaises(ValueError):
                validate_board_url("forasna", wrong)
        with patch("egypt_job_sources.sources.read") as reader:
            with self.assertRaises(ValueError):
                query(
                    "forasna",
                    work_model="part_time",
                    continuation_url=board_page_url("forasna") + "?start=30",
                )
            reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
