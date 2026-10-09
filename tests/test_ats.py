"""Official ATS semantics and anonymous URL boundaries with synthetic data only."""

import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

from egypt_job_sources import ats


def greenhouse_job(identifier=100, *, content=None):
    return {
        "id": identifier,
        "internal_job_id": identifier + 1000,
        "title": "Synthetic opportunity",
        "content": content
        if content is not None
        else "<p>" + "Complete work description. " * 150 + "</p>",
        "absolute_url": f"https://job-boards.greenhouse.io/example/jobs/{identifier}",
        "location": {"name": "Cairo, Egypt"},
        "offices": [{"id": 10, "name": "Example office", "location": "Egypt"}],
        "updated_at": "2026-01-01T12:00:00Z",
    }


def greenhouse_board(rows=None):
    rows = [greenhouse_job()] if rows is None else rows
    return {"jobs": rows, "meta": {"total": len(rows)}}


def lever_job(identifier="synthetic-100", *, region="global"):
    host = "jobs.eu.lever.co" if region == "eu" else "jobs.lever.co"
    return {
        "id": identifier,
        "text": "Synthetic opportunity",
        "categories": {
            "location": "Cairo",
            "allLocations": ["Cairo", "Giza"],
            "commitment": "Contract",
        },
        "country": "EG",
        "workplaceType": "remote",
        "description": "<p>" + "Complete source body. " * 180 + "</p>",
        "descriptionPlain": "Complete source body. " * 180,
        "lists": [
            {"text": "Requirements", "content": "<li>Specific source requirement.</li>"},
            {"text": "Benefits", "content": "<li>Specific source benefit.</li>"},
        ],
        "additional": "<p>Closing terms.</p>",
        "additionalPlain": "Closing terms.",
        "salaryDescription": "<p>Pay conditions.</p>",
        "salaryRange": {"currency": "EUR", "interval": "hour", "min": 20, "max": 25},
        "hostedUrl": f"https://{host}/example/{identifier}",
        "createdAt": 1767272400000,
    }


def ashby_job(identifier="synthetic-100", *, listed=True):
    return {
        "title": "Synthetic opportunity",
        "jobUrl": f"https://jobs.ashbyhq.com/example/{identifier}",
        "descriptionHtml": "<p>" + "Complete returned source text. " * 130 + "</p>",
        "descriptionPlain": "Complete returned source text. " * 130,
        "isListed": listed,
        "isRemote": True,
        "workplaceType": "Remote",
        "employmentType": "Contract",
        "location": "Worldwide",
        "secondaryLocations": [{"location": "Cairo", "address": {"addressCountry": "EG"}}],
        "publishedAt": "2026-01-01T12:00:00+00:00",
        "compensation": {
            "summaryComponents": [
                {"currencyCode": "GBP", "interval": "1 HOUR", "minValue": 10, "maxValue": 15}
            ]
        },
    }


def ashby_board(rows=None):
    return {"apiVersion": "1", "jobs": [ashby_job()] if rows is None else rows}


def encoded(document):
    return json.dumps(document).encode()


class FakeResponse(io.BytesIO):
    def __init__(self, body, url, *, status=200, headers=None):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = {"Content-Type": "application/json"} if headers is None else headers

    def geturl(self):
        return self.url


