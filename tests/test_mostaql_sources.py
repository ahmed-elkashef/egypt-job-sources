import unittest

from egypt_job_sources.mostaql import canonical_project_url, parse_mostaql_detail

URL = "https://mostaql.com/project/100001-example"


def page(brief="<p>First paragraph.</p><p>Second <b>bold</b> paragraph.</p>"):
    return f"""<html><head><link rel="canonical" href="{URL}"></head><body>
    <h1 class="heada__title">Public project</h1>
    <div id="project-brief"><div id="projectDetailsTab">
      <div class="text-wrapper-div carda__content">{brief}</div>
    </div></div>
    <div id="project-meta-panel">
      <div class="meta-row"><div class="meta-label">حالة المشروع</div>
        <div class="meta-value"><bdi class="label label-prj-open">مفتوح</bdi></div></div>
      <div class="meta-row"><div class="meta-label">الميزانية</div>
        <div class="meta-value" data-type="project-budget_range">$50.00 - $100.00</div></div>
      <div class="meta-row"><div class="meta-label">مدة التنفيذ</div>
        <div class="meta-value">7 أيام</div></div>
      <div class="meta-row"><div class="meta-label">تاريخ النشر</div>
        <div class="meta-value"><time itemprop="datePublished" datetime="2026-10-09 20:13:32">منذ 7 دقائق</time></div></div>
      <div id="project-users"><div class="profile_card">Owner contact secrets</div></div>
    </div>
    <div id="project-bids-panel">Different freelancer offer promises</div>
    <form id="add-bid">Apply for $999 now</form>
    <div class="payment-summary-row">$0 payment placeholder</div>
    </body></html>"""


class MostaqlDetailTests(unittest.TestCase):
    def test_current_scope_needs_no_main_and_excludes_bids_profiles_and_forms(self):
        parsed = parse_mostaql_detail(page())
        self.assertEqual(parsed["stable_id"], "mostaql:100001")
        self.assertEqual(parsed["description"], "First paragraph.\nSecond bold paragraph.")
        self.assertIn("<p>", parsed["description_html"])
        for unwanted in ["Owner contact", "offer promises", "$999", "$0"]:
            self.assertNotIn(unwanted, parsed["description"])
            self.assertNotIn(unwanted, parsed["description_html"])
        self.assertFalse(parsed["reviewed_by_model"])
        self.assertFalse(parsed["coverage_complete"])

    def test_source_terms_keep_date_timezone_status_budget_unit_and_delivery_distinct(self):
        parsed = parse_mostaql_detail(page())
        self.assertEqual(parsed["project_status_raw"], "مفتوح")
        self.assertIn("label-prj-open", parsed["project_status_marker_raw"])
        self.assertEqual(parsed["budget_raw"], "$50.00 - $100.00")
        self.assertEqual(
            parsed["budget_unit"], "whole_project_posted_budget_range_not_earned_income"
        )
        self.assertEqual(parsed["delivery_duration_raw"], "7 أيام")
        self.assertEqual(parsed["posted_at_raw"], "2026-10-09 20:13:32")
        self.assertIn("unverified", parsed["date_basis"])
        self.assertNotIn("hours", parsed)

    def test_missing_or_drifted_brief_is_failure_not_empty_success(self):
        for body in [
            "<html><h1>Access denied</h1></html>",
            page().replace('id="projectDetailsTab"', 'id="newUnverifiedScope"'),
            page("<form>Not the project description</form>"),
        ]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_mostaql_detail(body)

    def test_canonical_identity_matches_requested_id_and_survives_slug_change(self):
        self.assertEqual(
            parse_mostaql_detail(page(), "https://mostaql.com/project/100001-old-slug")["id"],
            "100001",
        )
        with self.assertRaises(ValueError):
            parse_mostaql_detail(page(), "https://mostaql.com/project/100002-wrong-project")
        without_canonical = page().replace(f'<link rel="canonical" href="{URL}">', "")
        self.assertEqual(parse_mostaql_detail(without_canonical, URL)["id"], "100001")
        with self.assertRaises(ValueError):
            parse_mostaql_detail(without_canonical)
        for url in [
            "https://other.test/project/100001-example",
            "https://u:p@mostaql.com/project/100001-example",
            URL + "?access_token=secret",
            "https://mostaql.com/project/100001-example%2Fother",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_project_url(url)

    def test_accidentally_nested_action_panel_cannot_become_project_text(self):
        parsed = parse_mostaql_detail(
            page(
                '<p>Deliver this item.</p><div id="project-bids">Freelancer bid</div>'
                "<script>Not source prose</script><!-- Hidden implementation comment -->"
            )
        )
        self.assertEqual(parsed["description"], "Deliver this item.")
        self.assertNotIn("Freelancer bid", parsed["description_html"])
        self.assertNotIn("Hidden implementation comment", parsed["description_html"])

    def test_missing_metadata_stays_unknown_without_losing_available_brief(self):
        parsed = parse_mostaql_detail(
            page().replace('id="project-meta-panel"', 'id="driftedMetadata"')
        )
        self.assertTrue(parsed["description"])
        self.assertIsNone(parsed["budget_raw"])
        self.assertIsNone(parsed["delivery_duration_raw"])
        self.assertIsNone(parsed["project_status_raw"])
        self.assertIsNone(parsed["posted_at_raw"])
        self.assertTrue(any("Missing source terms" in limit for limit in parsed["limits"]))


if __name__ == "__main__":
    unittest.main()
