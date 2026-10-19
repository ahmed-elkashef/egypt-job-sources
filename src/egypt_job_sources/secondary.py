"""Scoped secondary-board acquisition; source evidence, never candidate fit.

Tanqeeb's native Next link omits its selected work-model state. Its anonymous
HTTP route is not a verified filtered transport. Public DOM captures therefore
bind the observed country/selected controls and require native browser clicks.
Akhtaboot's exact anonymous Egypt page has a separately verified empty state.
"""

from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from lxml import html

HOSTS = {"tanqeeb": "egypt.tanqeeb.com", "akhtaboot": "www.akhtaboot.com"}
TANQEEB_MODELS = {
    "-1": "All",
    "1": "Full Time",
    "2": "Part Time",
    "5": "Internship",
    "7": "Freelance/ Project",
}
TANQEEB_PARAMETERS = {"keywords": "", "country": "213", "state": "0", "lang": "all"}


def _text(node):
    from .boards import clean_text

    return clean_text(node)


def _class(name):
    return f'contains(concat(" ", normalize-space(@class), " "), " {name} ")'


def _one_text(node, xpath):
    matches = node.xpath(xpath)
    return _text(matches[0]) if matches else None


def page_url(source, page=1, work_model=None):
    if source not in HOSTS or isinstance(page, bool) or not 1 <= page <= 10000:
        raise ValueError("Unsupported secondary board or page")
    if work_model is not None:
        raise ValueError(
            "No verified secondary-board work-model URL encoding; select the native control and capture its state"
        )
    if source == "tanqeeb":
        suffix = "" if page == 1 else f"/page/{page}"
        return f"https://{HOSTS[source]}/jobs/search{suffix}?" + urlencode(
            TANQEEB_PARAMETERS | {"order_by": "most_recent"}
        )
    return f"https://{HOSTS[source]}/en/egypt/jobs" + (f"?page={page}" if page > 1 else "")


def validate_url(source, url, *, detail=False):
    p = urlsplit(url)
    if (
        source not in HOSTS
        or p.scheme != "https"
        or p.hostname != HOSTS[source]
        or p.username is not None
        or p.password is not None
        or p.port is not None
        or p.fragment
    ):
        raise ValueError("Only canonical HTTPS public secondary-board URLs are allowed")
    q = parse_qs(p.query, keep_blank_values=True)
    if any(len(values) != 1 for values in q.values()):
        raise ValueError("Duplicate source query/filter values are not allowed")
    if detail:
        if source == "akhtaboot":
            if q or not re.fullmatch(r"/en/egypt/jobs/[a-z0-9-]+/[1-9]\d*-[^/?#]+", p.path):
                raise ValueError("Unrecognized canonical Akhtaboot Egypt public detail URL")
            return url
        if q or not re.fullmatch(
            r"/jobs-in-(?:egypt|middle-east)/all/jobs/0?[1-9]\d*\.html", p.path
        ):
            raise ValueError("Unrecognized canonical Tanqeeb public detail URL")
        return url
    if source == "tanqeeb":
        if not re.fullmatch(r"/jobs/search(?:/page/[1-9]\d*)?", p.path):
            raise ValueError("Unrecognized Tanqeeb inventory route")
        if (
            set(q) - {*TANQEEB_PARAMETERS, "order_by"}
            or any(q.get(key) != [value] for key, value in TANQEEB_PARAMETERS.items())
            or q.get("order_by", ["most_recent"]) != ["most_recent"]
        ):
            raise ValueError(
                "Tanqeeb requires blank keywords, Egypt country213, all cities/languages and newest order"
            )
        native = re.search(r"/page/(\d+)$", p.path)
        if native and int(native[1]) > 10000:
            raise ValueError("Invalid native page")
    else:
        if p.path != "/en/egypt/jobs" or set(q) - {"page", "per_page"}:
            raise ValueError(
                "Only exact Akhtaboot Egypt inventory and observed pagination are supported"
            )
        if "page" in q and (not q["page"][0].isdigit() or not 1 <= int(q["page"][0]) <= 10000):
            raise ValueError("Invalid native page")
        if "per_page" in q and q["per_page"] != ["25"]:
            raise ValueError("Only the observed Akhtaboot25-card page size is supported")
    return url


