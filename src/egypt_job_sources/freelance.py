"""Read-only worldwide client-demand access through fixed platform API operations.

Freelancer's public project endpoints were verified without account credentials.
Upwork requires an approved API application and an authorized access token. No
account, proposal, bid, messaging, payment, or arbitrary GraphQL operation exists.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

HTTP_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
MAX_OFFSET = 1_000_000
FREELANCER_API = "https://www.freelancer.com/api/projects/0.1/projects/"
UPWORK_API = "https://api.upwork.com/graphql"
UPWORK_SEARCH_QUERY = """query PublicOpportunitySearch($filter: MarketplaceJobPostingsSearchFilter) {
  marketplaceJobPostingsSearch(
    marketPlaceJobFilter: $filter
    searchType: USER_JOBS_SEARCH
    sortAttributes: [{field: RECENCY}]
  ) {
    totalCount
    edges { cursor node { id title description ciphertext amount { displayValue currency } } }
    pageInfo { hasNextPage endCursor }
  }
}"""
UPWORK_CONTENT_QUERY = """query PublicOpportunityContents($ids: [ID!]!) {
  marketplaceJobPostingsContents(ids: $ids) {
    id ciphertext title description publishedDateTime
  }
}"""


class NativeTimeFilterMismatch(ValueError):
    """The source returned known activity outside the exact native envelope."""


def source_capabilities(source: str | None = None) -> dict:
    """Return dated capability evidence, without reading accounts or credentials."""
    capabilities = {
        "freelancer": {
            "source": "freelancer",
            "source_kind": "client_project_briefs",
            "access": "public_read_api_verified_without_account_credentials",
            "scope": "worldwide_active_projects_without_keyword_skill_or_country_filters",
            "search_url": FREELANCER_API + "active/",
            "detail_url_template": FREELANCER_API + "{numeric_project_id}/",
            "pagination": "limit_offset_with_total_count_mutable_during_enumeration",
            "full_description_projection": "full_description=true",
            "time_filter": {
                "arguments": "Paired aware RFC3339 from_time/to_time; requested window is [start,end).",
                "native_parameters": "Integer epoch seconds from_time/to_time bound update activity, not original creation.",
                "verification": "Validate returned time_updated against the native envelope; separately classify coherent submitdate/time_submitted within the exact requested window.",
                "live_basis": "Official SDK and bounded activity-vs-submission control verified 2026-10-10.",
            },
            "source_basis": "official_sdk_contract_and_live_public_response_2026-10-09",
            "reference": "https://github.com/freelancer/freelancer-sdk-python",
            "credentials_sent": False,
            "limits": [
                "Active-project search does not provide a complete historical market census.",
                "Local projects and full-time commitments remain source evidence; verify compatibility.",
                "Posted budget is client demand, not earned income or a guaranteed hourly rate.",
                "Hourly commitment hours are a billing limit (default 40/week), not a proven minimum required workload.",
                "Fees, identity, eligibility and payout access must be checked before any human bid.",
            ],
        },
        "upwork": {
            "source": "upwork",
            "source_kind": "client_marketplace_job_postings",
            "access": "approved_official_api_and_authorized_token_required_not_live_verified",
            "scope": "user_initiated_marketplace_search_without_keyword_or_skill_filters",
            "search_operation": "marketplaceJobPostingsSearch",
            "detail_operation": "marketplaceJobPostingsContents",
            "required_permission": "Read marketplace Job Postings",
            "token_environment_variable": "UPWORK_ACCESS_TOKEN",
            "pagination": "pagination_eq_after_first_and_returned_pageInfo_cursor",
            "api_approval_criteria_as_of": "2026-10-09",
            "api_approval_criteria": [
                "Valid identity, name, address, photo and verified payment method.",
                "At least USD 25,000 lifetime earnings, spend, or their combination.",
                "For freelancers and agencies, Job Success Score at least 90 percent.",
                "Account in good standing; reviewed personal or internal application use.",
            ],
            "approval_reference": "https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork",
            "schema_reference": "https://www.upwork.com/developer/documentation/graphql/api/docs/index.html",
            "limits": [
                "Official API approval is separate from ordinary marketplace membership.",
                "Approved-token live behavior and this account's permissions are unverified.",
                "Official API limits: 300 requests/minute/IP and 40,000 requests/day; cache at most 24 hours.",
                "Personal/internal API use only; open-source code does not authorize commercial data use.",
                "Verified search fields do not establish weekly hours, eligibility or hourly pay.",
                "Description text must still be read and checked against the exact work situation.",
            ],
        },
    }
    if source is not None:
        if source not in capabilities:
            raise ValueError("Unsupported freelance source")
        result = capabilities[source]
    else:
        result = {"sources": list(capabilities.values())}
    return {**result, "status": "ok", "coverage_complete": False, "reviewed_by_model": False}


def _integer(value: int, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside its supported integer range")
    return value


def _time_window(from_time: str | None, to_time: str | None) -> dict | None:
    """Keep an exact aware window and an enclosing integer native filter.

    Native search dates apply to update activity. They are not proof of a new
    project; exact submission timestamps are classified separately, without
    dropping rows or changing pagination counts.
    """
    if from_time is None and to_time is None:
        return None
    if from_time is None or to_time is None:
        raise ValueError("Both aware from_time and to_time are required")
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})"
    dates = []
    for value in (from_time, to_time):
        if (
            not isinstance(value, str)
            or len(value) > 128
            or not re.fullmatch(pattern, value)
            or value.endswith("-00:00")
        ):
            raise ValueError("Aware RFC3339 time required")
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.utcoffset() is None:
            raise ValueError("Aware RFC3339 time required")
        dates.append(date.astimezone(timezone.utc))
    lower, upper = (date.timestamp() for date in dates)
    if not 0 < lower < upper <= 253402300799:
        raise ValueError("Positive ordered supported time window required")
    return {
        "start": dates[0].isoformat(),
        "end": dates[1].isoformat(),
        "start_inclusive": True,
        "end_exclusive": True,
        "native_from_time": math.floor(lower),
        "native_to_time": math.ceil(upper),
        "native_time_basis": "source_update_activity_not_original_creation",
        "original_publication_semantics": "Source submission fields do not prove first-ever creation or exclude a repost of the same identity.",
    }


def _epoch(value: object) -> int | float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 < value <= 253402300799
    ):
        return None
    return value


def _classify_time_window(listing: dict, window: dict) -> dict:
    updated = _epoch(listing.get("time_updated_raw"))
    if (
        updated is not None
        and not window["native_from_time"] <= updated <= window["native_to_time"]
    ):
        raise NativeTimeFilterMismatch("Returned update timestamp contradicts native time filter")
    submitted = _epoch(listing.get("time_submitted_raw"))
    submitdate = _epoch(listing.get("submitdate_raw"))
    coherent = submitted is not None and submitdate is not None and submitted == submitdate
    lower = datetime.fromisoformat(window["start"]).timestamp()
    upper = datetime.fromisoformat(window["end"]).timestamp()
    submission_status = (
        ("in_window" if lower <= submitted < upper else "outside_window")
        if coherent
        else "undetermined"
    )
    return {
        "native_activity_filter_status": "verified" if updated is not None else "undetermined",
        "submission_time_window_status": submission_status,
        "submission_basis": "matching_source_submitdate_and_time_submitted_epoch_seconds"
        if coherent
        else "source_submission_fields_missing_invalid_or_conflicting",
        "first_ever_creation_verified": False,
    }


def _project_id(value: str | int) -> str:
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,29}", str(value)):
        raise ValueError("Expected a numeric public project identifier")
    return str(value)


def _cursor(value: str | None) -> str:
    if value is None:
        return "0"
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or any(ord(character) < 32 or ord(character) > 126 for character in value)
    ):
        raise ValueError("Invalid opaque marketplace cursor")
    return value


def _base(source: str, status: str = "ok") -> dict:
    return {
        "source": source,
        "status": status,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "coverage_complete": False,
        "reviewed_by_model": False,
    }


def _limited(source: str, reason: str) -> dict:
    return {
        **_base(source, "source_limited"),
        "error": reason,
        "limits": source_capabilities(source)["limits"],
    }


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("API redirects are not an acquisition success")


def _validated_upwork_variables(query: str, variables: dict) -> bool:
    if query == UPWORK_SEARCH_QUERY:
        if set(variables) != {"filter"} or not isinstance(variables["filter"], dict):
            return False
        filters = variables["filter"]
        if set(filters) != {"pagination_eq"} or not isinstance(filters["pagination_eq"], dict):
            return False
        paging = filters["pagination_eq"]
        if set(paging) != {"after", "first"} or not isinstance(paging["after"], str):
            return False
        _cursor(paging["after"])
        _integer(paging["first"], 1, 100, "limit")
        return True
    if query == UPWORK_CONTENT_QUERY:
        if set(variables) != {"ids"} or not isinstance(variables["ids"], list):
            return False
        if len(variables["ids"]) != 1:
            return False
        _project_id(variables["ids"][0])
        return True
    return False


def read_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    headers: dict | None = None,
) -> dict:
    """Bounded JSON transport; fixed paths and fixed read operations only."""
    parsed = urlsplit(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    parameters = dict(pairs)
    if len(parameters) != len(pairs):
        raise ValueError("Duplicate API parameters are not supported")
    freelancer_path = parsed.path.removeprefix("/api/projects/0.1/projects/")
    freelancer_search = freelancer_path == "active/"
    projection = {"full_description", "job_details", "location_details"}
    expected_parameters = projection | ({"limit", "offset"} if freelancer_search else set())
    native_dates = {"from_time", "to_time"}
    dated_search = freelancer_search and native_dates <= set(parameters)
    if dated_search:
        expected_parameters |= native_dates
    freelancer_parameters = set(parameters) == expected_parameters and all(
        parameters.get(name) == "true" for name in projection
    )
    if freelancer_parameters and freelancer_search:
        freelancer_parameters = all(parameters[name].isdigit() for name in ("limit", "offset"))
        if freelancer_parameters:
            _integer(int(parameters["limit"]), 1, 100, "limit")
            _integer(int(parameters["offset"]), 0, MAX_OFFSET, "offset")
            if dated_search:
                if not all(parameters[name].isdigit() for name in native_dates):
                    raise ValueError("Integer native time bounds required")
                lower = _integer(int(parameters["from_time"]), 1, 253402300799, "from_time")
                upper = _integer(int(parameters["to_time"]), 1, 253402300799, "to_time")
                if lower >= upper:
                    raise ValueError("Native time bounds must be ordered")
    freelancer_allowed = (
        parsed.scheme == "https"
        and parsed.netloc == "www.freelancer.com"
        and parsed.path == "/api/projects/0.1/projects/" + freelancer_path
        and (freelancer_path == "active/" or re.fullmatch(r"[1-9][0-9]{0,29}/", freelancer_path))
        and method == "GET"
        and body is None
        and not headers
        and freelancer_parameters
    )
    upwork_allowed = (
        url == UPWORK_API
        and method == "POST"
        and isinstance(body, dict)
        and body.get("query") in {UPWORK_SEARCH_QUERY, UPWORK_CONTENT_QUERY}
        and set(body) == {"query", "variables"}
        and isinstance(body["variables"], dict)
        and _validated_upwork_variables(body["query"], body["variables"])
        and isinstance(headers, dict)
        and set(headers) == {"Authorization"}
        and isinstance(headers["Authorization"], str)
        and headers["Authorization"].startswith("Bearer ")
        and _upwork_token(headers["Authorization"][7:]) is not None
    )
    if parsed.fragment or not (freelancer_allowed or upwork_allowed):
        raise ValueError("Request is outside the fixed public opportunity API contract")
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "egypt-job-sources/0.2.0",
        **(headers or {}),
    }
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=request_headers, method=method)
    with build_opener(NoRedirects()).open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        if response.geturl() != url or response.headers.get_content_type() != "application/json":
            raise ValueError("Unexpected API redirect or non-JSON response")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("API payload exceeds its bounded response limit")

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON keys are not supported")
            value[key] = item
        return value

    def finite_constant(value):
        raise ValueError("Non-finite JSON numbers are not supported")

    document = json.loads(
        raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=finite_constant
    )
    if not isinstance(document, dict):
        raise ValueError("API root must be a JSON object")
    return document


def _object_fields(value: object, names: tuple[str, ...], label: str) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"Unexpected {label} structure")
    result = {}
    for name in names:
        field = value.get(name)
        _scalar(field, label)
        if name in value:
            result[name] = field
    return result


def _scalar(value: object, label: str) -> str | int | float | bool | None:
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError(f"Unexpected nested {label} structure")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Non-finite {label} value")
    return value


def _freelancer_location(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Unexpected public project location structure")
    country = _object_fields(value.get("country"), ("name", "code", "iso3"), "country")
    result = _object_fields(
        value, ("city", "administrative_area", "administrative_area_code"), "location"
    )
    result["country"] = country
    result["timezone"] = _object_fields(
        value.get("timezone"), ("timezone", "offset", "country"), "timezone"
    )
    return result


def _freelancer_hourly(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Unexpected hourly project terms structure")
    result = _object_fields(value, ("duration_enum",), "hourly duration")
    result["commitment"] = _object_fields(
        value.get("commitment"), ("hours", "interval"), "hourly commitment"
    )
    return result


def _freelancer_url(seo_url: object) -> tuple[str | None, str]:
    if isinstance(seo_url, str) and re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", seo_url):
        return "https://www.freelancer.com/projects/" + seo_url, "public_source_seo_path"
    return None, "source_seo_path_missing_or_unverified"


def _freelancer_project(project: dict, expected_id: str | None = None) -> dict | None:
    if not isinstance(project, dict):
        raise ValueError("Project row must be an object")
    identifier = _project_id(project.get("id"))
    if expected_id is not None and identifier != expected_id:
        raise ValueError("Detail identifier does not match requested project")
    if not isinstance(project.get("nonpublic"), bool) or not isinstance(
        project.get("deleted"), bool
    ):
        raise ValueError("Project public/deleted flags are missing or unverified")
    upgrades = project.get("upgrades")
    if (
        project["nonpublic"]
        or project["deleted"]
        or (isinstance(upgrades, dict) and upgrades.get("nonpublic") is True)
    ):
        return None
    title = project.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Public project title is missing")
    description = project.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError("Unexpected full project description structure")
    description_present = bool(description and description.strip())
    skills = []
    jobs = project.get("jobs")
    if jobs is not None:
        if not isinstance(jobs, list):
            raise ValueError("Unexpected public job skills structure")
        for job in jobs:
            if not isinstance(job, dict):
                raise ValueError("Unexpected public job skill row")
            category = _object_fields(job.get("category"), ("id", "name"), "skill category")
            skills.append({**_object_fields(job, ("id", "name"), "skill"), "category": category})
    url, url_basis = _freelancer_url(project.get("seo_url"))
    return {
        "id": identifier,
        "stable_id": "freelancer:" + identifier,
        "source": "freelancer",
        "title": title,
        "url": url,
        "url_basis": url_basis,
        "description": description if description_present else None,
        "description_basis": "source_full_description_field_not_yet_reviewed"
        if description_present
        else "missing_full_description",
        "gates": [] if description_present else ["missing_full_description"],
        "status_raw": _scalar(project.get("status"), "status"),
        "sub_status_raw": _scalar(project.get("sub_status"), "sub-status"),
        "frontend_project_status_raw": _scalar(
            project.get("frontend_project_status"), "frontend status"
        ),
        "project_type_raw": _scalar(project.get("type"), "project type"),
        "budget": _object_fields(
            project.get("budget"),
            ("minimum", "maximum", "name", "project_type", "currency_id"),
            "budget",
        ),
        "currency": _object_fields(
            project.get("currency"), ("id", "code", "name", "sign"), "currency"
        ),
        "budget_unit": "source_posted_hourly_range_not_earned_income"
        if project.get("type") == "hourly"
        else "source_posted_whole_project_range_not_earned_income"
        if project.get("type") == "fixed"
        else "source_budget_unit_unverified_not_earned_income",
        "hourly_project_info": _freelancer_hourly(project.get("hourly_project_info")),
        "hourly_commitment_basis": "source_weekly_billing_limit_not_minimum_required_hours",
        "full_time_upgrade_raw": _scalar(
            upgrades.get("fulltime") if isinstance(upgrades, dict) else None, "full-time upgrade"
        ),
        "skills": skills,
        "local_raw": _scalar(project.get("local"), "local flag"),
        "location": _freelancer_location(project.get("location")),
        "language_raw": _scalar(project.get("language"), "language"),
        "submitdate_raw": _scalar(project.get("submitdate"), "submit date"),
        "time_submitted_raw": _scalar(project.get("time_submitted"), "submitted time"),
        "time_updated_raw": _scalar(project.get("time_updated"), "updated time"),
        "date_basis": "source_epoch_seconds_original_publication_semantics_unverified",
        "eligibility_basis": "worldwide_source_inventory_requires_exact_project_country_and_hours_review",
        "coverage_complete": False,
        "reviewed_by_model": False,
    }


def parse_freelancer_page(
    document: dict,
    *,
    limit: int,
    offset: int,
    from_time: str | None = None,
    to_time: str | None = None,
) -> dict:
    _integer(limit, 1, 100, "limit")
    _integer(offset, 0, MAX_OFFSET, "offset")
    window = _time_window(from_time, to_time)
    result = document.get("result") if isinstance(document, dict) else None
    if document.get("status") != "success" or not isinstance(result, dict):
        raise ValueError("Freelancer API did not return successful project results")
    projects = result.get("projects")
    total = result.get("total_count")
    if (
        not isinstance(projects, list)
        or isinstance(total, bool)
        or not isinstance(total, int)
        or total < 0
        or len(projects) > limit
        or (projects and total < offset + len(projects))
        or (not projects and offset < total)
    ):
        raise ValueError("Freelancer project count or pagination schema is inconsistent")
    listings, excluded, identifiers = [], [], set()
    for project in projects:
        if not isinstance(project, dict):
            raise ValueError("Project row must be an object")
        identifier = _project_id(project.get("id"))
        if identifier in identifiers:
            raise ValueError("Duplicate project identifiers on one source page")
        identifiers.add(identifier)
        item = _freelancer_project(project)
        if item is None:
            excluded.append({"id": identifier, "reason": "source_marks_nonpublic_or_deleted"})
        else:
            if window is not None:
                item["time_window_screening"] = _classify_time_window(item, window)
            listings.append(item)
    following = offset + len(projects)
    has_more = following < total
    output = {
        **_base("freelancer"),
        "listings": listings,
        "reported_total": total,
        "returned_count": len(projects),
        "excluded_rows": excluded,
        "pagination": {
            "requested_offset": offset,
            "requested_limit": limit,
            "next_offset": following if has_more else None,
            "has_more": has_more,
            "basis": "offset_derived_from_returned_rows_and_mutable_source_total",
        },
        "limits": source_capabilities("freelancer")["limits"],
    }
    if window is not None:
        output["requested_time_window"] = window
        output["source_filters"] = {
            "active_only": True,
            "from_time": window["native_from_time"],
            "to_time": window["native_to_time"],
            "time_basis": window["native_time_basis"],
        }
        statuses = [item["time_window_screening"] for item in listings]
        output["source_filter_verification"] = {
            "native_activity_timestamps_verified": sum(
                item["native_activity_filter_status"] == "verified" for item in statuses
            ),
            "native_activity_timestamps_undetermined": sum(
                item["native_activity_filter_status"] == "undetermined" for item in statuses
            ),
            "submission_in_window": sum(
                item["submission_time_window_status"] == "in_window" for item in statuses
            ),
            "submission_outside_window": sum(
                item["submission_time_window_status"] == "outside_window" for item in statuses
            ),
            "submission_undetermined": sum(
                item["submission_time_window_status"] == "undetermined" for item in statuses
            ),
            "all_rows_retained_pagination_counts_unchanged": True,
            "provider_echoed_applied_filters": False,
            "first_ever_creation_verified": False,
        }
    return output


def read_freelancer_page(
    limit: int = 20,
    offset: int = 0,
    *,
    transport: Callable | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
) -> dict:
    try:
        _integer(limit, 1, 100, "limit")
        _integer(offset, 0, MAX_OFFSET, "offset")
        window = _time_window(from_time, to_time)
        params = {
            "limit": limit,
            "offset": offset,
            "full_description": "true",
            "job_details": "true",
            "location_details": "true",
        }
        if window is not None:
            params.update(from_time=window["native_from_time"], to_time=window["native_to_time"])
        url = FREELANCER_API + "active/?" + urlencode(params)
        result = parse_freelancer_page(
            (transport or read_json)(url),
            limit=limit,
            offset=offset,
            from_time=from_time,
            to_time=to_time,
        )
        return {**result, "source_url": url}
    except NativeTimeFilterMismatch:
        return {
            **_limited(
                "freelancer",
                "Returned update timestamps contradict the requested activity window; acquisition is incomplete, not zero supply.",
            ),
            "error_code": "native_activity_time_filter_mismatch",
            "filter_verification_failed": True,
        }
    except Exception:
        return _limited(
            "freelancer", "Public project request or schema validation failed; not zero supply."
        )


def read_freelancer_detail(project_id: str | int, *, transport: Callable | None = None) -> dict:
    try:
        identifier = _project_id(project_id)
        params = {"full_description": "true", "job_details": "true", "location_details": "true"}
        url = FREELANCER_API + identifier + "/?" + urlencode(params)
        document = (transport or read_json)(url)
        if document.get("status") != "success" or not isinstance(document.get("result"), dict):
            raise ValueError("Invalid detail result")
        listing = _freelancer_project(document["result"], identifier)
        if listing is None:
            return _limited(
                "freelancer", "Requested project is nonpublic or deleted; content excluded."
            )
        return {
            **_base("freelancer"),
            "listing": listing,
            "source_url": url,
            "limits": source_capabilities("freelancer")["limits"],
        }
    except Exception:
        return _limited(
            "freelancer", "Public project detail request or identity validation failed."
        )


def _upwork_token(access_token: str | None) -> str | None:
    value = os.environ.get("UPWORK_ACCESS_TOKEN") if access_token is None else access_token
    if not value:
        return None
    if (
        not isinstance(value, str)
        or len(value) > 8192
        or any(ord(character) < 33 or ord(character) > 126 for character in value)
    ):
        raise ValueError("Invalid authorized access token")
    return value


def _upwork_data(document: dict, operation: str) -> object:
    if not isinstance(document, dict) or document.get("errors"):
        raise ValueError("GraphQL error or malformed response")
    data = document.get("data")
    if not isinstance(data, dict) or operation not in data or data[operation] is None:
        raise ValueError("Expected marketplace operation data is absent")
    return data[operation]


def _upwork_listing(node: dict, expected_id: str | None = None) -> dict:
    if not isinstance(node, dict):
        raise ValueError("Marketplace posting must be an object")
    identifier = _project_id(node.get("id"))
    if expected_id is not None and identifier != expected_id:
        raise ValueError("Marketplace detail identifier does not match request")
    title, description = node.get("title"), node.get("description")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Marketplace title is missing")
    if description is not None and not isinstance(description, str):
        raise ValueError("Marketplace description has an unexpected structure")
    has_description = bool(description and description.strip())
    ciphertext = node.get("ciphertext")
    if ciphertext is not None and (
        not isinstance(ciphertext, str) or not re.fullmatch(r"~?[A-Za-z0-9_-]{1,120}", ciphertext)
    ):
        raise ValueError("Marketplace public ciphertext is malformed")
    return {
        "source": "upwork",
        "id": identifier,
        "stable_id": "upwork:" + identifier,
        "title": title,
        "description": description if has_description else None,
        "description_basis": "source_description_requires_detail_and_full_read_verification"
        if has_description
        else "missing_full_description",
        "gates": [] if has_description else ["missing_full_description"],
        "ciphertext": ciphertext,
        "url": None,
        "url_basis": "canonical_detail_url_not_exposed_by_verified_query_fields",
        "amount": _object_fields(
            node.get("amount"), ("displayValue", "currency"), "marketplace amount"
        ),
        "budget_unit": "source_amount_unit_and_hourly_terms_unverified_not_earned_income",
        "published_at_raw": _scalar(node.get("publishedDateTime"), "publication date"),
        "date_basis": "source_publishedDateTime_when_returned_semantics_unverified",
        "eligibility_basis": "marketplace_inventory_requires_exact_country_hours_and_profile_review",
        "coverage_complete": False,
        "reviewed_by_model": False,
    }


def parse_upwork_page(document: dict, *, limit: int, cursor: str | None = None) -> dict:
    _integer(limit, 1, 100, "limit")
    requested_cursor = _cursor(cursor)
    connection = _upwork_data(document, "marketplaceJobPostingsSearch")
    if not isinstance(connection, dict):
        raise ValueError("Marketplace search connection is malformed")
    edges, info, total = (
        connection.get("edges"),
        connection.get("pageInfo"),
        connection.get("totalCount"),
    )
    if (
        not isinstance(edges, list)
        or len(edges) > limit
        or not isinstance(info, dict)
        or not isinstance(info.get("hasNextPage"), bool)
        or isinstance(total, bool)
        or not isinstance(total, int)
        or total < len(edges)
        or (requested_cursor == "0" and not edges and total > 0)
    ):
        raise ValueError("Marketplace pagination or count is inconsistent")
    following = info.get("endCursor")
    if info["hasNextPage"]:
        if not edges or _cursor(following) == requested_cursor or following is None:
            raise ValueError("Marketplace reports more supply without an advancing cursor")
    elif following is not None:
        _cursor(following)
    identifiers, listings = set(), []
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Marketplace edge is malformed")
        listing = _upwork_listing(edge.get("node"))
        if listing["id"] in identifiers:
            raise ValueError("Duplicate marketplace identifiers on one source page")
        identifiers.add(listing["id"])
        listings.append(listing)
    return {
        **_base("upwork"),
        "listings": listings,
        "reported_total": total,
        "returned_count": len(edges),
        "pagination": {
            "requested_cursor": requested_cursor,
            "requested_limit": limit,
            "next_cursor": following if info["hasNextPage"] else None,
            "has_more": info["hasNextPage"],
            "basis": "source_returned_pageInfo_cursor",
        },
        "limits": source_capabilities("upwork")["limits"],
    }


def _upwork_missing_token() -> dict:
    return {
        **_limited(
            "upwork",
            "Approved Upwork API access and UPWORK_ACCESS_TOKEN are required; no network request made.",
        ),
        "api_approval_required": True,
        "approval_reference": source_capabilities("upwork")["approval_reference"],
    }


def read_upwork_page(
    limit: int = 20,
    cursor: str | None = None,
    *,
    transport: Callable | None = None,
    access_token: str | None = None,
) -> dict:
    try:
        _integer(limit, 1, 100, "limit")
        after = _cursor(cursor)
        token = _upwork_token(access_token)
        if token is None:
            return _upwork_missing_token()
        body = {
            "query": UPWORK_SEARCH_QUERY,
            "variables": {"filter": {"pagination_eq": {"after": after, "first": limit}}},
        }
        document = (transport or read_json)(
            UPWORK_API, method="POST", body=body, headers={"Authorization": "Bearer " + token}
        )
        return parse_upwork_page(document, limit=limit, cursor=cursor)
    except Exception:
        return _limited(
            "upwork",
            "Marketplace API request, authorization or schema validation failed; not zero supply.",
        )


def read_upwork_detail(
    project_id: str | int, *, transport: Callable | None = None, access_token: str | None = None
) -> dict:
    try:
        identifier = _project_id(project_id)
        token = _upwork_token(access_token)
        if token is None:
            return _upwork_missing_token()
        document = (transport or read_json)(
            UPWORK_API,
            method="POST",
            body={"query": UPWORK_CONTENT_QUERY, "variables": {"ids": [identifier]}},
            headers={"Authorization": "Bearer " + token},
        )
        contents = _upwork_data(document, "marketplaceJobPostingsContents")
        if not isinstance(contents, list) or len(contents) != 1:
            raise ValueError("Marketplace contents do not contain exactly the requested posting")
        listing = _upwork_listing(contents[0], identifier)
        return {
            **_base("upwork"),
            "listing": listing,
            "limits": source_capabilities("upwork")["limits"],
        }
    except Exception:
        return _limited(
            "upwork", "Marketplace content request, authorization or identity validation failed."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["freelancer", "upwork"])
    parser.add_argument("--capabilities", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int)
    parser.add_argument("--cursor")
    parser.add_argument("--project-id")
    parser.add_argument("--from-time", help="Freelancer activity lower bound, aware RFC3339")
    parser.add_argument("--to-time", help="Freelancer activity upper bound, aware RFC3339")
    arguments = parser.parse_args(argv)
    if arguments.capabilities:
        result = source_capabilities(arguments.source)
    elif arguments.source is None:
        parser.error("--source is required unless --capabilities is used")
    elif (arguments.from_time is not None or arguments.to_time is not None) and (
        arguments.source != "freelancer" or arguments.project_id is not None
    ):
        parser.error("Time filters are Freelancer search-only, not Upwork or detail arguments")
    elif (arguments.source == "freelancer" and arguments.cursor is not None) or (
        arguments.source == "upwork" and arguments.offset is not None
    ):
        parser.error("--offset is Freelancer-only; --cursor is Upwork-only")
    elif arguments.project_id is not None:
        if arguments.offset is not None or arguments.cursor is not None:
            parser.error("Detail requests do not accept pagination")
        result = (
            read_freelancer_detail if arguments.source == "freelancer" else read_upwork_detail
        )(arguments.project_id)
    elif arguments.source == "freelancer":
        result = read_freelancer_page(
            arguments.limit,
            arguments.offset or 0,
            from_time=arguments.from_time,
            to_time=arguments.to_time,
        )
    else:
        result = read_upwork_page(arguments.limit, arguments.cursor)
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if result.get("status", "ok") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
