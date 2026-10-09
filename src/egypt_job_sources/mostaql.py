"""Parse current public Mostaql project briefs without reading bids or profiles.

Independent implementation from the observed public HTML. No network, browser,
authentication or transaction code. Parsed source text remains unreviewed.
"""

from __future__ import annotations

import re
from copy import deepcopy
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from lxml import html


def _class(name: str) -> str:
    return f'contains(concat(" ",normalize-space(@class)," ")," {name} ")'


def _compact(node) -> str:
    return " ".join(node.text_content().split())


def canonical_project_url(url: str) -> tuple[str, str]:
    """Validate a source identity; this function does not fetch the URL."""
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.netloc != "mostaql.com"
        or parts.query
        or parts.fragment
        or parts.username is not None
        or parts.password is not None
        or parts.port
    ):
        raise ValueError("Canonical HTTPS Mostaql project URL required")
    path = unquote(parts.path)
    match = re.fullmatch(r"/project/([1-9]\d*)-([^/]+)", path)
    if not match or any(ord(char) < 32 for char in path):
        raise ValueError("Stable Mostaql project ID and source slug required")
    canonical = urlunsplit(("https", "mostaql.com", quote(path, safe="/"), "", ""))
    return canonical, match.group(1)


def _description_text(node) -> str:
    """Keep paragraph/list boundaries while allowing inline text to join."""
    blocks = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "section", "tr"}

    def parts(current):
        if not isinstance(current.tag, str):
            return
        if current.tag in blocks or current.tag == "br":
            yield "\n"
        if current.text:
            yield current.text
        for child in current:
            yield from parts(child)
            if child.tail:
                yield child.tail
        if current.tag in blocks:
            yield "\n"

    return "\n".join(
        " ".join(line.split()) for line in "".join(parts(node)).splitlines() if line.strip()
    )


def parse_mostaql_detail(body: str | bytes, url: str | None = None) -> dict:
    """Acquire one complete scoped public brief, with raw source terms.

    A caller URL can supply identity when canonical markup is absent. When both
    exist their stable project IDs must agree, including after a slug change.
    Metadata omissions stay explicit; description/identity drift fails closed.
    """
    doc = html.fromstring(body)
    canonicals = set(
        doc.xpath('//link[contains(concat(" ",normalize-space(@rel)," ")," canonical ")]/@href')
    )
    if len(canonicals) > 1:
        raise ValueError("Ambiguous Mostaql canonical project identity")
    page_identity = canonical_project_url(next(iter(canonicals))) if canonicals else None
    requested_identity = canonical_project_url(url) if url is not None else None
    if page_identity and requested_identity and page_identity[1] != requested_identity[1]:
        raise ValueError("Mostaql canonical project ID differs from requested project")
    identity = page_identity or requested_identity
    if identity is None:
        raise ValueError("Mostaql canonical project identity absent")

    titles = doc.xpath(f"//h1[{_class('heada__title')}]")
    briefs = doc.xpath(
        f'//*[@id="project-brief"]//*[@id="projectDetailsTab"]'
        f"//*[{_class('text-wrapper-div')} and {_class('carda__content')}]"
    )
    if len(titles) != 1 or not _compact(titles[0]):
        raise ValueError("Mostaql public project title missing or ambiguous")
    if len(briefs) != 1:
        raise ValueError("Mostaql complete public project brief missing or ambiguous")
    brief = deepcopy(briefs[0])
    # These scopes are outside the brief in the verified source. Exclude them
    # even if a later layout accidentally nests an action/profile panel here.
    for node in brief.xpath(
        ".//script|.//style|.//form|.//input|.//button|.//iframe|.//dialog|.//comment()|"
        './/*[@id="add-bid-panel" or @id="add-bid" or @id="project-bids-panel" '
        'or @id="project-bids" or starts-with(normalize-space(@id),"project-users") '
        f"or {_class('profile_card')} or {_class('payment-summary-row')}]"
    ):
        if node.getparent() is not None:
            node.drop_tree()
    description = _description_text(brief)
    if not description:
        raise ValueError("Mostaql complete public project brief is empty")

    panels = doc.xpath('//*[@id="project-meta-panel"]')
    if not panels:
        panels = doc.xpath('//*[@id="mobile-project-meta-panel"]')
    if len(panels) > 1:
        raise ValueError("Mostaql project metadata scope is ambiguous")
    metadata = {}
    publication_raw = None
    publication_display = None
    status_marker = None
    budget_notation = None
    skills = []
    if panels:
        panel = panels[0]
        for row in panel.xpath(f".//*[{_class('meta-row')}]"):
            labels = row.xpath(f"./*[{_class('meta-label')}]")
            values = row.xpath(f"./*[{_class('meta-value')}]")
            if len(labels) != 1 or len(values) != 1 or not _compact(labels[0]):
                continue
            label, value = _compact(labels[0]), _compact(values[0])
            if label in metadata and metadata[label] != value:
                raise ValueError("Mostaql project metadata values conflict")
            metadata[label] = value
            if label == "حالة المشروع":
                markers = values[0].xpath('.//*[contains(@class,"label-prj-")]/@class')
                status_marker = markers[0] if len(markers) == 1 else None
        dates = panel.xpath('.//time[@itemprop="datePublished"]')
        if len(dates) > 1:
            raise ValueError("Mostaql project publication metadata is ambiguous")
        if dates:
            publication_raw = dates[0].get("datetime")
            publication_display = _compact(dates[0])
        budgets = panel.xpath('.//*[@data-type="project-budget_range"]')
        if len(budgets) > 1:
            raise ValueError("Mostaql project budget metadata is ambiguous")
        if budgets:
            budget_notation = _compact(budgets[0])
        skills = [_compact(node) for node in panel.xpath(f".//ul[{_class('skills')}]//a")]

    missing = [
        label
        for label in ("حالة المشروع", "الميزانية", "مدة التنفيذ", "تاريخ النشر")
        if not metadata.get(label)
    ]
    return {
        "id": identity[1],
        "stable_id": f"mostaql:{identity[1]}",
        "url": identity[0],
        "title": _compact(titles[0]),
        "description": description,
        "description_html": html.tostring(brief, encoding="unicode", with_tail=False),
        "description_basis": "scoped_complete_public_project_brief_not_yet_reviewed",
        "source_metadata": metadata,
        "project_status_raw": metadata.get("حالة المشروع"),
        "project_status_marker_raw": status_marker,
        "budget_raw": budget_notation or metadata.get("الميزانية"),
        "budget_unit": "whole_project_posted_budget_range_not_earned_income",
        "delivery_duration_raw": metadata.get("مدة التنفيذ"),
        "posted_at_raw": publication_raw,
        "posted_at_display": publication_display,
        "date_basis": "source_datetime_attribute_timezone_and_original_publication_semantics_unverified",
        "skills_raw": skills,
        "coverage_complete": False,
        "reviewed_by_model": False,
        "limits": [
            "Client authenticity, platform fees, Egypt payment access and delivery ability remain unverified.",
            "A delivery duration is not working hours; a posted budget is not guaranteed or earned income.",
            "Publication timezone is unverified; do not assume an exact aware frozen-window instant.",
            *(["Missing source terms: " + ", ".join(missing)] if missing else []),
        ],
    }
