"""Read-only WUZZUF JSON:API acquisition from its current public frontend contract.

Independent implementation; no third-party scraper code, login, cookies or evasion.
The public frontend protocol was observed on 2026-10-09; it is undocumented
and may change. Acquisition is never model review or market completion.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from lxml import html

API_BASE = "https://wuzzuf.net/api/"
PAGE_SIZE = 15
HTTP_TIMEOUT_SECONDS = 12
WORK_MODELS = {
    "full_time",
    "part_time",
    "freelance_project",
    "internship",
    "shift_based",
    "volunteering",
}
UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
SLUG = re.compile(r"[a-z0-9]{12}-[a-z0-9-]+\Z")
HEADERS = {
    "User-Agent": "egypt-job-sources/0.1.0",
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}


def model_name(value: str | None) -> str | None:
    value = "freelance_project" if value == "freelance" else value
    if value is not None and value not in WORK_MODELS:
        raise ValueError("Unsupported WUZZUF native work model")
    return value


def public_page_url(page: int = 1, work_model: str | None = None) -> str:
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10000:
        raise ValueError("page must be an integer in 1..10000")
    model = model_name(work_model)
    pairs = [("filters[country][0]", "Egypt")]
    if model:
        pairs.append(("filters[job_types][0]", model))
    if page > 1:
        pairs.append(("start", str(page - 1)))
    return "https://wuzzuf.net/search/jobs?" + urllib.parse.urlencode(pairs)


def search_body(page: int, work_model: str | None = None) -> dict[str, Any]:
    public_page_url(page, work_model)
    filters = {"country": ["Egypt"]}
    if model := model_name(work_model):
        filters["job_types"] = [model]
    return {
        "startIndex": (page - 1) * PAGE_SIZE,
        "pageSize": PAGE_SIZE,
        "longitude": "0",
        "latitude": "0",
        "query": "",
        "searchFilters": filters,
    }


def canonical_detail_url(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "wuzzuf.net"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Expected a canonical public WUZZUF job URL")
    # Native internship resources were observed on 10 October 2026 under
    # /internship/<the same 12-character public ID>-slug. Preserve that actual
    # route rather than constructing a nonexistent /jobs/p/ mirror.
    prefix = next(
        (
            candidate
            for candidate in ("/jobs/p/", "/internship/")
            if parsed.path.startswith(candidate)
        ),
        None,
    )
    if prefix is None:
        raise ValueError("Expected /jobs/p/<source-slug> or /internship/<source-slug>")
    slug = parsed.path[len(prefix) :]
    if not SLUG.fullmatch(slug):
        raise ValueError("Invalid WUZZUF source slug")
    return "https://wuzzuf.net" + parsed.path, slug


def api_url(path: str, pairs: dict[str, str] | None = None) -> str:
    if path not in {"search/job", "search/job/filters", "job", "country"}:
        raise ValueError("WUZZUF API path is not allowlisted")
    return API_BASE + path + ("?" + urllib.parse.urlencode(pairs) if pairs else "")


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("WUZZUF API redirect is not an acquisition success")


def read_json(url: str, *, method: str = "GET", body: dict | None = None) -> dict:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "wuzzuf.net" or parsed.fragment:
        raise ValueError("WUZZUF API request is not allowlisted")
    path = parsed.path.removeprefix("/api/")
    if parsed.path != "/api/" + path or path not in {
        "search/job",
        "search/job/filters",
        "job",
        "country",
    }:
        raise ValueError("WUZZUF API request path is not allowlisted")
    if method not in {"GET", "POST"} or (
        method == "POST" and path not in {"search/job", "search/job/filters"}
    ):
        raise ValueError("Only public GETs and read-only search POSTs are supported")
    if (method == "POST") != (body is not None):
        raise ValueError("Search POSTs require a JSON body; GETs must have no body")
    data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.build_opener(NoRedirects()).open(
        request, timeout=HTTP_TIMEOUT_SECONDS
    ) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected WUZZUF API redirect")
        if response.headers.get_content_type() not in {
            "application/vnd.api+json",
            "application/json",
        }:
            raise ValueError("WUZZUF API returned non-JSON content")
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("WUZZUF API payload exceeds 8 MiB")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict) or document.get("errors"):
        raise ValueError("WUZZUF API response has errors or an invalid root")
    return document


def rows(document: dict) -> list[dict]:
    data = document.get("data")
    if not isinstance(data, list) or any(not isinstance(x, dict) for x in data):
        raise ValueError("WUZZUF API has no valid resource array")
    return data


def text_from_html(value: str) -> str:
    if not value.strip():
        return ""
    root = html.fragment_fromstring(value, create_parent="div")
    for node in root.xpath(".//script|.//style"):
        node.drop_tree()
    blocks = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "section", "table", "tr"}

    def parts(node):
        if node.tag in blocks or node.tag == "br":
            yield "\n"
        if node.text:
            yield node.text
        for child in node:
            yield from parts(child)
            if child.tail:
                yield child.tail
        if node.tag in blocks:
            yield "\n"

    return "\n".join(line.strip() for line in "".join(parts(root)).splitlines() if line.strip())


def normalize_job(resource: dict, company_name: str | None = None) -> dict:
    rid, attrs = resource.get("id"), resource.get("attributes")
    if (
        resource.get("type") != "job"
        or not isinstance(rid, str)
        or not UUID.fullmatch(rid)
        or not isinstance(attrs, dict)
    ):
        raise ValueError("Malformed WUZZUF job resource")
    if not isinstance(attrs.get("title"), str) or not attrs["title"].strip():
        raise ValueError("WUZZUF job title is missing")
    uri = attrs.get("uri")
    if not isinstance(uri, str):
        raise ValueError("WUZZUF job public URI is missing")
    public_url, slug = canonical_detail_url("https://wuzzuf.net/" + uri)
    description, requirements = attrs.get("description"), attrs.get("requirements")
    if not isinstance(description, str) or not text_from_html(description):
        raise ValueError("WUZZUF authoritative description is missing")
    if not isinstance(requirements, str):
        raise ValueError("WUZZUF authoritative requirements field is missing")
    company = resource.get("relationships", {}).get("company", {}).get("data") or {}
    # Deliberately select public vacancy fields, excluding insights, applicant data,
    # employer representative/contact fields and unrelated profile resources.
    public_attributes = {
        key: attrs[key]
        for key in (
            "title",
            "description",
            "requirements",
            "status",
            "jobType",
            "salary",
            "careerLevel",
            "workplaceArrangement",
            "location",
            "workExperienceYears",
            "vacancies",
            "workRoles",
            "workTypes",
            "candidatePreferences",
            "slug",
            "uri",
            "postedAt",
            "expireAt",
            "hideCompany",
            "hideSalary",
            "tempWorkingFromHome",
        )
        if key in attrs
    }
    if attrs.get("hideSalary"):
        public_attributes["salary"] = {"is_confidential": True}
    if attrs.get("hideCompany"):
        company_name = None
        company = {}
    return {
        "id": slug[:12],
        "api_id": rid,
        "url": public_url,
        "title": attrs["title"],
        "company": company_name,
        "company_id": company.get("id"),
        "company_display": "Confidential" if attrs.get("hideCompany") else company_name,
        "salary_display": "Confidential" if attrs.get("hideSalary") else attrs.get("salary"),
        "location": attrs.get("location"),
        "work_types": attrs.get("workTypes"),
        "posted_at_raw": attrs.get("postedAt"),
        "expires_at_raw": attrs.get("expireAt"),
        "date_basis": "source_MM_DD_YYYY_HH_MM_SS_timezone_not_verified",
        "source_status": attrs.get("status"),
        "description": description,
        "requirements": requirements,
        "sections": {
            "Job Description": {
                "html": description,
                "text": text_from_html(description),
            },
            "Job Requirements": {
                "html": requirements,
                "text": text_from_html(requirements),
            },
        },
        "requirements_source_empty": not bool(text_from_html(requirements)),
        "description_basis": "authoritative_public_JSONAPI_job_description_and_requirements",
        "detail_status": "acquired_unreviewed",
        "reviewed_by_model": False,
        "source_attributes": public_attributes,
    }


def parse_page(search: dict, details: dict, page: int, work_model: str | None = None) -> dict:
    requested_url = public_page_url(page, work_model)
    model = model_name(work_model)
    search_rows = rows(search)
    total = search.get("meta", {}).get("totalResultsCount")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ValueError("WUZZUF search lacks a valid totalResultsCount")
    ids = [row.get("id") for row in search_rows]
    if any(not isinstance(rid, str) or not UUID.fullmatch(rid) for rid in ids):
        raise ValueError("WUZZUF search has malformed stable IDs")
    issues = []
    if len(ids) != len(set(ids)):
        issues.append("duplicate_search_ids")
    if len(ids) > PAGE_SIZE or len(ids) != min(PAGE_SIZE, max(0, total - (page - 1) * PAGE_SIZE)):
        issues.append("unexpected_page_size_for_source_total")
    detail_rows = rows(details)
    lookup = {}
    for row in detail_rows:
        rid = row.get("id")
        if rid in lookup:
            issues.append("duplicate_detail_id")
        lookup[rid] = row
    missing_ids = [rid for rid in ids if rid not in lookup]
    extra_ids = [rid for rid in lookup if rid not in ids]
    if missing_ids or extra_ids:
        issues.append("search_detail_ID_mismatch")
    listings = []
    for row in search_rows:
        rid = row["id"]
        computed = row.get("attributes", {}).get("computedFields", [])
        names = [
            x.get("value", [None])[0]
            for x in computed
            if x.get("name") == "company_name" and x.get("value")
        ]
        placeholder = {
            "id": None,
            "api_id": rid,
            "detail_status": "missing_or_invalid",
            "reviewed_by_model": False,
        }
        if rid not in lookup:
            listings.append(placeholder)
            continue
        try:
            listing = normalize_job(
                lookup[rid], names[0] if names and isinstance(names[0], str) else None
            )
            country = (listing["location"] or {}).get("country", {})
            types = listing["work_types"] or []
            if country.get("code") != "EG" or country.get("name") != "Egypt":
                issues.append("country_filter_not_verified_for_ID:" + rid)
            if model and model not in {x.get("name") for x in types}:
                issues.append("work_model_filter_not_verified_for_ID:" + rid)
            listings.append(listing)
        except (ValueError, TypeError, AttributeError) as error:
            issues.append("detail_invalid_for_ID:" + rid)
            placeholder["error"] = str(error)[:200]
            listings.append(placeholder)
    has_more = page * PAGE_SIZE < total
    return {
        "source": "wuzzuf",
        "requested_url": requested_url,
        "status": "source_limited" if issues else "ok",
        "snapshot_status": "source_page_snapshot",
        "coverage_complete": False,
        "reviewed_by_model": False,
        "page": page,
        "page_size": PAGE_SIZE,
        "total_count": total,
        "reported_total": total,
        "listing_count": len(listings),
        "search_ids": ids,
        "listings": listings,
        "has_more": has_more,
        "next_url": public_page_url(page + 1, model) if has_more else None,
        "next_url_basis": "verified_public_page_index_route_and_API_total_not_a_captured_anchor",
        "url_pagination_position": page - 1,
        "page_fingerprint": hashlib.sha256(
            "\n".join(sorted(row["id"] for row in listings if row.get("id"))).encode()
        ).hexdigest(),
        "pagination_basis": "public_start_page_index_API_startIndex_15_card_offset",
        "missing_detail_ids": missing_ids,
        "unexpected_detail_ids": extra_ids,
        "issues": issues,
        "applied_filters": {"country": ["Egypt"], **({"job_types": [model]} if model else {})},
    }


def base_result(url: str) -> dict:
    return {
        "source": "wuzzuf",
        "requested_url": url,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "coverage_complete": False,
        "reviewed_by_model": False,
        "transport": "transparent_urllib_public_JSONAPI_no_auth_or_cookies",
        "protocol_basis": "undocumented_public_frontend_contract_observed_2026-10-09",
        "vendor_supported_developer_api": False,
        "http_timeout_seconds": HTTP_TIMEOUT_SECONDS,
        "limits": [
            "Source date strings have no verified timezone; preserve raw values.",
            "A page or detail acquisition does not establish complete source or interval coverage.",
            "The public frontend protocol may change; it is not a documented developer API.",
        ],
    }


def acquisition_failure(error: Exception) -> dict:
    """Retain provider cooldown evidence without logging cookies or credentials."""
    result = {"status": "source_limited", "error": str(error)[:300]}
    if isinstance(error, urllib.error.HTTPError):
        result["http_status"] = error.code
        result["http_response_headers"] = {
            key: value
            for key in (
                "Retry-After",
                "Date",
                "RateLimit-Limit",
                "RateLimit-Remaining",
                "RateLimit-Reset",
            )
            if (value := error.headers.get(key)) is not None
        }
        result["retry_after_raw"] = error.headers.get("Retry-After")
    return result


def query_taxonomy() -> dict:
    """Observe current country scope and every source-native employment facet."""
    body = {"query": "", "searchFilters": {"country": ["Egypt"]}}
    document = read_json(api_url("search/job/filters"), method="POST", body=body)
    facets = {row.get("name"): row for row in rows(document)}
    country = facets.get("country", {}).get("filters", [])
    selected = [row for row in country if row.get("isSelected")]
    if len(selected) != 1 or selected[0].get("name") != "Egypt":
        raise ValueError("WUZZUF country facet selection is not exactly Egypt")
    types = facets.get("job_types", {}).get("filters")
    if not isinstance(types, list) or not all(isinstance(row, dict) for row in types):
        raise ValueError("WUZZUF native employment taxonomy is missing")
    return {
        "native_work_model_facets": types,
        "country_facet": selected[0],
        "taxonomy_api_endpoint": api_url("search/job/filters"),
        "taxonomy_api_method": "POST",
        "taxonomy_request_parameters": body,
    }


def query_page(page: int = 1, work_model: str | None = None) -> dict:
    public_url = public_page_url(page, work_model)
    body = search_body(page, work_model)
    result = base_result(public_url)
    result.update(api_endpoint=api_url("search/job"), api_method="POST", request_parameters=body)
    try:
        search = read_json(api_url("search/job"), method="POST", body=body)
        ids = [x.get("id") for x in rows(search)]
        result["search_ids"] = ids
        if any(not isinstance(rid, str) or not UUID.fullmatch(rid) for rid in ids):
            raise ValueError("WUZZUF search IDs are malformed")
        detail_endpoint = api_url("job", {"filter[other][ids]": ",".join(ids)}) if ids else None
        result["detail_api_endpoint"] = detail_endpoint
        details = read_json(detail_endpoint) if detail_endpoint else {"data": []}
        result.update(parse_page(search, details, page, work_model))
        if page == 1:
            result.update(query_taxonomy())
            if work_model and model_name(work_model) not in {
                row.get("name") for row in result["native_work_model_facets"]
            }:
                result["status"] = "source_limited"
                result["issues"].append("requested_work_model_absent_from_native_taxonomy")
        return result
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        result.update(acquisition_failure(error))
        return result


def query_detail(public_url: str) -> dict:
    canonical, slug = canonical_detail_url(public_url)
    endpoint = api_url("job", {"filter[slug]": slug})
    result = base_result(canonical)
    result.update(
        api_endpoint=endpoint, api_method="GET", request_parameters={"filter[slug]": slug}
    )
    try:
        resources = rows(read_json(endpoint))
        if len(resources) != 1:
            raise ValueError("WUZZUF detail slug did not resolve to exactly one job")
        job = normalize_job(resources[0])
        if job["url"] != canonical:
            raise ValueError("WUZZUF detail resource does not match the public URL")
        result.update(status="ok", snapshot_status="source_detail_snapshot", **job)
        return result
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        result.update(acquisition_failure(error))
        return result