def filter_signature(source, url):
    p = urlsplit(validate_url(source, url))
    q = parse_qs(p.query, keep_blank_values=True)
    if source == "tanqeeb":
        q.setdefault("order_by", ["most_recent"])
        path = "/jobs/search"
    else:
        q.pop("page", None)
        path = p.path
    return path, tuple(sorted((key, tuple(value)) for key, value in q.items()))


def source_id(source, url):
    validate_url(source, url, detail=True)
    if source == "akhtaboot":
        return re.search(r"/([1-9]\d*)-[^/]+$", urlsplit(url).path)[1]
    return str(int(re.search(r"/(\d+)\.html$", urlsplit(url).path)[1]))


def _document(body):
    if not isinstance(body, str) or not body.strip():
        raise ValueError("Source response is empty; not zero supply")
    doc = html.fromstring(body)
    visible = _text(doc)
    gate_text = " ".join(_text(node) for node in doc.xpath("//title|//h1"))
    if re.search(
        r"(?:verify (?:that )?you are human|checking your browser|captcha challenge)",
        gate_text or visible[:300],
        re.I,
    ) or gate_text.strip().casefold() in {"access denied", "403 forbidden", "just a moment..."}:
        raise ValueError("Source challenge/access gate; not zero supply")
    return doc


def _tanqeeb_filters(doc):
    sections = doc.xpath("//*[@data-public-native-filters]")
    if len(sections) != 1 or sections[0].get("data-country") != "Egypt":
        raise ValueError("Tanqeeb selected public native country/filter evidence is required")
    selected = []
    for node in sections[0].xpath(".//*[@data-filter-name][@data-filter-value]"):
        name, value, label = (
            node.get("data-filter-name"),
            node.get("data-filter-value"),
            _text(node),
        )
        if name == "refine[job_types][]":
            if value not in TANQEEB_MODELS:
                raise ValueError("Unverified native Tanqeeb employment filter value")
            # Preserve the original visible label. Its text is not an inferred
            # actual-hours requirement and does not screen any returned card.
        elif name == "refine[order_by]":
            if value != "most_recent":
                raise ValueError("Tanqeeb selected ordering is not newest first")
        elif name == "refine[search_period]":
            if value != "0":
                raise ValueError("Only observed Tanqeeb all-time capture is supported")
        elif name in {
            "state",
            "refine[workplaces][]",
            "refine[apply_types][]",
            "refine[only_featured]",
            "refine[has_salary]",
            "notify_period",
        }:
            # Retain benign observed default controls, refusing narrower scope.
            defaults = {
                "state": {"0", "-1"},
                "notify_period": {"1"},
                "refine[only_featured]": {"0"},
                "refine[has_salary]": {"0"},
            }
            if value not in defaults.get(name, {""}):
                raise ValueError("Unverified/narrowed native Tanqeeb filter")
        else:
            raise ValueError("Unverified native Tanqeeb filter name")
        selected.append({"name": name, "value": value, "label": label})
    models = [row["value"] for row in selected if row["name"] == "refine[job_types][]"]
    ordering = [row for row in selected if row["name"] == "refine[order_by]"]
    if (
        not models
        or len(set(models)) != len(models)
        or ("-1" in models and len(models) != 1)
        or len(ordering) != 1
    ):
        raise ValueError("Tanqeeb selected work-model/order state is incomplete or contradictory")
    signature = hashlib.sha256(
        json.dumps(
            sorted((row["name"], row["value"]) for row in selected), ensure_ascii=False
        ).encode()
    ).hexdigest()
    return {"country": "Egypt", "selected_controls": selected, "native_filter_signature": signature}


