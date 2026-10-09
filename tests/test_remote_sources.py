"""Broad-feed behavior and transport boundaries using synthetic source records."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from egypt_job_sources import remote


def remotive_row(identifier=100):
    return {
        "id": identifier,
        "url": f"https://remotive.com/remote-jobs/other/synthetic-{identifier}",
        "title": "Synthetic opportunity",
        "company_name": "Example organization",
        "description": "<p>" + "Complete synthetic work description. " * 120 + "</p>",
        "job_type": "part_time",
        "publication_date": "2026-01-01T12:30:00",
        "candidate_required_location": "Worldwide",
        "salary": "USD 20/hour",
    }


def remotive_feed(rows=None):
    rows = [remotive_row()] if rows is None else rows
    return json.dumps({"0-legal-notice": "Synthetic terms", "job-count": len(rows), "jobs": rows})


def remoteok_row(identifier=100):
    return {
        "id": str(identifier),
        "url": f"https://remoteOK.com/remote-jobs/synthetic-{identifier}",
        "position": "Synthetic opportunity",
        "description": "<p>Source description</p>",
        "date": "2026-01-01T12:30:00+00:00",
        "location": "Worldwide",
        "salary_min": 0,
        "salary_max": 0,
    }


def himalayas_feed(cursor="c3ludGhldGlj"):
    return json.dumps(
        {
            "totalCount": 21,
            "limit": 20,
            "offset": 0,
            "nextCursor": cursor,
            "comments": "Synthetic source notice",
            "jobs": [
                {
                    "guid": "https://himalayas.app/jobs/synthetic-opportunity",
                    "title": "Synthetic opportunity",
                    "description": "<p>Full source description</p>",
                    "employmentType": "Contractor",
                    "salaryPeriod": "hourly",
                    "currency": "EUR",
                    "minSalary": 20,
                    "maxSalary": 25,
                    "locationRestrictions": ["Egypt"],
                    "timezoneRestrictions": ["UTC+02:00"],
                    "pubDate": 1767270600,
                    "applicationLink": "https://example.invalid/apply?reference=synthetic",
                }
            ],
        }
    )


RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Example feed</title>
<item><guid isPermaLink="false">synthetic-100</guid>
<link>https://weworkremotely.com/remote-jobs/example-synthetic</link>
<title>Example organization: Synthetic opportunity</title><type>Contract</type>
<region>Anywhere</region><country>Egypt</country><skills>First</skills><skills>Second</skills>
<description><![CDATA[<p>Full synthetic source description.</p>]]></description>
<pubDate>Thu, 01 Jan 2026 12:30:00 +0000</pubDate></item></channel></rss>"""


class FakeResponse(io.BytesIO):
    def __init__(self, body, url, *, status=200, headers=None):
        super().__init__(body)
        self.url = url
        self.status = status
        self.headers = {} if headers is None else headers

    def geturl(self):
        return self.url


