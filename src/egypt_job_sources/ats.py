"""Strict anonymous public Greenhouse, Lever and Ashby employer-board reads.

Board tokens must come from an identified employer's official career page. This
module neither discovers employers nor guesses tokens from domains. Complete
source responses and descriptions are acquisition evidence, never a geographic
census, historical interval, candidate review or permission to apply.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_entities
import json
import re
import sys
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lxml import html

from .boards import clean_text

MAX_BYTES = 25 * 1024 * 1024
TIMEOUT_SECONDS = 35
SOURCES = ("greenhouse", "lever", "ashby")
DOCUMENTATION = {
    "greenhouse": "https://docs.greenhouse.io/job-board.html",
    "lever": "https://github.com/lever/postings-api",
    "ashby": "https://developers.ashbyhq.com/docs/public-job-posting-api",
}
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_NUMERIC_ID = re.compile(r"[1-9][0-9]{0,29}\Z")
_FIELDS = {
    "greenhouse": {
        "id",
        "internal_job_id",
        "title",
        "company_name",
        "location",
        "content",
        "absolute_url",
        "updated_at",
        "first_published",
        "application_deadline",
        "requisition_id",
        "language",
        "metadata",
        "departments",
        "offices",
        "pay_input_ranges",
        "include_ai_disclaimer",
        "ai_disclaimer",
    },
    "lever": {
        "id",
        "text",
        "categories",
        "country",
        "opening",
        "openingPlain",
        "description",
        "descriptionPlain",
        "descriptionBody",
        "descriptionBodyPlain",
        "lists",
        "additional",
        "additionalPlain",
        "hostedUrl",
        "workplaceType",
        "salaryRange",
        "salaryDescription",
        "salaryDescriptionPlain",
        "createdAt",
        "updatedAt",
    },
    "ashby": {
        "id",
        "title",
        "location",
        "secondaryLocations",
        "department",
        "team",
        "isListed",
        "isRemote",
        "workplaceType",
        "descriptionHtml",
        "descriptionPlain",
        "publishedAt",
        "employmentType",
        "address",
        "jobUrl",
        "compensation",
    },
}
COMMON_LIMITS = [
    "Only this explicitly supplied employer board is acquired; no country or market census.",
    "Current public postings are not complete historical supply or a frozen weekly interval.",
    "Remote, contract and internship labels do not establish Egypt eligibility or part-time hours.",
    "Amounts, currency and source units remain source terms, not earned income or assumed salary.",
    "Preserve employer/source attribution; code licensing does not license posting content.",
]


def _board(value: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError("Invalid explicit board token")
    return value


def _integer(value, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {label}")
    return value


def _job_id(value, source: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("Invalid public posting identifier")
    value = str(value)
    pattern = _NUMERIC_ID if source == "greenhouse" else _OPAQUE_ID
    if not pattern.fullmatch(value):
        raise ValueError("Invalid public posting identifier")
    return value


def endpoint(
    source: str,
    board: str,
    *,
    region: str | None = None,
    skip: int | None = None,
    limit: int | None = None,
    job_id: str | int | None = None,
) -> str:
    """Build only documented public GET routes, with pagination instead of filters."""
    if source not in SOURCES:
        raise ValueError("Unsupported ATS source")
    board = _board(board)
    if source != "lever" and any(value is not None for value in (region, skip, limit)):
        raise ValueError("Region and offset pagination are Lever-only")
    if job_id is not None and (skip is not None or limit is not None):
        raise ValueError("Posting details do not accept pagination")
    if source == "greenhouse":
        base = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        return (
            base + "/" + _job_id(job_id, source) + "?pay_transparency=true"
            if job_id is not None
            else base + "?content=true"
        )
    if source == "ashby":
        if job_id is not None:
            raise ValueError("No documented individual Ashby public detail endpoint")
        return f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    region = "global" if region is None else region
    if region not in {"global", "eu"}:
        raise ValueError("Unsupported Lever region")
    host = "api.lever.co" if region == "global" else "api.eu.lever.co"
    base = f"https://{host}/v0/postings/{board}"
    if job_id is not None:
        return base + "/" + _job_id(job_id, source)
    skip = _integer(0 if skip is None else skip, 0, 1_000_000_000, "offset")
    limit = _integer(100 if limit is None else limit, 1, 100, "page size")
    return base + "?" + urlencode({"mode": "json", "skip": skip, "limit": limit})


def validate_endpoint(url: str) -> str:
    """Refuse host/path changes, account routes, credentials and extra query fields."""
    if not isinstance(url, str):
        raise ValueError("Invalid public endpoint")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.fragment:
        raise ValueError("Invalid public endpoint")
    segments = parts.path.split("/")
    pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    params = dict(pairs)
    if len(params) != len(pairs):
        raise ValueError("Duplicate endpoint parameter")
    if parts.netloc == "boards-api.greenhouse.io" and segments[:3] == ["", "v1", "boards"]:
        if len(segments) not in {5, 6} or segments[4] != "jobs":
            raise ValueError("Unsupported Greenhouse route")
        expected = endpoint(
            "greenhouse", segments[3], job_id=segments[5] if len(segments) == 6 else None
        )
    elif parts.netloc in {"api.lever.co", "api.eu.lever.co"} and segments[:3] == [
        "",
        "v0",
        "postings",
    ]:
        if len(segments) not in {4, 5}:
            raise ValueError("Unsupported Lever route")
        kwargs = {"region": "eu" if parts.netloc == "api.eu.lever.co" else "global"}
        if len(segments) == 5:
            kwargs["job_id"] = segments[4]
        else:
            if set(params) != {"mode", "skip", "limit"} or params["mode"] != "json":
                raise ValueError("Unsupported Lever query")
            kwargs.update(skip=int(params["skip"]), limit=int(params["limit"]))
        expected = endpoint("lever", segments[3], **kwargs)
    elif parts.netloc == "api.ashbyhq.com" and segments[:3] == ["", "posting-api", "job-board"]:
        if len(segments) != 4:
            raise ValueError("Unsupported Ashby route")
        expected = endpoint("ashby", segments[3])
    else:
        raise ValueError("Endpoint outside the fixed public board scope")
    if url != expected:
        raise ValueError("Noncanonical or filtered public endpoint")
    return url


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Public ATS redirects are refused")


def read(url: str) -> bytes:
    """One bounded anonymous GET. No cookie jar, account access or raw error logs."""
    validate_endpoint(url)
    request = Request(
        url,
        headers={
            "User-Agent": "EgyptJobSources (+https://github.com/ahmed-elkashef/egypt-job-sources)",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
    )
    with build_opener(NoRedirects()).open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Unexpected response status or endpoint")
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime != "application/json" and not (
            mime.startswith("application/") and mime.endswith("+json")
        ):
            raise ValueError("Public endpoint did not return JSON")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("Unexpected encoded response")
        declared = response.headers.get("Content-Length")
        if declared is not None and (not declared.isdigit() or int(declared) > MAX_BYTES):
            raise ValueError("Invalid or oversized response length")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES or (declared is not None and len(body) != int(declared)):
            raise ValueError("Oversized or incomplete public response")
        return body


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _json(raw: str | bytes):
    def nonfinite(_):
        raise ValueError("Nonfinite JSON value")

    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=nonfinite)


def _string(value, label: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise ValueError(f"Invalid {label}")
    return value


def _public_url(value, *, host: str | None = None, path: str | None = None) -> str:
    value = _string(value, "public posting URL")
    if any(ord(character) < 33 or ord(character) == 127 for character in value):
        raise ValueError("Invalid public posting URL")
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.port is not None
        or parts.fragment
    ):
        raise ValueError("Invalid public posting URL")
    if host is not None and (parts.scheme != "https" or parts.netloc != host or parts.query):
        raise ValueError("Posting URL does not match its source")
    if path is not None and parts.path.rstrip("/") != path:
        raise ValueError("Posting URL does not match its identity")
    return value


def _html_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = value
    # Greenhouse documents HTML entities in its content, including nested ones.
    for _ in range(2):
        following = html_entities.unescape(decoded)
        if following == decoded:
            break
        decoded = following
    node = html.fragment_fromstring(
        decoded, create_parent="div", parser=html.HTMLParser(no_network=True)
    )
    return clean_text(node)


def _ashby_identity(value, board: str) -> tuple[str, str]:
    url = _public_url(value, host="jobs.ashbyhq.com")
    path = urlsplit(url).path.rstrip("/")
    parts = path.split("/")
    if len(parts) != 3 or parts[0] or parts[1] != board or not _OPAQUE_ID.fullmatch(parts[2]):
        raise ValueError("Ashby posting URL does not match its explicit board")
    return url, hashlib.sha256(url.rstrip("/").encode()).hexdigest()


def _source_data(row: dict, source: str) -> dict:
    data = {key: value for key, value in row.items() if key in _FIELDS[source]}
    json.dumps(data, allow_nan=False)  # Reject non-JSON/nonfinite injected transport values too.
    return data


def _base(source: str, board: str, region: str | None = None, *, status: str = "ok") -> dict:
    return {
        "status": status,
        "source": source,
        "board": board,
        "region": (region or "global") if source == "lever" else None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "coverage_complete": False,
        "reviewed_by_model": False,
        "board_snapshot_complete": False,
    }


def _listing(row: dict, source: str, board: str, region: str | None) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Invalid public posting")
    if any(key in row for key in ("error", "errors")):
        raise ValueError("Unexpected posting error envelope")
    data = _source_data(row, source)
    if source == "greenhouse":
        ident = _job_id(row.get("id"), source)
        url = _public_url(row.get("absolute_url"))
        title = _string(row.get("title"), "posting title")
        content = _string(row.get("content"), "description", optional=True)
        text, full_html = _html_text(content), content or ""
        source_id, identity_basis = ident, "source_public_job_post_id"
        dates = {
            key: row.get(key) for key in ("first_published", "updated_at", "application_deadline")
        }
        date_basis = (
            "first_published_when_returned; updated_at_is_an_update_not_original_publication"
        )
        location = {key: row.get(key) for key in ("location", "offices")}
        model, arrangement = None, None
        compensation = row.get("pay_input_ranges")
        internal = row.get("internal_job_id")
        if internal is not None:
            _job_id(internal, source)
        posting_kind = (
            "prospect_post"
            if "internal_job_id" in row and internal is None
            else "job_post"
            if "internal_job_id" in row
            else "job_or_prospect_kind_unverified"
        )
        sections = [{"label": "Description", "html": content, "text": text}]
    elif source == "lever":
        ident = _job_id(row.get("id"), source)
        host = "jobs.eu.lever.co" if region == "eu" else "jobs.lever.co"
        url = _public_url(row.get("hostedUrl"), host=host, path=f"/{board}/{ident}")
        title = _string(row.get("text"), "posting title")
        categories = row.get("categories")
        if not isinstance(categories, dict):
            raise ValueError("Invalid posting categories")
        for key in (
            "opening",
            "openingPlain",
            "description",
            "descriptionPlain",
            "descriptionBody",
            "descriptionBodyPlain",
            "additional",
            "additionalPlain",
            "salaryDescription",
            "salaryDescriptionPlain",
        ):
            _string(row.get(key), "description component", optional=True)
        body_html = row.get("description")
        if not body_html:
            body_html = "\n".join(row.get(key) or "" for key in ("opening", "descriptionBody"))
        body_plain = row.get("descriptionPlain")
        if not body_plain:
            if row.get("description"):
                body_plain = _html_text(row["description"])
            else:
                body_plain = "\n".join(
                    row.get(plain) or _html_text(row.get(markup))
                    for plain, markup in (
                        ("openingPlain", "opening"),
                        ("descriptionBodyPlain", "descriptionBody"),
                    )
                )
        sections = [
            {"label": "Description", "html": body_html, "text": body_plain or _html_text(body_html)}
        ]
        lists = row.get("lists", [])
        if not isinstance(lists, list):
            raise ValueError("Invalid posting description lists")
        for section in lists:
            if not isinstance(section, dict):
                raise ValueError("Invalid posting description section")
            label = _string(section.get("text"), "section label")
            content = _string(section.get("content"), "section HTML", optional=True)
            sections.append({"label": label, "html": content, "text": _html_text(content)})
        for label, markup, plain in (
            ("Additional", "additional", "additionalPlain"),
            ("Salary description", "salaryDescription", "salaryDescriptionPlain"),
        ):
            if row.get(markup) or row.get(plain):
                sections.append(
                    {
                        "label": label,
                        "html": row.get(markup),
                        "text": row.get(plain) or _html_text(row.get(markup)),
                    }
                )
        text = "\n\n".join(
            (section["label"] + "\n" if index else "") + section["text"]
            for index, section in enumerate(sections)
            if section["text"]
        )
        full_html = "\n".join(
            ("<h3>" + html_entities.escape(section["label"]) + "</h3>" if index else "")
            + (section["html"] or "")
            for index, section in enumerate(sections)
        )
        source_id, identity_basis = ident, "source_public_posting_id"
        dates = {key: row.get(key) for key in ("createdAt", "updatedAt")}
        date_basis = (
            "optional_undocumented_createdAt_or_updatedAt_not_verified_original_publication"
        )
        location = {
            "country": row.get("country"),
            "location": categories.get("location"),
            "allLocations": categories.get("allLocations"),
        }
        model, arrangement = categories.get("commitment"), row.get("workplaceType")
        compensation, internal, posting_kind = row.get("salaryRange"), None, "published_job_post"
    else:
        title = _string(row.get("title"), "posting title")
        url, ident = _ashby_identity(row.get("jobUrl"), board)
        source_id = None if row.get("id") is None else _job_id(row["id"], source)
        identity_basis = (
            "canonical_source_jobUrl_SHA256; no_native_id_required_by_documented_schema"
        )
        content = _string(row.get("descriptionHtml"), "description HTML", optional=True)
        plain = _string(row.get("descriptionPlain"), "description plaintext", optional=True)
        text, full_html = plain or _html_text(content), content or ""
        sections = [{"label": "Description", "html": content, "text": text}]
        dates, date_basis = (
            {"publishedAt": row.get("publishedAt")},
            "source_last_published_not_verified_first_publication",
        )
        location = {key: row.get(key) for key in ("location", "address", "secondaryLocations")}
        model, arrangement = row.get("employmentType"), row.get("workplaceType")
        compensation, internal, posting_kind = (
            row.get("compensation"),
            None,
            "listed_public_job_post",
        )
    return {
        "id": ident,
        "source_id": source_id,
        "stable_id": f"{source}:{region or 'global'}:{board}:{ident}",
        "identity_basis": identity_basis,
        "internal_job_id": internal,
        "posting_kind": posting_kind,
        "title": title,
        "url": url,
        "source": source,
        "board": board,
        "description": text if text.strip() else None,
        "description_html": full_html or None,
        "description_sections": sections,
        "description_basis": "complete_returned_public_posting_components_requires_full_read_verification",
        "gates": [] if text.strip() else ["missing_full_description"],
        "dates_raw": dates,
        "date_basis": date_basis,
        "location_raw": location,
        "employment_type_raw": model,
        "workplace_arrangement_raw": arrangement,
        "compensation_raw": compensation,
        "eligibility_basis": "exact_country_hours_and_requirements_need_posting_level_review",
        "source_data": data,
        "attribution": {"source": source, "url": url},
        "coverage_complete": False,
        "reviewed_by_model": False,
    }


def parse_board(
    document,
    source: str,
    board: str,
    *,
    region: str | None = None,
    skip: int | None = None,
    limit: int | None = None,
) -> dict:
    source_url = endpoint(source, board, region=region, skip=skip, limit=limit)
    if source == "lever":
        rows = document
    else:
        if not isinstance(document, dict) or not isinstance(document.get("jobs"), list):
            raise ValueError("Missing public jobs list")
        if any(key in document for key in ("error", "errors", "success")):
            raise ValueError("Unexpected source error envelope")
        rows = document["jobs"]
    if not isinstance(rows, list):
        raise ValueError("Invalid public posting list")
    result = {
        **_base(source, board, region),
        "source_url": source_url,
        "returned_count": len(rows),
        "limits": source_capabilities(source)["limits"],
    }
    if source == "greenhouse":
        meta = document.get("meta")
        if not isinstance(meta, dict):
            raise ValueError("Missing native board count")
        total = _integer(meta.get("total"), 0, sys.maxsize, "native board count")
        if total != len(rows):
            raise ValueError("Board count does not reconcile with returned postings")
        result.update(
            reported_total=total,
            board_snapshot_complete=True,
            pagination={
                "basis": "documented_all_jobs_response_with_reconciled_meta_total",
                "has_more": False,
            },
        )
    elif source == "ashby":
        if document.get("apiVersion") != "1":
            raise ValueError("Unknown Ashby public schema version")
        result.update(
            board_snapshot_complete=True,
            pagination={
                "basis": "documented_whole_board_response_no_native_total_or_pagination",
                "has_more": None,
            },
        )
    else:
        skip, limit = 0 if skip is None else skip, 100 if limit is None else limit
        if len(rows) > limit:
            raise ValueError("Lever page exceeds requested maximum")
        result["pagination"] = {
            "requested_skip": skip,
            "requested_limit": limit,
            "next_skip": skip + len(rows) if rows else None,
            "has_more": None if rows else False,
            "page_exhaustion_observed": not rows,
            "basis": "documented_skip_plus_observed_count; only_successful_empty_page_observes_terminal_offset",
        }
    listings, excluded, seen = [], [], set()
    for row in rows:
        if source == "ashby":
            if not isinstance(row, dict) or not isinstance(row.get("isListed"), bool):
                raise ValueError("Unknown Ashby listing visibility")
            if not row["isListed"]:
                _, key = _ashby_identity(row.get("jobUrl"), board)
                excluded.append(
                    {"identity_digest": key, "reason": "source_isListed_false_direct_link_only"}
                )
                if key in seen:
                    raise ValueError("Duplicate public posting identity")
                seen.add(key)
                continue
        listing = _listing(row, source, board, region)
        if listing["id"] in seen:
            raise ValueError("Duplicate public posting identity")
        seen.add(listing["id"])
        listings.append(listing)
    result.update(
        listings=listings,
        listed_count=len(listings),
        excluded_count=len(excluded),
        excluded_items=excluded,
    )
    return result


def parse_detail(
    document, source: str, board: str, job_id: str | int, *, region: str | None = None
) -> dict:
    url = endpoint(source, board, region=region, job_id=job_id)
    listing = _listing(document, source, board, region)
    if listing["source_id"] != _job_id(job_id, source):
        raise ValueError("Detail identity differs from the requested posting")
    return {
        **_base(source, board, region),
        "source_url": url,
        "listing": listing,
        "limits": source_capabilities(source)["limits"],
    }


def _limited(source: str, board: str, region: str | None, message: str) -> dict:
    return {**_base(source, board, region, status="source_limited"), "error": message}


def read_board(
    source: str,
    board: str,
    *,
    region: str | None = None,
    skip: int | None = None,
    limit: int | None = None,
    transport: Callable = read,
) -> dict:
    try:
        url = endpoint(source, board, region=region, skip=skip, limit=limit)
        document = _json(transport(url))
        return parse_board(document, source, board, region=region, skip=skip, limit=limit)
    except Exception:
        return _limited(
            source,
            board,
            region,
            "Public ATS board request, parameters or schema validation failed; not zero supply.",
        )


def read_detail(
    source: str,
    board: str,
    job_id: str | int,
    *,
    region: str | None = None,
    transport: Callable = read,
) -> dict:
    try:
        url = endpoint(source, board, region=region, job_id=job_id)
        document = _json(transport(url))
        return parse_detail(document, source, board, job_id, region=region)
    except Exception:
        return _limited(
            source,
            board,
            region,
            "Public ATS detail request, parameters or identity validation failed; no posting verified.",
        )


def source_capabilities(source: str | None = None) -> dict:
    capabilities = {}
    for name in SOURCES:
        capabilities[name] = {
            "status": "ok",
            "source": name,
            "access": "anonymous_official_public_GET",
            "reference": DOCUMENTATION[name],
            "documentation_checked": "2026-10-09",
            "scope": "one_explicit_employer_board_without_role_keyword_or_candidate_filters",
            "board_token_basis": "operator_verified_official_career_board_not_inferred_from_domain",
            "individual_detail_supported": name in {"greenhouse", "lever"},
            "pagination": "documented_skip_limit_pages"
            if name == "lever"
            else "whole_board_snapshot",
            "credentials_sent": False,
            "coverage_complete": False,
            "reviewed_by_model": False,
            "limits": COMMON_LIMITS
            + (
                {
                    "greenhouse": [
                        "meta.total counts public posts, including prospect posts; internal_job_id is a separate job/headcount key.",
                        "List updated_at is not original publication; request a detail for first_published when needed.",
                    ],
                    "lever": [
                        "No documented native total or first-publication timestamp; offsets can move as the board changes.",
                        "Continue every nonempty page using next_skip; a short page alone does not establish exhaustion.",
                    ],
                    "ashby": [
                        "publishedAt is when the job was last published, not guaranteed original publication.",
                        "isListed=false records are direct-link-only; only their identity digest/exclusion count is retained.",
                        "No documented native total, pagination or individual public detail endpoint.",
                    ],
                }[name]
            ),
        }
    if source is None:
        return {
            "status": "ok",
            "sources": capabilities,
            "coverage_complete": False,
            "reviewed_by_model": False,
        }
    if source not in capabilities:
        raise ValueError("Unsupported ATS source")
    return capabilities[source]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=SOURCES)
    parser.add_argument("--board")
    parser.add_argument("--region", choices=("global", "eu"))
    parser.add_argument("--skip", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--job-id")
    parser.add_argument("--capabilities", action="store_true")
    args = parser.parse_args(argv)
    if args.capabilities:
        result = source_capabilities(args.source)
    elif args.source is None or args.board is None:
        parser.error("--source and --board are required unless --capabilities is used")
    elif args.job_id is not None:
        if args.skip is not None or args.limit is not None:
            result = _limited(
                args.source,
                args.board,
                args.region,
                "Public posting details do not accept pagination; no request made.",
            )
        else:
            result = read_detail(args.source, args.board, args.job_id, region=args.region)
    else:
        result = read_board(
            args.source, args.board, region=args.region, skip=args.skip, limit=args.limit
        )
    json.dump(result, sys.stdout, ensure_ascii=False, allow_nan=False)
    sys.stdout.write("\n")
    return 2 if result.get("status") == "source_limited" else 0


if __name__ == "__main__":
    raise SystemExit(main())