def _pagination(source, doc, url):
    xpath = (
        '//*[@aria-label="Search Results Navigation"]//a[@href]'
        if source == "tanqeeb"
        else f"//*[{_class('pagination')}]//a[@href]"
    )
    links = []
    for anchor in doc.xpath(xpath):
        href = urljoin(url, anchor.get("href"))
        disabled = anchor.get("aria-disabled") == "true" or any(
            "disabled" in (node.get("class") or "").split()
            for node in [anchor, *anchor.iterancestors()]
        )
        # Disabled/current pager placeholders are evidence, not navigable URLs.
        if not disabled:
            validate_url(source, href)
            if filter_signature(source, href) != filter_signature(source, url):
                raise ValueError("Native continuation changed source filter scope")
        links.append(
            {"text": _text(anchor), "url": href, "disabled": disabled, "rel": anchor.get("rel")}
        )
    next_links = [
        row
        for row in links
        if not row["disabled"]
        and (
            row["text"].casefold() in {"next", "next ›", "next »", "التالي", "التالى"}
            or row["rel"] == "next"
        )
    ]
    if len(next_links) > 1 and len({row["url"] for row in next_links}) > 1:
        raise ValueError("Conflicting native Next controls")
    observed = next_links[0]["url"] if next_links else None
    if observed == url:
        raise ValueError("Native Next repeats the current page")
    return links, observed


def parse_page(source, body, url):
    validate_url(source, url)
    doc = _document(body)
    listings = []
    if source == "tanqeeb":
        native_filters = _tanqeeb_filters(doc)
        for article in doc.xpath("//article[@data-job-id]"):
            native_id = article.get("data-job-id")
            anchors = article.xpath(".//h2/a[@href]")
            if (
                not native_id
                or not native_id.isdigit()
                or len(anchors) != 1
                or not _text(anchors[0])
            ):
                raise ValueError("Tanqeeb card lacks its native ID/title/link")
            href = urljoin(url, anchors[0].get("href"))
            if source_id(source, href) != str(int(native_id)):
                raise ValueError("Tanqeeb card identity differs from canonical URL")
            closed = article.get("data-job-closed")
            listings.append(
                {
                    "id": str(int(native_id)),
                    "url": href,
                    "title": _text(anchors[0]),
                    "card_text": _text(article),
                    "employment_type_raw": article.get("data-job-type"),
                    "native_closed_raw": closed,
                    "source_status": "closed" if closed == "1" else None,
                    "source_date_raw": _one_text(article, f".//*[{_class('search-job-date')}]"),
                    "company": _one_text(article, f".//*[{_class('search-job-company-name')}]"),
                    "location": _one_text(
                        article, f".//*[{_class('search-job-workplace-location')}]"
                    ),
                    "source_name_raw": _one_text(article, f".//*[{_class('search-job-source')}]"),
                }
            )
        if not listings:
            raise ValueError("Tanqeeb card structure absent; no verified empty-state contract")
        native_page = (
            int(re.search(r"/page/(\d+)$", urlsplit(url).path)[1])
            if "/page/" in urlsplit(url).path
            else 1
        )
        explicit_empty = False
    else:
        countries = doc.xpath(
            '//*[@id="filter_form"]//input[@name="search[cp_country_name][vals][]"]/@value'
        )
        country_marker = doc.xpath("//*[@data-public-native-filters]/@data-country")
        if countries != ["Egypt"] and country_marker != ["Egypt"]:
            raise ValueError("Akhtaboot exact Egypt source scope is unverified")
        breadcrumb = _one_text(doc, '//*[@id="current_page"]')
        if breadcrumb != "Jobs in Egypt":
            raise ValueError("Akhtaboot Egypt breadcrumb missing or contradictory")
        for anchor in doc.xpath(f"//a[{_class('job-link')}][@href]"):
            href = urljoin(url, anchor.get("href"))
            native_id = source_id(source, href)
            containers = anchor.xpath(f"ancestor::*[{_class('row')}]")
            if not containers or not _text(anchor):
                raise ValueError("Akhtaboot job card container/title is missing")
            container = containers[-1]
            labels = _one_text(container, ".//small") or ""
            ref = re.search(r"Ref\. Number:\s*(\d+)", labels)
            date = re.search(r"Date Posted:\s*(\d{2}-\d{2}-\d{4})", labels)
            if not ref or ref[1] != native_id:
                raise ValueError("Akhtaboot card reference differs from canonical job URL")
            listings.append(
                {
                    "id": native_id,
                    "url": href,
                    "title": _text(anchor),
                    "card_text": _text(container),
                    "source_date_raw": date[1] if date else None,
                    "company_location_raw": _one_text(container, f".//p[{_class('no-margin')}]"),
                    "employment_type_raw": None,
                }
            )
        explicit_empty = any(
            _text(node) == "Sorry, no results found"
            for node in doc.xpath(f"//p[{_class('error_message')}]")
        )
        if explicit_empty and listings:
            raise ValueError("Akhtaboot no-results message contradicts job cards")
        if not explicit_empty and not listings:
            raise ValueError("Akhtaboot listing structure/empty state absent; not zero supply")
        native_filters = {
            "country": "Egypt",
            "scope_basis": "exact_Egypt_URL_and_source_country_and_breadcrumb",
        }
        native_page = int(parse_qs(urlsplit(url).query).get("page", ["1"])[0])
    pagination, observed = _pagination(source, doc, url)
    if explicit_empty and observed:
        raise ValueError("Akhtaboot empty state contradicts a live Next control")
    return {
        "listings": listings,
        "reported_total": 0 if explicit_empty else None,
        "source_filters": native_filters,
        "rendered_page_number": native_page,
        "next_url": None if source == "tanqeeb" else observed,
        "observed_next_control_href": observed,
        "pagination_links": pagination,
        "next_browser_action": {
            "kind": "click_visible_next_then_verify_native_filter_signature",
            "label": "Next",
            "expected_native_filter_signature": native_filters["native_filter_signature"],
        }
        if source == "tanqeeb" and observed
        else None,
        "page_fingerprint": hashlib.sha256(
            "\n".join(sorted(row["id"] for row in listings)).encode()
        ).hexdigest(),
        "native_empty_state_verified": explicit_empty,
        "native_partition_pagination_verified": explicit_empty,
        "description_basis": "listing_card_only_full_detail_required",
        "date_basis": "source_display_or_aggregator_publication_not_original_employer_history",
        "limits": [
            "Source metadata and native filters do not establish actual hours, original employer publication or candidate eligibility.",
            "Tanqeeb native Next omits selected work-model state; preserve native clicks and verify the captured filter signature."
            if source == "tanqeeb"
            else "Current Egypt empty state was live verified; nonempty provider markup was separately checked outside Egypt as diagnostics, not Egyptian supply or history.",
        ],
    }