class ATSTests(unittest.TestCase):
    def test_only_fixed_public_endpoints_and_documented_parameters(self):
        endpoints = [
            ats.endpoint("greenhouse", "example"),
            ats.endpoint("greenhouse", "example", job_id=100),
            ats.endpoint("lever", "example"),
            ats.endpoint("lever", "example", region="eu", skip=100, limit=20),
            ats.endpoint("lever", "example", region="eu", job_id="synthetic-100"),
            ats.endpoint("ashby", "example"),
        ]
        for endpoint in endpoints:
            self.assertEqual(ats.validate_endpoint(endpoint), endpoint)
        self.assertIn("boards-api.greenhouse.io", endpoints[0])
        self.assertIn("content=true", endpoints[0])
        self.assertIn("pay_transparency=true", endpoints[1])
        self.assertIn("includeCompensation=true", endpoints[-1])

    def test_arbitrary_account_filtered_and_credential_urls_fail_before_network(self):
        safe = ats.endpoint("lever", "example")
        invalid = [
            safe.replace("https:", "http:"),
            safe.replace("api.lever.co", "evil.invalid"),
            safe.replace("api.lever.co", "user:password@api.lever.co"),
            safe.replace("api.lever.co", "api.lever.co:443"),
            safe + "#fragment",
            safe + "&token=synthetic-secret",
            safe + "&team=Engineering",
            safe + "&limit=100",
            safe.replace("mode=json", "mode=html"),
            safe.replace("/example?", "/example/../account?"),
            "https://api.lever.co/v0/account",
            "https://api.ashbyhq.com/application.list",
            "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true&questions=true",
        ]
        with patch.object(ats, "build_opener") as opener:
            for url in invalid:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    ats.read(url)
            opener.assert_not_called()

    def test_unsafe_tokens_and_unsupported_flags_do_not_invoke_transport(self):
        forbidden = Mock(side_effect=AssertionError("Must not read"))
        for source, board, kwargs in [
            ("greenhouse", "../example", {}),
            ("greenhouse", "https://example.invalid", {}),
            ("greenhouse", "example", {"skip": 0}),
            ("greenhouse", "example", {"region": "eu"}),
            ("ashby", "example", {"limit": 20}),
            ("lever", "example", {"skip": -1}),
            ("lever", "example", {"limit": True}),
            ("lever", "example", {"limit": 101}),
            ("lever", "example", {"region": "other"}),
        ]:
            result = ats.read_board(source, board, transport=forbidden, **kwargs)
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
        result = ats.read_detail("ashby", "example", "synthetic-100", transport=forbidden)
        self.assertEqual(result["status"], "source_limited")
        forbidden.assert_not_called()

    def test_greenhouse_complete_text_stable_post_and_internal_job_ids_no_100_cap(self):
        rows = [greenhouse_job(index) for index in range(100, 205)]
        result = ats.parse_board(greenhouse_board(rows), "greenhouse", "example")
        self.assertEqual(len(result["listings"]), 105)
        self.assertEqual(result["reported_total"], 105)
        self.assertTrue(result["board_snapshot_complete"])
        self.assertFalse(result["coverage_complete"])
        listing = result["listings"][0]
        self.assertGreater(len(listing["description"]), 2500)
        self.assertEqual(listing["source_id"], "100")
        self.assertEqual(listing["internal_job_id"], 1100)
        self.assertEqual(listing["stable_id"], "greenhouse:global:example:100")
        self.assertEqual(listing["source_data"]["content"], rows[0]["content"])

    def test_greenhouse_entity_encoded_html_and_prospect_identity_are_preserved(self):
        row = greenhouse_job(
            content="&amp;lt;p&amp;gt;Arabic العربية &amp;amp; exact terms.&amp;lt;/p&amp;gt;"
        )
        row["internal_job_id"] = None
        result = ats.parse_board(greenhouse_board([row]), "greenhouse", "example")
        listing = result["listings"][0]
        self.assertIn("العربية & exact terms.", listing["description"])
        self.assertEqual(listing["posting_kind"], "prospect_post")
        self.assertEqual(listing["description_html"], row["content"])

    def test_greenhouse_missing_or_contradictory_total_is_failure_not_empty(self):
        documents = [
            {"jobs": []},
            {"jobs": [], "meta": {"total": 1}},
            {"jobs": [], "meta": {"total": True}},
            {"jobs": [], "meta": {"total": -1}},
            {"jobs": [], "meta": {"total": 0}, "error": "synthetic-secret"},
        ]
        for document in documents:
            result = ats.read_board("greenhouse", "example", transport=lambda _: encoded(document))
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
            self.assertNotIn("reported_total", result)
            self.assertNotIn("synthetic-secret", json.dumps(result))

    def test_lever_preserves_body_requirements_benefits_closing_and_salary_terms(self):
        row = lever_job()
        result = ats.parse_board([row], "lever", "example")
        listing = result["listings"][0]
        self.assertGreater(len(listing["description"]), 2500)
        for component in (
            "Specific source requirement.",
            "Specific source benefit.",
            "Closing terms.",
            "Pay conditions.",
        ):
            self.assertIn(component, listing["description"])
        self.assertEqual(listing["source_data"]["descriptionPlain"], row["descriptionPlain"])
        self.assertEqual(listing["compensation_raw"]["interval"], "hour")
        self.assertEqual(listing["compensation_raw"]["currency"], "EUR")
        self.assertEqual(listing["employment_type_raw"], "Contract")
        self.assertEqual(listing["location_raw"]["allLocations"], ["Cairo", "Giza"])
        self.assertIn("not_verified_original_publication", listing["date_basis"])

    def test_lever_partial_plain_components_do_not_drop_html_body(self):
        row = lever_job()
        del row["descriptionPlain"]
        del row["description"]
        row["openingPlain"] = "Opening plain text."
        row["descriptionBody"] = "<p>Body only available as HTML.</p>"
        listing = ats.parse_board([row], "lever", "example")["listings"][0]
        self.assertIn("Opening plain text.", listing["description"])
        self.assertIn("Body only available as HTML.", listing["description"])

    def test_lever_short_page_continues_actual_offset_then_empty_is_explicit_terminal(self):
        first = ats.parse_board([lever_job()], "lever", "example", skip=0, limit=100)
        self.assertEqual(first["pagination"]["next_skip"], 1)
        self.assertIsNone(first["pagination"]["has_more"])
        self.assertFalse(first["board_snapshot_complete"])
        self.assertNotIn("reported_total", first)
        end = ats.parse_board([], "lever", "example", skip=1, limit=100)
        self.assertTrue(end["pagination"]["page_exhaustion_observed"])
        self.assertFalse(end["pagination"]["has_more"])
        self.assertFalse(end["coverage_complete"])
        self.assertFalse(end["board_snapshot_complete"])

    def test_lever_commitments_repeat_exact_encoded_labels_without_arbitrary_query(self):
        labels = ["Observed part time & remote", "التزام تجريبي"]
        url = ats.endpoint("lever", "example", skip=17, limit=50, commitments=labels)
        self.assertIn("skip=17&limit=50&commitment=Observed+part+time+%26+remote&commitment=", url)
        self.assertEqual(ats.validate_endpoint(url), url)
        self.assertEqual(ats._commitments(labels), labels)
        with self.assertRaises(ValueError):
            ats.validate_endpoint(url + "&country=EG")
        with self.assertRaises(ValueError):
            ats.endpoint("lever", "example", job_id="synthetic-100", commitments=labels)

    def test_invalid_or_cross_source_commitments_fail_before_transport(self):
        forbidden = Mock(side_effect=AssertionError("Must not read"))
        invalid = [
            [],
            "Contract",
            ("Contract",),
            [None],
            [True],
            [""],
            [" "],
            [" Contract"],
            ["Contract\n"],
            ["Contract", "Contract"],
            ["x" * 201],
            [f"Label {index}" for index in range(21)],
        ]
        for labels in invalid:
            result = ats.read_board("lever", "example", commitments=labels, transport=forbidden)
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
        for source in ("greenhouse", "ashby"):
            result = ats.read_board(
                source, "example", commitments=["Contract"], transport=forbidden
            )
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
        forbidden.assert_not_called()

    def test_filtered_lever_preserves_components_filters_counts_and_exact_continuation(self):
        rows = [lever_job("synthetic-100"), lever_job("synthetic-101")]
        rows[0]["categories"]["commitment"] = "Observed A"
        rows[1]["categories"]["commitment"] = "Observed B"
        labels = ["Observed A", "Observed B"]
        result = ats.parse_board(rows, "lever", "example", skip=7, limit=50, commitments=labels)
        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["pagination"]["next_skip"], 9)
        self.assertEqual(result["source_filters"]["commitments"], labels)
        self.assertEqual(result["source_filters"]["matching"], "case_sensitive_OR")
        self.assertEqual(result["source_filter_verification"]["commitment_matches"], 2)
        self.assertFalse(result["board_snapshot_complete"])
        self.assertFalse(result["coverage_complete"])
        self.assertNotIn("reported_total", result)
        for listing, row in zip(result["listings"], rows):
            self.assertEqual(listing["source_data"]["descriptionPlain"], row["descriptionPlain"])
            for text in ("Specific source requirement.", "Closing terms.", "Pay conditions."):
                self.assertIn(text, listing["description"])
        terminal = ats.parse_board([], "lever", "example", skip=9, limit=50, commitments=labels)
        self.assertEqual(terminal["returned_count"], 0)
        self.assertIsNone(terminal["pagination"]["next_skip"])
        self.assertTrue(terminal["pagination"]["page_exhaustion_observed"])
        self.assertEqual(terminal["source_filters"], result["source_filters"])
        self.assertFalse(terminal["board_snapshot_complete"])

    def test_missing_or_mixed_commitment_metadata_remains_undetermined_without_row_drops(self):
        rows = [lever_job("synthetic-100"), lever_job("synthetic-101")]
        rows[0]["categories"].pop("commitment")
        rows[1]["categories"]["commitment"] = ["Observed A", "other"]
        result = ats.parse_board(rows, "lever", "example", commitments=["Observed A"])
        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["listed_count"], 2)
        self.assertEqual(result["pagination"]["next_skip"], 2)
        self.assertEqual(result["source_filter_verification"]["commitment_undetermined"], 2)
        self.assertEqual(result["listings"][1]["employment_type_raw"], ["Observed A", "other"])
        broad = ats.parse_board(rows, "lever", "example")
        self.assertEqual(broad["listed_count"], 2)
        self.assertNotIn("source_filters", broad)

    def test_known_source_commitment_contradiction_is_limitation_not_empty_or_partial(self):
        result = ats.read_board(
            "lever", "example", commitments=["contract"], transport=lambda _: encoded([lever_job()])
        )
        self.assertEqual(result["status"], "source_limited")
        self.assertEqual(result["error_code"], "native_commitment_filter_mismatch")
        self.assertTrue(result["filter_verification_failed"])
        self.assertNotIn("listings", result)
        self.assertNotIn("returned_count", result)

    def test_cli_repeats_commitments_only_for_board_search_without_network_on_rejection(self):
        with patch.object(ats, "read_board", return_value={"status": "ok"}) as reader:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    ats.main(
                        [
                            "--source",
                            "lever",
                            "--board",
                            "example",
                            "--skip",
                            "9",
                            "--limit",
                            "50",
                            "--commitment",
                            "Observed A",
                            "--commitment",
                            "Observed B",
                        ]
                    ),
                    0,
                )
            self.assertEqual(reader.call_args.kwargs["commitments"], ["Observed A", "Observed B"])
            self.assertEqual(reader.call_args.kwargs["skip"], 9)
        with patch.object(ats, "build_opener") as opener:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                ats.main(["--capabilities", "--commitment", "Observed A"])
            self.assertEqual(error.exception.code, 2)
            for source, extra in [
                ("greenhouse", []),
                ("ashby", []),
                ("lever", ["--job-id", "synthetic-100"]),
            ]:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(
                        ats.main(
                            [
                                "--source",
                                source,
                                "--board",
                                "example",
                                "--commitment",
                                "Observed A",
                                *extra,
                            ]
                        ),
                        2,
                    )
                self.assertEqual(json.loads(output.getvalue())["status"], "source_limited")
            opener.assert_not_called()

    def test_lever_more_than_100_across_pages_is_not_truncated_or_duplicate(self):
        first = [lever_job(f"synthetic-{index}") for index in range(100)]
        second = [lever_job(f"synthetic-{index}") for index in range(100, 105)]
        one = ats.parse_board(first, "lever", "example", limit=100)
        two = ats.parse_board(
            second, "lever", "example", skip=one["pagination"]["next_skip"], limit=100
        )
        identities = [item["stable_id"] for result in (one, two) for item in result["listings"]]
        self.assertEqual(len(identities), 105)
        self.assertEqual(len(set(identities)), 105)
        self.assertEqual(two["pagination"]["next_skip"], 105)

    def test_region_and_detail_identity_checks(self):
        row = lever_job(region="eu")
        result = ats.parse_detail(row, "lever", "example", row["id"], region="eu")
        self.assertEqual(result["listing"]["stable_id"], "lever:eu:example:synthetic-100")
        for source, row, requested, kwargs in [
            ("greenhouse", greenhouse_job(), 101, {}),
            ("lever", row, "synthetic-other", {"region": "eu"}),
            ("lever", row, "synthetic-100", {}),
        ]:
            result = ats.read_detail(
                source, "example", requested, transport=lambda _: encoded(row), **kwargs
            )
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listing", result)

    def test_ashby_source_url_identity_last_publication_units_and_secondary_locations(self):
        row = ashby_job()
        result = ats.parse_board(ashby_board([row]), "ashby", "example")
        listing = result["listings"][0]
        self.assertGreater(len(listing["description"]), 2500)
        self.assertIsNone(listing["source_id"])
        self.assertEqual(len(listing["id"]), 64)
        self.assertEqual(listing["description"], row["descriptionPlain"])
        self.assertEqual(listing["compensation_raw"]["summaryComponents"][0]["interval"], "1 HOUR")
        self.assertEqual(listing["location_raw"]["secondaryLocations"], row["secondaryLocations"])
        self.assertIn("last_published", listing["date_basis"])
        self.assertNotIn("reported_total", result)
        self.assertTrue(result["board_snapshot_complete"])
        self.assertIsNone(result["pagination"]["has_more"])

    def test_ashby_unlisted_content_is_excluded_and_counted_without_disclosure(self):
        unlisted = ashby_job("synthetic-unlisted", listed=False)
        unlisted["descriptionPlain"] = "SYNTHETIC DIRECT-LINK-ONLY CONTENT"
        result = ats.parse_board(ashby_board([ashby_job(), unlisted]), "ashby", "example")
        self.assertEqual(
            (result["returned_count"], result["listed_count"], result["excluded_count"]), (2, 1, 1)
        )
        self.assertNotIn("SYNTHETIC DIRECT-LINK-ONLY CONTENT", json.dumps(result))
        for document in (
            {"jobs": []},
            {"apiVersion": "2", "jobs": []},
            {"apiVersion": "1", "jobs": [{**ashby_job(), "isListed": None}]},
        ):
            result = ats.read_board("ashby", "example", transport=lambda _: encoded(document))
            self.assertEqual(result["status"], "source_limited")

    def test_missing_full_text_retains_card_with_gate_instead_of_omitting_it(self):
        row = greenhouse_job(content="")
        result = ats.parse_board(greenhouse_board([row]), "greenhouse", "example")
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(len(result["listings"]), 1)
        self.assertIsNone(result["listings"][0]["description"])
        self.assertEqual(result["listings"][0]["gates"], ["missing_full_description"])

    def test_ashby_unlisted_urls_obey_the_same_board_identity_boundary(self):
        for url in (
            "https://jobs.ashbyhq.com/other/synthetic-100",
            "https://jobs.ashbyhq.com//example/synthetic-100",
            "https://jobs.ashbyhq.com/example/account/profile",
            "https://jobs.ashbyhq.com/example/synthetic-100?token=synthetic-secret",
        ):
            document = ashby_board([{**ashby_job(listed=False), "jobUrl": url}])
            result = ats.read_board("ashby", "example", transport=lambda _: encoded(document))
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("returned_count", result)
            self.assertNotIn("excluded_items", result)
            self.assertNotIn("synthetic-secret", json.dumps(result))

    def test_duplicate_ids_or_wrong_board_urls_are_not_silently_deduped(self):
        for source, document in [
            ("greenhouse", greenhouse_board([greenhouse_job(), greenhouse_job()])),
            ("lever", [lever_job(), lever_job()]),
            ("ashby", ashby_board([ashby_job(), ashby_job()])),
            (
                "ashby",
                ashby_board(
                    [{**ashby_job(), "jobUrl": "https://jobs.ashbyhq.com/other/synthetic-100"}]
                ),
            ),
        ]:
            result = ats.read_board(source, "example", transport=lambda _: encoded(document))
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)

    def test_transport_failure_and_bad_json_never_become_empty_supply_or_raw_errors(self):
        for raw in (
            b"not JSON",
            b'{"jobs":[],"jobs":[],"meta":{"total":0}}',
            b'{"jobs":[],"meta":{"total":NaN}}',
        ):
            result = ats.read_board("greenhouse", "example", transport=lambda _: raw)
            self.assertEqual(result["status"], "source_limited")
            self.assertNotIn("listings", result)
        result = ats.read_board(
            "lever", "example", transport=Mock(side_effect=RuntimeError("synthetic-secret"))
        )
        self.assertNotIn("synthetic-secret", json.dumps(result))
        self.assertNotIn("reported_total", result)

    def test_http_anonymous_bounded_status_content_and_redirect_checks(self):
        url = ats.endpoint("greenhouse", "example")
        body = encoded(greenhouse_board())
        response = FakeResponse(
            body,
            url,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(body)),
            },
        )
        opener = Mock()
        opener.open.return_value = response
        with patch.object(ats, "build_opener", return_value=opener):
            self.assertEqual(ats.read(url), body)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertNotIn("Authorization", request.headers)
        self.assertNotIn("Cookie", request.headers)
        bad = [
            FakeResponse(body, url, status=403),
            FakeResponse(body, url + "/redirect"),
            FakeResponse(body, url, headers={"Content-Type": "text/html"}),
            FakeResponse(
                body, url, headers={"Content-Type": "application/json", "Content-Encoding": "gzip"}
            ),
            FakeResponse(
                body,
                url,
                headers={"Content-Type": "application/json", "Content-Length": str(len(body) + 1)},
            ),
            FakeResponse(
                body,
                url,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(ats.MAX_BYTES + 1),
                },
            ),
        ]
        for response in bad:
            opener.open.return_value = response
            with (
                patch.object(ats, "build_opener", return_value=opener),
                self.assertRaises(ValueError),
            ):
                ats.read(url)
        with self.assertRaises(ValueError):
            ats.NoRedirects().redirect_request(
                None, None, 302, "redirect", {}, "https://evil.invalid"
            )

    def test_successful_empty_board_is_distinct_from_source_failure(self):
        for source, document in [
            ("greenhouse", greenhouse_board([])),
            ("ashby", ashby_board([])),
            ("lever", []),
        ]:
            result = ats.read_board(source, "example", transport=lambda _: encoded(document))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["listings"], [])
            self.assertEqual(result["returned_count"], 0)
            self.assertFalse(result["coverage_complete"])

    def test_source_data_whitelist_excludes_unrelated_account_and_applicant_fields(self):
        row = greenhouse_job()
        row.update(
            candidateEmail="synthetic-private@example.invalid", access_token="synthetic-secret"
        )
        listing = ats.parse_board(greenhouse_board([row]), "greenhouse", "example")["listings"][0]
        self.assertNotIn("candidateEmail", listing["source_data"])
        self.assertNotIn("access_token", listing["source_data"])

    def test_offline_capabilities_and_invalid_cli_combinations_do_not_read_network(self):
        with (
            patch.object(ats, "build_opener") as opener,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(ats.main(["--capabilities"]), 0)
            contract = json.loads(output.getvalue())
            self.assertEqual(contract["status"], "ok")
            self.assertEqual(set(contract["sources"]), set(ats.SOURCES))
            self.assertTrue(all(c["status"] == "ok" for c in contract["sources"].values()))
            output.seek(0)
            output.truncate(0)
            self.assertEqual(
                ats.main(["--source", "ashby", "--board", "example", "--job-id", "synthetic-100"]),
                2,
            )
            self.assertEqual(json.loads(output.getvalue())["status"], "source_limited")
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
