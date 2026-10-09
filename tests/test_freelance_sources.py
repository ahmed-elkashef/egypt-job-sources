import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from egypt_job_sources import freelance


def project(identifier=100001, **changes):
    value = {
        "id": identifier,
        "title": "Synthetic client project",
        "description": "Deliver a synthetic public work product.\nConfirm hours with the client.",
        "preview_description": "Truncated description is not the full brief.",
        "seo_url": "example-category/synthetic-project",
        "nonpublic": False,
        "deleted": False,
        "upgrades": {"nonpublic": False, "fulltime": True},
        "status": "active",
        "frontend_project_status": "open",
        "type": "hourly",
        "local": False,
        "budget": {"minimum": 8, "maximum": 12, "currency_id": 1, "secret": "DROP_ME"},
        "currency": {"code": "USD", "sign": "$", "name": "US Dollar", "exchange_rate": 1},
        "hourly_project_info": {
            "commitment": {"hours": 40, "interval": "week", "owner_email": "DROP_ME"},
            "duration_enum": "unspecified",
            "private_note": "DROP_ME",
        },
        "jobs": [
            {
                "id": 1,
                "name": "Synthetic skill",
                "category": {"id": 1, "name": "Example"},
                "private_note": "DROP_ME",
            }
        ],
        "location": {
            "country": {"code": "EG", "name": "Egypt", "flag_url": "DROP_ME"},
            "city": "Example city",
            "full_address": "DROP_ME",
            "latitude": 1,
            "timezone": {"timezone": "Africa/Cairo", "offset": 2},
        },
        "submitdate": 1767225600,
        "time_submitted": 1767225600,
        "time_updated": 1767312000,
        "owner_info": {"email": "DROP_ME"},
        "owner_id": 123,
        "bid_stats": {"bid_count": 99},
        "selected_bids": [{"description": "DROP_ME"}],
        "attachments": ["DROP_ME"],
        "nda_signatures": ["DROP_ME"],
        "enterprise_metadata_values": ["DROP_ME"],
    }
    value.update(changes)
    return value


def freelancer_page(projects=None, total=3):
    return {
        "status": "success",
        "result": {
            "projects": [project()] if projects is None else projects,
            "total_count": total,
            "users": {"123": {"private_email": "DROP_ME"}},
            "selected_bids": ["DROP_ME"],
        },
    }


def upwork_node(identifier="200001", **changes):
    value = {
        "id": identifier,
        "title": "Synthetic marketplace request",
        "description": "A synthetic project description with deliverables.",
        "ciphertext": "example_public_cipher",
        "amount": {"displayValue": "100.00", "currency": "USD", "secret": "DROP_ME"},
        "client": {"private_email": "DROP_ME"},
        "financialData": "DROP_ME",
    }
    value.update(changes)
    return value


def upwork_page(nodes=None, total=2, more=True, cursor="following-cursor"):
    return {
        "data": {
            "marketplaceJobPostingsSearch": {
                "totalCount": total,
                "edges": [
                    {"cursor": "edge-cursor", "node": node}
                    for node in ([upwork_node()] if nodes is None else nodes)
                ],
                "pageInfo": {"hasNextPage": more, "endCursor": cursor},
            }
        }
    }