def parse_detail(source, body, url):
    if url is None:
        raise ValueError("Canonical secondary-board detail URL required for source identity")
    validate_url(source, url, detail=True)
    doc = _document(body)
    expected = source_id(source, url)
    if source == "akhtaboot":
        return _akhtaboot_detail(doc, url, expected)
    titles = (
        doc.xpath("//*[@data-public-source-title]")
        or doc.xpath(f"//h3[{_class('job-title-text')}]")
        or doc.xpath("//h1")
    )
    if len(titles) != 1 or not _text(titles[0]):
        raise ValueError("Tanqeeb exact detail title is missing")
    # Use only the job's explicitly selected public description container. The
    # browser extractor supplies this marker from the actual native description.
    descriptions = doc.xpath("//*[@data-public-job-description]") or doc.xpath(
        '//*[@id="jobDescriptionBody"]'
    )
    if len(descriptions) != 1 or not _text(descriptions[0]):
        raise ValueError("Tanqeeb full native job description is absent")
    selected = {}
    fields = {
        "@type": {},
        "title": {},
        "description": {},
        "datePosted": {},
        "validThrough": {},
        "employmentType": {},
        "jobLocationType": {},
        "url": {},
        "identifier": {"@type": {}, "value": {}, "name": {}},
        "hiringOrganization": {"@type": {}, "name": {}, "sameAs": {}},
        "applicantLocationRequirements": {"@type": {}, "name": {}},
        "jobLocation": {
            "@type": {},
            "address": {
                "@type": {},
                "addressCountry": {},
                "addressRegion": {},
                "addressLocality": {},
            },
        },
        "baseSalary": {
            "@type": {},
            "currency": {},
            "value": {"@type": {}, "value": {}, "minValue": {}, "maxValue": {}, "unitText": {}},
        },
    }

    def select(value, allowed):
        if isinstance(value, list):
            return [select(child, allowed) for child in value]
        if isinstance(value, dict):
            return {
                key: select(value[key], children)
                for key, children in allowed.items()
                if key in value
            }
        return value

    postings = []

    def walk(value):
        if isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            if value.get("@type") == "JobPosting":
                postings.append(value)
            if "@graph" in value:
                walk(value["@graph"])

    for script in doc.xpath('//script[@type="application/ld+json"]'):
        try:
            walk(json.loads(script.text or ""))
        except (ValueError, TypeError):
            raise ValueError("Malformed public structured job metadata") from None
    if len(postings) > 1:
        raise ValueError("Multiple structured jobs cannot identify this exact detail")
    if postings:
        posting = postings[0]
        declared_url = posting.get("url")
        if declared_url is not None and (
            not isinstance(declared_url, str) or source_id(source, declared_url) != expected
        ):
            raise ValueError("Structured Tanqeeb URL identity differs from requested detail")
        identifier = posting.get("identifier")
        native_id = identifier.get("value") if isinstance(identifier, dict) else identifier
        if native_id is not None and (
            isinstance(native_id, bool) or str(native_id).lstrip("0") != expected
        ):
            raise ValueError("Structured Tanqeeb identifier differs from requested detail")
        selected = select(posting, fields)
    description = descriptions[0]
    return {
        "id": expected,
        "url": url,
        "title": _text(titles[0]),
        "description": html.tostring(description, encoding="unicode"),
        "description_text": _text(description),
        "employment_type_raw": selected.get("employmentType"),
        "source_jobposting": selected,
        "source_identity_verification": "canonical_detail_URL_ID",
        "source_date_raw": selected.get("datePosted"),
        "description_basis": "complete_selected_native_description_not_yet_reviewed",
        "date_basis": "aggregator_datePosted_source_assertion_not_original_employer_creation_history",
        "reviewed_by_model": False,
    }


