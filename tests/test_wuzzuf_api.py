import copy
import unittest
import urllib.error
from unittest.mock import patch

from egypt_job_sources import wuzzuf as w

ID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_ID = "123e4567-e89b-12d3-a456-426614174001"
URL = "https://wuzzuf.net/jobs/p/abcdefghijkl-example-egypt"


def resource():
    return {
        "id": ID,
        "type": "job",
        "attributes": {
            "title": "Example",
            "uri": "jobs/p/abcdefghijkl-example-egypt",
            "description": "<p>Complete duties.</p><ul><li>One deliverable.</li></ul>",
            "requirements": "<ul><li><p></p></li></ul><p></p>",
            "location": {"country": {"code": "EG", "name": "Egypt", "id": 56}},
            "workTypes": [{"name": "part_time"}, {"name": "full_time"}],
            "postedAt": "10/07/2026 14:14:56",
            "expireAt": "12/06/2026 14:14:56",
            "insights": {"applicant_detail": "must not be returned"},
            "contactEmail": "must not be returned",
        },
        "relationships": {"company": {"data": {"id": "123", "type": "company"}}},
    }


def search(total=1):
    return {"meta": {"totalResultsCount": total}, "data": [{"id": ID, "type": "talentSearch"}]}


class WuzzufApiTests(unittest.TestCase):
    def test_native_country_and_employment_filters_without_keywords(self):
        body = w.search_body(2, "freelance")
        self.assertEqual(body["startIndex"], 15)
        self.assertEqual(body["pageSize"], 15)
        self.assertEqual(body["query"], "")
        self.assertEqual(
            body["searchFilters"], {"country": ["Egypt"], "job_types": ["freelance_project"]}
        )
        self.assertIn("start=1", w.public_page_url(2, "freelance"))
        self.assertEqual(w.search_body(1)["searchFilters"], {"country": ["Egypt"]})
        for page in [True, 0, 10001, "2"]:
            with self.subTest(page=page), self.assertRaises(ValueError):
                w.search_body(page)

    def test_missing_and_extra_hydration_preserves_every_search_id(self):
        result = w.parse_page(search(), {"data": []}, 1, "part_time")
        self.assertEqual(result["status"], "source_limited")
        self.assertEqual(result["search_ids"], [ID])
        self.assertEqual(result["listings"][0]["api_id"], ID)
        self.assertEqual(result["missing_detail_ids"], [ID])
        other = resource()
        other["id"] = OTHER_ID
        result = w.parse_page(search(), {"data": [resource(), other]}, 1)
        self.assertEqual(result["unexpected_detail_ids"], [OTHER_ID])
        self.assertEqual(result["status"], "source_limited")

    def test_authoritative_sections_empty_requirements_and_mixed_types_survive(self):
        result = w.parse_page(search(), {"data": [resource()]}, 1, "part_time")
        self.assertEqual(result["status"], "ok")
        row = result["listings"][0]
        self.assertEqual(row["id"], "abcdefghijkl")
        self.assertEqual(row["api_id"], ID)
        self.assertEqual(row["description"], resource()["attributes"]["description"])
        self.assertEqual(row["requirements"], resource()["attributes"]["requirements"])
        self.assertTrue(row["requirements_source_empty"])
        self.assertEqual(row["posted_at_raw"], "10/07/2026 14:14:56")
        self.assertEqual(row["expires_at_raw"], "12/06/2026 14:14:56")
        self.assertNotIn("insights", row["source_attributes"])
        self.assertNotIn("contactEmail", row["source_attributes"])
        self.assertFalse(result["coverage_complete"])
        self.assertFalse(row["reviewed_by_model"])

    def test_foreign_country_and_ignored_employment_filter_are_limited(self):
        for change in [
            {"location": {"country": {"code": "SA", "name": "Saudi Arabia"}}},
            {"workTypes": [{"name": "full_time"}]},
        ]:
            job = resource()
            job["attributes"].update(change)
            result = w.parse_page(search(), {"data": [job]}, 1, "part_time")
            self.assertEqual(result["status"], "source_limited")
            self.assertEqual(len(result["listings"]), 1)

    def test_missing_description_and_bad_total_never_claim_zero_supply(self):
        job = resource()
        del job["attributes"]["description"]
        result = w.parse_page(search(), {"data": [job]}, 1)
        self.assertEqual(result["status"], "source_limited")
        self.assertEqual(result["listings"][0]["api_id"], ID)
        with self.assertRaises(ValueError):
            w.parse_page({"data": []}, {"data": []}, 1)
        result = w.parse_page({"meta": {"totalResultsCount": 147}, "data": []}, {"data": []}, 1)
        self.assertEqual(result["status"], "source_limited")

    def test_repeated_search_ids_are_not_silent_deduplication(self):
        document = search(2)
        document["data"].append(copy.deepcopy(document["data"][0]))
        result = w.parse_page(document, {"data": [resource()]}, 1)
        self.assertEqual(result["status"], "source_limited")
        self.assertEqual(result["search_ids"], [ID, ID])
        self.assertIn("duplicate_search_ids", result["issues"])

    def test_http_failure_is_not_empty_success(self):
        failure = urllib.error.HTTPError(w.API_BASE, 403, "Forbidden", {}, None)
        with patch.object(
            w,
            "read_json",
            side_effect=failure,
        ):
            result = w.query_page()
        failure.close()
        self.assertEqual(result["status"], "source_limited")
        self.assertNotIn("listings", result)
        self.assertFalse(result["coverage_complete"])

    def test_transport_timeout_fits_three_request_page_budget(self):
        endpoint = w.api_url("job", {"filter[slug]": "abcdefghijkl-example-egypt"})
        with patch.object(w.urllib.request, "build_opener") as builder:
            response = builder.return_value.open.return_value.__enter__.return_value
            response.geturl.return_value = endpoint
            response.headers.get_content_type.return_value = "application/vnd.api+json"
            response.read.return_value = b'{"data": []}'
            self.assertEqual(w.read_json(endpoint), {"data": []})
            self.assertEqual(builder.return_value.open.call_args.kwargs["timeout"], 12)
        self.assertLess(3 * w.HTTP_TIMEOUT_SECONDS, 45)

    def test_detail_rejects_credentials_query_and_arbitrary_paths(self):
        for url in [
            URL.replace("wuzzuf.net", "evil.test"),
            URL.replace("wuzzuf.net", "u:p@wuzzuf.net"),
            URL + "?token=secret",
            URL + "#detail",
            URL + "/",
            URL.replace("/jobs/p/", "/api/application/"),
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                w.canonical_detail_url(url)
        with self.assertRaises(ValueError):
            w.read_json("https://wuzzuf.net/api/application", method="POST", body={})

    def test_detail_slug_response_must_match_public_job(self):
        job = resource()
        with patch.object(w, "read_json", return_value={"data": [job]}):
            result = w.query_detail(URL)
        self.assertEqual(result["status"], "ok")
        job["attributes"]["uri"] = "jobs/p/abcdefghijkl-wrong-job"
        with patch.object(w, "read_json", return_value={"data": [job]}):
            result = w.query_detail(URL)
        self.assertEqual(result["status"], "source_limited")

    def test_native_taxonomy_requires_egypt_selected(self):
        facets = {
            "data": [
                {
                    "name": "country",
                    "filters": [{"name": "Egypt", "isSelected": True, "count": 5250}],
                },
                {"name": "job_types", "filters": [{"name": "freelance_project", "count": 80}]},
            ]
        }
        with patch.object(w, "read_json", return_value=facets):
            self.assertEqual(
                w.query_taxonomy()["native_work_model_facets"][0]["name"], "freelance_project"
            )
        facets["data"][0]["filters"][0]["isSelected"] = False
        with patch.object(w, "read_json", return_value=facets), self.assertRaises(ValueError):
            w.query_taxonomy()

    def test_source_confidentiality_and_inline_names_are_preserved(self):
        job = resource()
        job["attributes"].update(hideSalary=True, hideCompany=True, salary={"min": 123})
        row = w.normalize_job(job, "Hidden employer")
        self.assertEqual(row["salary_display"], "Confidential")
        self.assertEqual(row["source_attributes"]["salary"], {"is_confidential": True})
        self.assertEqual(row["company_display"], "Confidential")
        self.assertIsNone(row["company"])
        self.assertEqual(
            w.text_from_html("<p>Open<b>CV</b> work.<br>Delivery.</p><p>Next.</p>"),
            "OpenCV work.\nDelivery.\nNext.",
        )


if __name__ == "__main__":
    unittest.main()