class FreelancerTests(unittest.TestCase):
    def test_search_is_unfiltered_public_fixed_host_and_real_full_description(self):
        seen = []

        def transport(url, **kwargs):
            seen.append((url, kwargs))
            return freelancer_page()

        result = freelance.read_freelancer_page(limit=2, offset=0, transport=transport)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(urlsplit(seen[0][0]).netloc, "www.freelancer.com")
        self.assertEqual(seen[0][1], {})
        self.assertEqual(
            parse_qs(urlsplit(seen[0][0]).query),
            {
                "limit": ["2"],
                "offset": ["0"],
                "full_description": ["true"],
                "job_details": ["true"],
                "location_details": ["true"],
            },
        )
        self.assertEqual(result["listings"][0]["description"], project()["description"])
        self.assertEqual(result["pagination"]["next_offset"], 1)
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(result["reviewed_by_model"])

    def test_all_private_extras_are_dropped_without_losing_currency_hours_or_terms(self):
        result = freelance.parse_freelancer_page(freelancer_page(), limit=20, offset=0)
        serialized = json.dumps(result)
        self.assertNotIn("DROP_ME", serialized)
        self.assertNotIn("owner_id", serialized)
        self.assertNotIn("exchange_rate", serialized)
        self.assertNotIn("bid_stats", serialized)
        row = result["listings"][0]
        self.assertEqual(row["hourly_project_info"]["commitment"]["hours"], 40)
        self.assertEqual(row["budget"]["minimum"], 8)
        self.assertEqual(row["currency"]["code"], "USD")
        self.assertEqual(row["location"]["country"]["code"], "EG")
        self.assertIn("not_earned_income", row["budget_unit"])
        self.assertEqual(row["time_updated_raw"], 1767312000)
        self.assertTrue(row["full_time_upgrade_raw"])

    def test_nonpublic_deleted_rows_are_not_returned_and_pagination_counts_consumed_rows(self):
        projects = [project(100001, nonpublic=True), project(100002, deleted=True), project(100003)]
        result = freelance.parse_freelancer_page(freelancer_page(projects, 4), limit=3, offset=0)
        self.assertEqual([row["id"] for row in result["listings"]], ["100003"])
        self.assertEqual(len(result["excluded_rows"]), 2)
        self.assertEqual(result["pagination"]["next_offset"], 3)
        self.assertEqual(result["returned_count"], 3)

    def test_upgrades_nonpublic_flag_also_excludes_content(self):
        result = freelance.parse_freelancer_page(
            freelancer_page([project(upgrades={"nonpublic": True})], 1), limit=1, offset=0
        )
        self.assertEqual(result["listings"], [])
        self.assertEqual(len(result["excluded_rows"]), 1)

    def test_missing_full_description_is_a_named_gate_not_a_card_fallback(self):
        result = freelance.parse_freelancer_page(
            freelancer_page([project(description=None)], 1), limit=1, offset=0
        )
        row = result["listings"][0]
        self.assertIsNone(row["description"])
        self.assertEqual(row["gates"], ["missing_full_description"])
        self.assertNotIn("Truncated", json.dumps(row))

    def test_drifted_schema_duplicates_excess_and_empty_nonzero_are_failures(self):
        documents = [
            freelancer_page([project(), project()], 2),
            freelancer_page([project(nonpublic=None)], 1),
            freelancer_page([project(deleted=None)], 1),
            freelancer_page([project(status={"secret": "DROP_ME"})], 1),
            freelancer_page([], 1),
            freelancer_page([project()], 0),
            freelancer_page([project()], True),
            {"status": "error", "message": "secret"},
        ]
        for document in documents:
            with self.subTest(document=document), self.assertRaises(ValueError):
                freelance.parse_freelancer_page(document, limit=1, offset=0)

    def test_detail_verifies_identity_public_flags_and_whitelists(self):
        def transport(url):
            return {"status": "success", "result": project()}

        result = freelance.read_freelancer_detail("100001", transport=transport)
        self.assertEqual(result["listing"]["stable_id"], "freelancer:100001")
        self.assertNotIn("DROP_ME", json.dumps(result))
        for identifier in ["100002", "https://evil.test/100001", "100001?token=x", True]:
            self.assertEqual(
                freelance.read_freelancer_detail(identifier, transport=transport)["status"],
                "source_limited",
            )
        self.assertEqual(
            freelance.read_freelancer_detail(
                "100001",
                transport=lambda url: {"status": "success", "result": project(nonpublic=True)},
            )["status"],
            "source_limited",
        )

    def test_missing_budget_and_unknown_type_do_not_become_zero_or_fixed_price(self):
        row = freelance.parse_freelancer_page(
            freelancer_page([project(budget=None, type="new_source_type")], 1), limit=1, offset=0
        )["listings"][0]
        self.assertIsNone(row["budget"])
        self.assertIn("unit_unverified", row["budget_unit"])

    def test_invalid_limits_are_refused_before_network_and_errors_are_redacted(self):
        def forbidden(url):
            self.fail("Unexpected network")

        for limit, offset in [(0, 0), (101, 0), (True, 0), (1, -1), (1, 1_000_001)]:
            self.assertEqual(
                freelance.read_freelancer_page(limit, offset, transport=forbidden)["status"],
                "source_limited",
            )

        def fails(url):
            raise RuntimeError("private_request_token=DO_NOT_PRINT")

        result = freelance.read_freelancer_page(transport=fails)
        self.assertEqual(result["status"], "source_limited")
        self.assertNotIn("DO_NOT_PRINT", json.dumps(result))

    def test_transport_rejects_arbitrary_routes_credentials_queries_methods_and_redirects(self):
        urls = [
            "https://evil.test/api/projects/0.1/projects/active/",
            "http://www.freelancer.com/api/projects/0.1/projects/active/",
            "https://user:secret@www.freelancer.com/api/projects/0.1/projects/active/",
            "https://www.freelancer.com/api/projects/0.1/projects/active/?user_financial_details=true",
            "https://www.freelancer.com/api/users/0.1/self/",
            "https://www.freelancer.com/api/projects/0.1/projects/active/?full_description=true&job_details=true&location_details=true&limit=1&offset=0&limit=2",
        ]
        with patch.object(freelance, "build_opener") as opener:
            for url in urls:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    freelance.read_json(url)
            opener.assert_not_called()
        with self.assertRaises(ValueError):
            freelance.NoRedirects().redirect_request(
                None, None, 302, None, None, "https://evil.test"
            )

    def test_transport_refuses_duplicate_keys_and_nonfinite_json_values(self):
        url = (
            freelance.FREELANCER_API
            + "active/?limit=1&offset=0&full_description=true&job_details=true&location_details=true"
        )
        raw_documents = [
            b'{"status":"success","status":"error"}',
            b'{"result":{"projects":[{"nonpublic":true,"nonpublic":false}]}}',
            b'{"errors":[{"message":"blocked"}],"errors":[]}',
            b'{"result":{"budget":{"minimum":NaN}}}',
            b'{"result":{"budget":{"maximum":Infinity}}}',
            b'{"result":{"budget":{"maximum":-Infinity}}}',
        ]
        with patch.object(freelance, "build_opener") as opener:
            response = MagicMock()
            response.__enter__.return_value = response
            response.geturl.return_value = url
            response.headers.get_content_type.return_value = "application/json"
            opener.return_value.open.return_value = response
            for raw in raw_documents:
                response.read.return_value = raw
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    freelance.read_json(url)

    def test_injected_nonfinite_budget_also_fails_validation(self):
        with self.assertRaises(ValueError):
            freelance.parse_freelancer_page(
                freelancer_page([project(budget={"minimum": float("nan")})], 1),
                limit=1,
                offset=0,
            )