def _akhtaboot_detail(doc, url, expected):
    description_labels = doc.xpath(f"//*[{_class('description-list')}]//dl/dt")
    labels = [
        node for node in description_labels if _text(node) == "Job Description and Requirements"
    ]
    if len(labels) != 1 or labels[0].getnext() is None or labels[0].getnext().tag != "dd":
        raise ValueError("Akhtaboot full Job Description and Requirements section is absent")
    description = labels[0].getnext()
    if not _text(description):
        raise ValueError("Akhtaboot full description is empty")
    allowed = {
        "Company",
        "Industry",
        "Job Location",
        "Career Level",
        "Date Posted",
        "Ref. Number",
        "Citizenships",
        "Residence Country",
    }
    metadata = {}
    for label in doc.xpath("//dl/dt"):
        name = _text(label).rstrip(":")
        value = label.getnext()
        if name not in allowed or value is None or value.tag != "dd":
            continue
        text = _text(value)
        if name in metadata and metadata[name] != text:
            raise ValueError("Akhtaboot duplicate native metadata values conflict")
        metadata[name] = text
    if metadata.get("Ref. Number") != expected:
        raise ValueError("Akhtaboot detail reference differs from canonical URL")
    title = (
        _one_text(doc, "//*[@data-public-source-title]")
        or _one_text(doc, "//h1")
        or _one_text(doc, "//head/title")
    )
    if not title:
        raise ValueError("Akhtaboot detail title is absent")
    return {
        "id": expected,
        "url": url,
        "title": title,
        "description": html.tostring(description, encoding="unicode"),
        "description_text": _text(description),
        "sections": {
            "Job Description and Requirements": {
                "html": html.tostring(description, encoding="unicode"),
                "text": _text(description),
            }
        },
        "company": metadata.get("Company"),
        "location": metadata.get("Job Location"),
        "source_date_raw": metadata.get("Date Posted"),
        "source_metadata": metadata,
        "applicant_residence_country_raw": metadata.get("Residence Country"),
        "applicant_citizenships_raw": metadata.get("Citizenships"),
        "source_identity_verification": "canonical_URL_and_Ref_Number_match",
        "description_basis": "full_native_description_and_requirements_not_yet_reviewed",
        "date_basis": "native_DD_MM_YYYY_calendar_timezone_and_original_creation_unverified",
        "reviewed_by_model": False,
    }