class RemoteSourcesTests(unittest.TestCase):
    def test_unfiltered_endpoints_are_fixed_and_cursor_is_not_a_filter(self):
        for source in remote.SOURCES:
            url = remote.endpoint(source)
            self.assertEqual(remote.validate_endpoint(url), url)
            params = parse_qs(urlsplit(url).query)
            self.assertEqual(params, {"limit": ["20"]} if source == "himalayas_global" else {})
        url = remote.endpoint("himalayas_global", "a+b/c==")
        self.assertEqual(parse_qs(urlsplit(url).query)["cursor"], ["a+b/c=="])
        self.assertEqual(remote.validate_endpoint(url), url)

    def test_arbitrary_urls_and_filters_cannot_reach_transport(self):
        invalid = [
            "https://evil.test/api",
            "http://remoteok.com/api",
            "https://u:p@remoteok.com/api",
            "https://remoteok.com:443/api",
            "https://remoteok.com/api?tag=python",
            "https://remoteok.com/api#fragment",
            "https://remoteok.com/remote-jobs/synthetic-100",
            "https://himalayas.app/jobs/api?limit=20&q=python",
            "https://himalayas.app/jobs/api?limit=20&cursor=abc&cursor=abc",
            "https://himalayas.app/jobs/api?limit=20&cursor=https%3A%2F%2Fevil.test",
            "https://himalayas.app/jobs/api?limit=21&cursor=abc",
            "https://himalayas.app/jobs/api?offset=20",
        ]
        with patch.object(remote, "build_opener") as opener:
            for url in invalid:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    remote.read(url)
            opener.assert_not_called()

    def test_invalid_source_or_cursor_is_rejected_before_fetch(self):
        def unexpected(url):
            self.fail("Invalid argument reached network transport")

        for source, cursor in [
            ("unknown", None),
            ("remotive", "abc"),
            ("himalayas_global", ""),
            ("himalayas_global", "https://evil.test/token=secret"),
            ("himalayas_global", "abc\nAuthorization: secret"),
        ]:
            result = remote.query(source, cursor, fetch=unexpected)
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
            self.assertNotIn("secret", result["error"])

    def test_remotive_all_records_and_full_descriptions_survive(self):
        rows = [remotive_row(i) for i in range(1, 122)]
        result = remote.query("remotive", fetch=lambda url: remotive_feed(rows))
        self.assertEqual(result["returned_count"], 121)
        self.assertEqual(len(result["listings"]), 121)
        self.assertGreater(len(result["listings"][0]["description"]), 2500)
        self.assertEqual(result["listings"][0]["source_data"], rows[0])
        self.assertEqual(result["source_metadata"]["0-legal-notice"], "Synthetic terms")
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(result["reviewed_by_model"])

    def test_remotive_count_mismatch_duplicate_id_and_nonobject_fail(self):
        data = json.loads(remotive_feed())
        variants = [
            {**data, "job-count": 2},
            {**data, "job-count": True},
            {**data, "total-job-count": 0},
            {**data, "job-count": 2, "jobs": [remotive_row(), remotive_row()]},
            {**data, "jobs": [None]},
            {**data, "jobs": {}},
        ]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                remote.parse_snapshot("remotive", json.dumps(variant))

    def test_remoteok_legal_header_not_a_listing_zero_salary_is_preserved(self):
        metadata = {"legal": "Synthetic backlink terms", "last_updated": 1767270600}
        row = remoteok_row()
        result = remote.parse_snapshot("remoteok", json.dumps([metadata, row]))
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["source_metadata"], metadata)
        self.assertEqual(result["listings"][0]["source_data"]["salary_min"], 0)
        self.assertEqual(result["listings"][0]["attribution"]["source"], "Remote OK")
        self.assertIsNone(result["reported_total"])
        self.assertIsNone(result["has_more"])

    def test_remoteok_metadata_only_or_missing_legal_header_fails(self):
        for data in [[], [{"legal": "Synthetic terms"}], [remoteok_row()], {}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                remote.parse_snapshot("remoteok", json.dumps(data))

    def test_workingnomads_url_is_identity_and_exposed_subset_is_explicit(self):
        row = {
            "url": "https://www.workingnomads.com/jobs/synthetic-100",
            "title": "Synthetic opportunity",
            "description": "<p>Source description</p>",
            "location": "Egypt",
            "pub_date": "2026-01-01T12:30:00Z",
        }
        result = remote.parse_snapshot("workingnomads", json.dumps([row]))
        self.assertEqual(result["listings"][0]["id"], row["url"])
        self.assertEqual(result["listings"][0]["source_data"], row)
        self.assertTrue(any("subset" in limit for limit in result["limits"]))
        with self.assertRaises(ValueError):
            remote.parse_snapshot("workingnomads", json.dumps([row, row]))

    def test_rss_keeps_full_cdata_restrictions_dates_and_repeated_fields(self):
        result = remote.parse_snapshot("weworkremotely", RSS)
        listing = result["listings"][0]
        self.assertEqual(listing["id"], "synthetic-100")
        self.assertEqual(listing["description"], "<p>Full synthetic source description.</p>")
        self.assertEqual(listing["source_data"]["country"], "Egypt")
        self.assertEqual(listing["source_data"]["skills"], ["First", "Second"])
        self.assertEqual(listing["source_data"]["pubDate"], "Thu, 01 Jan 2026 12:30:00 +0000")
        self.assertEqual(
            listing["source_data"]["rss_attributes"]["guid"], [{"isPermaLink": "false"}]
        )

    def test_rss_entities_blocks_missing_descriptions_and_duplicate_items_fail(self):
        variants = [
            '<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + RSS,
            "<html>Verify you are human</html>",
            "<rss><channel><title>Example feed</title></channel></rss>",
            RSS.replace("<description>", "<other>").replace("</description>", "</other>"),
            RSS.replace(
                "</channel>", RSS[RSS.index("<item>") : RSS.index("</item>") + 7] + "</channel>"
            ),
        ]
        for body in variants:
            with self.subTest(body=body), self.assertRaises(ValueError):
                remote.parse_snapshot("weworkremotely", body)

    def test_rss_utf16_cannot_hide_document_entity_declarations(self):
        rss = RSS[RSS.index("<rss") :].replace(
            "<![CDATA[<p>Full synthetic source description.</p>]]>", "&example;"
        )
        body = (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<!DOCTYPE rss [<!ENTITY example "Synthetic content">]>' + rss
        ).encode("utf-16")
        with self.assertRaises(ValueError):
            remote.parse_snapshot("weworkremotely", body)

    def test_himalayas_official_cursor_and_salary_period_are_preserved(self):
        result = remote.query("himalayas_global", fetch=lambda url: himalayas_feed())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["next_cursor"], "c3ludGhldGlj")
        self.assertTrue(result["has_more"])
        row = result["listings"][0]["source_data"]
        self.assertEqual(row["salaryPeriod"], "hourly")
        self.assertEqual(row["currency"], "EUR")
        self.assertEqual(row["timezoneRestrictions"], ["UTC+02:00"])
        self.assertEqual(result["reported_total"], 21)
        terminal = remote.parse_snapshot("himalayas_global", himalayas_feed(None), "prior")
        self.assertFalse(terminal["has_more"])

    def test_himalayas_missing_stalled_invalid_cursor_and_bad_counts_fail(self):
        data = json.loads(himalayas_feed())
        variants = [
            {k: v for k, v in data.items() if k != "nextCursor"},
            {**data, "nextCursor": "prior"},
            {**data, "nextCursor": "https://evil.test"},
            {**data, "limit": 100},
            {**data, "totalCount": 0},
            {**data, "jobs": []},
        ]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                remote.parse_snapshot("himalayas_global", json.dumps(variant), "prior")

    def test_himalayas_empty_initial_feed_with_positive_total_is_source_limited(self):
        data = {**json.loads(himalayas_feed(None)), "jobs": []}
        result = remote.query("himalayas_global", fetch=lambda url: json.dumps(data))
        self.assertEqual(result["status"], "source_limited")
        self.assertNotIn("listings", result)
        self.assertFalse(result["coverage_complete"])

    def test_passive_application_url_is_retained_without_fetching_it(self):
        fetched = []

        def fetch(url):
            fetched.append(url)
            return himalayas_feed()

        result = remote.query("himalayas_global", fetch=fetch)
        self.assertEqual(fetched, [remote.endpoint("himalayas_global")])
        self.assertEqual(
            result["listings"][0]["source_data"]["applicationLink"],
            "https://example.invalid/apply?reference=synthetic",
        )

    def test_canonical_source_links_cannot_contain_credentials_or_token_queries(self):
        for url in [
            "https://evil.test/remote-jobs/synthetic-100",
            "https://u:p@remotive.com/remote-jobs/synthetic-100",
            "https://remotive.com/remote-jobs/synthetic-100?token=secret",
            "https://remotive.com/remote-jobs/synthetic-100\n",
            "https://remotive.com/account/profile",
        ]:
            row = {**remotive_row(), "url": url}
            result = remote.query("remotive", fetch=lambda requested: remotive_feed([row]))
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
            self.assertNotIn("secret", result["error"])

    def test_http_error_or_transport_error_never_becomes_empty_supply(self):
        for error in [
            HTTPError(remote.endpoint("remotive"), 403, "blocked", {}, None),
            TimeoutError("request includes token=secret"),
            RuntimeError("server says secret"),
        ]:
            with patch.object(remote, "read", side_effect=error):
                result = remote.query("remotive")
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
            self.assertNotIn("secret", result["error"])

    def test_json_duplicate_keys_nonfinite_and_html_block_pages_fail(self):
        for body in [
            '{"jobs":[],"job-count":0,"job-count":1}',
            '{"jobs":[],"job-count":NaN}',
            "<html>Access denied</html>",
        ]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                remote.parse_snapshot("remotive", body)

    def test_transport_requests_only_fixed_endpoint_without_credentials(self):
        url = remote.endpoint("remotive")
        response = FakeResponse(remotive_feed().encode(), url)
        with patch.object(remote, "build_opener") as factory:
            factory.return_value.open.return_value = response
            body = remote.read(url)
        self.assertGreater(len(body), 0)
        request = factory.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, url)
        self.assertEqual(factory.return_value.open.call_args.kwargs["timeout"], 35)
        self.assertFalse(any(k.lower() in {"cookie", "authorization"} for k in request.headers))

    def test_transport_declared_and_actual_size_limits_fail(self):
        url = remote.endpoint("remotive")
        responses = [
            FakeResponse(b"{}", url, headers={"Content-Length": str(remote.MAX_BYTES + 1)}),
            FakeResponse(b"{}", url, headers={"Content-Length": "not-a-number"}),
        ]
        with patch.object(remote, "MAX_BYTES", 10):
            responses.append(FakeResponse(b"x" * 11, url))
            for response in responses:
                with patch.object(remote, "build_opener") as factory:
                    factory.return_value.open.return_value = response
                    with self.assertRaises(ValueError):
                        remote.read(url)
            with self.assertRaises(ValueError):
                remote.parse_snapshot("remotive", "\u0627" * 6)

    def test_redirect_and_changed_response_url_are_refused(self):
        handler = remote.NoRedirects()
        request = type("RequestStub", (), {"full_url": remote.endpoint("remotive")})()
        with self.assertRaises(HTTPError):
            handler.redirect_request(request, None, 302, "redirect", {}, "https://evil.test/")
        with patch.object(remote, "build_opener") as factory:
            factory.return_value.open.return_value = FakeResponse(b"{}", "https://evil.test/")
            with self.assertRaises(ValueError):
                remote.read(remote.endpoint("remotive"))

    def test_capabilities_are_offline_and_always_unreviewed(self):
        with patch.object(remote, "read") as read:
            result = remote.capabilities()
        read.assert_not_called()
        self.assertEqual(len(result["sources"]), 5)
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(result["reviewed_by_model"])


if __name__ == "__main__":
    unittest.main()