class UpworkTests(unittest.TestCase):
    def test_missing_token_requires_approval_and_sends_no_request(self):
        def forbidden(*args, **kwargs):
            self.fail("Unexpected network")

        with patch.dict("os.environ", {}, clear=True):
            for result in [
                freelance.read_upwork_page(transport=forbidden),
                freelance.read_upwork_detail("200001", transport=forbidden),
            ]:
                self.assertEqual(result["status"], "source_limited")
                self.assertTrue(result["api_approval_required"])
                self.assertIn("API access", result["error"])
                self.assertNotIn("reported_total", result)

    def test_fixed_graphql_query_uses_verified_operation_and_returned_cursor(self):
        seen = []

        def transport(url, **kwargs):
            seen.append((url, kwargs))
            return upwork_page()

        result = freelance.read_upwork_page(
            2, "current-cursor", transport=transport, access_token="SYNTHETIC_TOKEN"
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(seen[0][0], freelance.UPWORK_API)
        self.assertEqual(seen[0][1]["method"], "POST")
        self.assertEqual(seen[0][1]["body"]["query"], freelance.UPWORK_SEARCH_QUERY)
        self.assertEqual(
            seen[0][1]["body"]["variables"],
            {"filter": {"pagination_eq": {"after": "current-cursor", "first": 2}}},
        )
        self.assertEqual(result["pagination"]["next_cursor"], "following-cursor")
        self.assertNotIn("SYNTHETIC_TOKEN", json.dumps(result))
        self.assertNotIn("DROP_ME", json.dumps(result))
        self.assertIsNone(result["listings"][0]["url"])
        self.assertIn("unit_and_hourly_terms_unverified", result["listings"][0]["budget_unit"])

    def test_advancing_cursor_count_duplicates_and_graphql_errors_are_checked(self):
        documents = [
            upwork_page(cursor="0"),
            upwork_page(cursor=None),
            upwork_page(cursor="bad\ncursor"),
            upwork_page(nodes=[], more=True),
            upwork_page(nodes=[upwork_node(), upwork_node()]),
            upwork_page(total=True),
            upwork_page(total=0),
            upwork_page(nodes=[], total=2, more=False, cursor=None),
            {
                "data": {"marketplaceJobPostingsSearch": None},
                "errors": [{"message": "TOKEN_DO_NOT_PRINT"}],
            },
        ]
        for document in documents:
            with self.subTest(document=document), self.assertRaises(ValueError):
                freelance.parse_upwork_page(document, limit=2)

    def test_graphql_and_http_errors_never_return_token_or_raw_messages(self):
        result = freelance.read_upwork_page(
            access_token="SYNTHETIC_TOKEN",
            transport=lambda *args, **kwargs: {"errors": [{"message": "SYNTHETIC_TOKEN"}]},
        )
        self.assertEqual(result["status"], "source_limited")
        self.assertNotIn("SYNTHETIC_TOKEN", json.dumps(result))

        def fails(*args, **kwargs):
            raise RuntimeError("Authorization Bearer SYNTHETIC_TOKEN")

        self.assertNotIn(
            "SYNTHETIC_TOKEN",
            json.dumps(freelance.read_upwork_page(access_token="SYNTHETIC_TOKEN", transport=fails)),
        )

    def test_detail_uses_only_fixed_read_content_operation_and_matches_id(self):
        seen = []

        def transport(url, **kwargs):
            seen.append(kwargs)
            return {
                "data": {
                    "marketplaceJobPostingsContents": [
                        upwork_node(publishedDateTime="2026-01-01T00:00:00Z")
                    ]
                }
            }

        result = freelance.read_upwork_detail(
            "200001", access_token="SYNTHETIC_TOKEN", transport=transport
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(seen[0]["body"]["query"], freelance.UPWORK_CONTENT_QUERY)
        self.assertEqual(seen[0]["body"]["variables"], {"ids": ["200001"]})
        self.assertEqual(result["listing"]["published_at_raw"], "2026-01-01T00:00:00Z")
        self.assertEqual(
            freelance.read_upwork_detail(
                "200002", access_token="SYNTHETIC_TOKEN", transport=transport
            )["status"],
            "source_limited",
        )

    def test_missing_full_description_stays_explicit(self):
        row = freelance.parse_upwork_page(
            upwork_page(nodes=[upwork_node(description=None)]), limit=2
        )["listings"][0]
        self.assertEqual(row["gates"], ["missing_full_description"])
        self.assertIsNone(row["description"])

    def test_arbitrary_graphql_mutations_and_tokens_with_newlines_never_send_http(self):
        with patch.object(freelance, "build_opener") as opener:
            for query in [
                "mutation { sendMessage }",
                "query { me { email } }",
                "{ __schema { types { name } } }",
            ]:
                with self.subTest(query=query), self.assertRaises(ValueError):
                    freelance.read_json(
                        freelance.UPWORK_API,
                        method="POST",
                        body={"query": query, "variables": {}},
                        headers={"Authorization": "Bearer SYNTHETIC_TOKEN"},
                    )
            opener.assert_not_called()
        result = freelance.read_upwork_page(
            access_token="TOKEN\nINJECT",
            transport=lambda *args, **kwargs: self.fail("Unexpected HTTP"),
        )
        self.assertEqual(result["status"], "source_limited")
        self.assertNotIn("INJECT", json.dumps(result))

    def test_terminal_source_page_and_valid_zero_are_not_market_completion(self):
        result = freelance.parse_upwork_page(
            upwork_page(nodes=[], total=0, more=False, cursor=None), limit=2
        )
        self.assertEqual(result["listings"], [])
        self.assertIsNone(result["pagination"]["next_cursor"])
        self.assertFalse(result["coverage_complete"])

    def test_fixed_queries_also_require_exact_allowlisted_variables_before_http(self):
        invalid = [
            (freelance.UPWORK_SEARCH_QUERY, {}),
            (
                freelance.UPWORK_SEARCH_QUERY,
                {
                    "filter": {
                        "searchExpression_eq": "keyword",
                        "pagination_eq": {"after": "0", "first": 1},
                    }
                },
            ),
            (
                freelance.UPWORK_SEARCH_QUERY,
                {"filter": {"pagination_eq": {"after": "0", "first": 101}}},
            ),
            (
                freelance.UPWORK_SEARCH_QUERY,
                {"filter": {"pagination_eq": {"after": "bad\ncursor", "first": 1}}},
            ),
            (
                freelance.UPWORK_SEARCH_QUERY,
                {"filter": {"pagination_eq": {"after": None, "first": 1}}},
            ),
            (freelance.UPWORK_CONTENT_QUERY, {"ids": ["200001", "200002"]}),
            (freelance.UPWORK_CONTENT_QUERY, {"ids": ["https://evil.test"]}),
            (freelance.UPWORK_CONTENT_QUERY, {"ids": ["200001"], "other": "private"}),
        ]
        with patch.object(freelance, "build_opener") as opener:
            for query, variables in invalid:
                with self.subTest(variables=variables), self.assertRaises(ValueError):
                    freelance.read_json(
                        freelance.UPWORK_API,
                        method="POST",
                        body={"query": query, "variables": variables},
                        headers={"Authorization": "Bearer SYNTHETIC_TOKEN"},
                    )
            opener.assert_not_called()


class CapabilityCliTests(unittest.TestCase):
    def test_capabilities_are_account_free_and_explain_approval_gate(self):
        result = freelance.source_capabilities("upwork")
        self.assertIn("USD 25,000", json.dumps(result))
        self.assertEqual(result["required_permission"], "Read marketplace Job Postings")
        with redirect_stdout(io.StringIO()) as output:
            code = freelance.main(["--capabilities"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(output.getvalue())["sources"]), 2)

    def test_cli_rejects_cross_source_pagination(self):
        for argv in [
            ["--source", "upwork", "--offset", "0"],
            ["--source", "freelancer", "--cursor", "x"],
            ["--source", "freelancer", "--project-id", "100001", "--offset", "0"],
        ]:
            with (
                self.subTest(argv=argv),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                freelance.main(argv)


if __name__ == "__main__":
    unittest.main()
