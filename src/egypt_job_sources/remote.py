"""Broad, read-only remote-job feeds with source-scoped transport and honest limits.

These adapters acquire every item returned by an official public endpoint. They
do not filter by a candidate, title, keyword, salary, or employment family. A
source snapshot or cursor page is never evidence of complete market coverage.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lxml import etree

MAX_BYTES = 25 * 1024 * 1024
TIMEOUT_SECONDS = 35
SOURCES = {
    "remotive": "https://remotive.com/api/remote-jobs",
    "remoteok": "https://remoteok.com/api",
    "weworkremotely": "https://weworkremotely.com/remote-jobs.rss",
    "workingnomads": "https://www.workingnomads.com/api/exposed_jobs/",
    "himalayas_global": "https://himalayas.app/jobs/api",
}
SOURCE_NAMES = {
    "remotive": "Remotive",
    "remoteok": "Remote OK",
    "weworkremotely": "We Work Remotely",
    "workingnomads": "Working Nomads",
    "himalayas_global": "Himalayas",
}
DOCUMENTATION = {
    "remotive": "https://github.com/remotive-com/remote-jobs-api",
    "remoteok": "https://remoteok.com/api",
    "weworkremotely": "https://weworkremotely.com/remote-job-rss-feed",
    "workingnomads": "https://www.workingnomads.com/jobs",
    "himalayas_global": "https://himalayas.app/api",
}
LIMITS = {
    "remotive": [
        "Current public snapshot, delayed by 24 hours; not complete historical supply.",
        "Remotive advises at most four fresh feed fetches per day; excessive polling is blocked.",
        "Preserve source attribution and canonical links; no third-party aggregator export or signup gating.",
        "The endpoint's returned counts describe its exposed feed, not every paid/private listing.",
    ],
    "remoteok": [
        "Current public snapshot; no verified historical or continuation contract.",
        "The live feed contains a bounded recent set; no total market count is exposed.",
        "Descriptions can be abbreviated; validate the employer's full posting before review.",
        "Retain the Remote OK name and followable canonical links; logo use needs permission.",
    ],
    "weworkremotely": [
        "Official all-category RSS snapshot; no verified historical pagination contract.",
        "RSS description is source content, not independently verified employer full text.",
        "Preserve attribution and links to We Work Remotely.",
    ],
    "workingnomads": [
        "Official footer-linked exposed-jobs API; no verified total or pagination contract.",
        "Public exposed subset does not include the complete subscription inventory.",
        "Description completeness, exact hours, geography and current employer availability need review.",
        "Source terms restrict commercial exploitation and competitive services; code licensing does not license job data.",
    ],
    "himalayas_global": [
        "Broad current feed with source cursor pagination, at most 20 jobs per response.",
        "Preserve each returned nextCursor; never derive offsets or claim completion after one page.",
        "Data refreshes daily; source cursor continuity and totals are not a frozen historical census.",
        "Preserve Himalayas attribution and canonical links; no third-party aggregator export.",
        "Salary amounts use salaryPeriod and currency; never assume every amount is annual or USD.",
    ],
}
_CURSOR = re.compile(r"[A-Za-z0-9+/=_-]{1,4096}\Z")


def endpoint(source: str, cursor: str | None = None) -> str:
    """Construct only an official, unfiltered endpoint; cursor is opaque data."""
    if source not in SOURCES:
        raise ValueError("Unsupported remote source")
    if cursor is not None and source != "himalayas_global":
        raise ValueError("Only the Himalayas full feed accepts a cursor")
    if cursor is not None and (not isinstance(cursor, str) or not _CURSOR.fullmatch(cursor)):
        raise ValueError("Invalid opaque source cursor")
    if source == "himalayas_global":
        params = {"limit": 20}
        if cursor is not None:
            params["cursor"] = cursor
        return SOURCES[source] + "?" + urlencode(params)
    return SOURCES[source]


def validate_endpoint(url: str) -> str:
    """Reject arbitrary hosts, details, credentials, filters, ports and fragments."""
    if not isinstance(url, str):
        raise ValueError("Invalid endpoint")
    for source in SOURCES:
        if url == endpoint(source):
            return url
    parts = urlsplit(url)
    base = urlsplit(SOURCES["himalayas_global"])
    if (
        parts.scheme != "https"
        or parts.netloc != base.netloc
        or parts.path != base.path
        or parts.fragment
    ):
        raise ValueError("Endpoint outside the fixed public feed scope")
    params = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    if set(params) != {"limit", "cursor"} or any(len(v) != 1 for v in params.values()):
        raise ValueError("Only the returned cursor and fixed page size are allowed")
    if params["limit"] != ["20"] or url != endpoint("himalayas_global", params["cursor"][0]):
        raise ValueError("Invalid canonical feed endpoint")
    return url


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Feed redirects are refused", headers, fp)


def read(url: str) -> bytes:
    """One anonymous GET with no cookies, credentials, proxy rotation or redirect."""
    validate_endpoint(url)
    request = Request(
        url,
        headers={
            "User-Agent": "EgyptJobSources/0.2 (+https://github.com/ahmed-elkashef/egypt-job-sources)",
            "Accept": "application/json, application/rss+xml, application/xml, text/xml",
            "Accept-Encoding": "identity",
        },
    )
    with build_opener(NoRedirects()).open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Unexpected response status or endpoint")
        declared = response.headers.get("Content-Length")
        if declared is not None and (not declared.isdigit() or int(declared) > MAX_BYTES):
            raise ValueError("Feed response exceeds the byte limit or has invalid length")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Feed response exceeds the byte limit")
        return body


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _json(body: bytes | str):
    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")

    return json.loads(body, object_pairs_hook=_object, parse_constant=invalid_constant)


def _count(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid {label}")
    return value


def _string(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid {label}")
    return value


def _identity(value) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Invalid source identifier")
    return _string(str(value), "source identifier")


def _listing_url(value, source: str) -> str | None:
    value = _string(value, "canonical source URL")
    if any(ord(character) < 33 or ord(character) == 127 for character in value):
        raise ValueError("Invalid canonical source URL")
    parts = urlsplit(value)
    hosts = {
        "remotive": {"remotive.com"},
        "remoteok": {"remoteok.com"},
        "weworkremotely": {"weworkremotely.com"},
        "workingnomads": {"workingnomads.com", "www.workingnomads.com"},
        "himalayas_global": {"himalayas.app"},
    }
    if (
        parts.scheme != "https"
        or parts.hostname not in hosts[source]
        or parts.username is not None
        or parts.password is not None
        or parts.port is not None
        or parts.fragment
        or parts.query
    ):
        raise ValueError("Invalid canonical source URL")
    # A Remote OK item can carry only the source index, despite retaining its
    # native ID and description. Preserve that item without inventing a detail.
    if source == "remoteok" and parts.path == "/remote-jobs/":
        return None
    prefix = "/jobs/" if source in {"workingnomads", "himalayas_global"} else "/remote-jobs/"
    valid_path = parts.path.startswith(prefix) and parts.path != prefix
    slug = r"[A-Za-z0-9][A-Za-z0-9_-]*"
    if source == "remoteok":
        valid_path = re.fullmatch(rf"/remote-jobs/{slug}/?", parts.path) is not None
    if source == "workingnomads":
        # Official exposed_jobs returns these native redirect links. Retain the
        # link as data; the feed reader never resolves it or fetches applications.
        valid_path = re.fullmatch(rf"/jobs/{slug}/?", parts.path) is not None
        valid_path |= re.fullmatch(r"/job/go/[1-9][0-9]*/", parts.path) is not None
    elif source == "himalayas_global":
        valid_path = re.fullmatch(rf"/jobs/{slug}/?", parts.path) is not None
        valid_path |= re.fullmatch(rf"/companies/{slug}/jobs/{slug}/?", parts.path) is not None
    if not valid_path:
        raise ValueError("Invalid canonical source URL")
    return value


def _listing(row: dict, source: str, *, identity, url, title, description) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Invalid feed item")
    canonical = _listing_url(url, source)
    link_scope = "source_posting"
    url_basis = "source_native_posting_link"
    if canonical is None:
        link_scope, url_basis = "source_index", "source_index_only_not_exact_posting"
    elif source == "workingnomads" and urlsplit(canonical).path.startswith("/job/go/"):
        link_scope, url_basis = "source_redirect", "source_native_redirect_link_not_resolved"
    return {
        "id": _identity(identity),
        "url": canonical,
        "url_basis": url_basis,
        "gates": ["canonical_posting_url_missing"] if canonical is None else [],
        "title": _string(title, "title"),
        "description": _string(description, "source description"),
        "source": source,
        "attribution": {
            "source": SOURCE_NAMES[source],
            "url": url if canonical is None else canonical,
            "link_scope": link_scope,
        },
        "source_data": row,
        "description_basis": (
            "source_full_html_field_not_independently_reviewed"
            if source in {"remotive", "himalayas_global"}
            else "source_description_field_completeness_unverified"
        ),
    }


def _rss(body: bytes | str) -> tuple[list[dict], dict]:
    raw = body.encode("utf-8") if isinstance(body, str) else body
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I):
        raise ValueError("RSS document declarations/entities are refused")
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    root = etree.fromstring(raw, parser=parser)
    # XML can declare UTF-16/UTF-32, bypassing an ASCII byte precheck. libxml
    # still reports the declaration without resolving its entities or network.
    if root.getroottree().docinfo.doctype:
        raise ValueError("RSS document declarations/entities are refused")
    if root.tag != "rss" or len(root.findall("channel")) != 1:
        raise ValueError("Unexpected RSS structure")
    channel = root.find("channel")
    items = channel.findall("item")
    if not items:
        raise ValueError("RSS has no job items; metadata alone cannot prove zero supply")
    rows = []
    for item in items:
        row = {}
        attributes = {}
        for child in item:
            key = child.tag
            value = child.text or ""
            if len(child):
                value += "".join(etree.tostring(n, encoding="unicode") for n in child)
            if child.attrib:
                attributes.setdefault(key, []).append(dict(child.attrib))
            if key in row:
                previous = row[key]
                row[key] = [*previous, value] if isinstance(previous, list) else [previous, value]
            else:
                row[key] = value
        if attributes:
            row["rss_attributes"] = attributes
        rows.append(
            _listing(
                row,
                "weworkremotely",
                identity=row.get("guid"),
                url=row.get("link"),
                title=row.get("title"),
                description=row.get("description"),
            )
        )
    metadata = {child.tag: child.text for child in channel if child.tag != "item"}
    return rows, metadata


def parse_snapshot(source: str, body: bytes | str, cursor: str | None = None) -> dict:
    """Validate an entire source response and preserve all returned jobs and fields."""
    endpoint(source, cursor)
    if not isinstance(body, (bytes, str)):
        raise ValueError("Invalid or oversized response body")
    body_size = len(body.encode("utf-8")) if isinstance(body, str) else len(body)
    if body_size > MAX_BYTES:
        raise ValueError("Invalid or oversized response body")
    metadata = {}
    next_cursor = None
    reported_total = None
    if source == "weworkremotely":
        listings, metadata = _rss(body)
    else:
        data = _json(body)
        if source in {"remotive", "himalayas_global"}:
            if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
                raise ValueError("Expected jobs array absent")
            rows = data["jobs"]
            metadata = {key: value for key, value in data.items() if key != "jobs"}
            if source == "remotive":
                if _count(data.get("job-count"), "returned count") != len(rows):
                    raise ValueError("Returned count does not match jobs")
                if "total-job-count" in data:
                    reported_total = _count(data["total-job-count"], "total count")
                    if reported_total < len(rows):
                        raise ValueError("Total count is smaller than returned jobs")
            else:
                reported_total = _count(data.get("totalCount"), "total count")
                limit = _count(data.get("limit"), "page size")
                if limit != 20 or len(rows) > limit or reported_total < len(rows):
                    raise ValueError("Unexpected page size or count")
                if "nextCursor" not in data:
                    raise ValueError("Cursor continuation field is absent")
                next_cursor = data["nextCursor"]
                if cursor is None and not rows and reported_total > 0:
                    raise ValueError("Initial feed is empty despite a positive total")
                if next_cursor is not None:
                    endpoint(source, next_cursor)
                    if next_cursor == cursor or not rows:
                        raise ValueError("Cursor did not advance or empty page claims continuation")
        elif source == "remoteok":
            if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                raise ValueError("Expected legal metadata followed by job items")
            metadata = data[0]
            _string(metadata.get("legal"), "source legal terms")
            if "id" in metadata or "position" in metadata:
                raise ValueError("Remote OK legal metadata structure changed")
            rows = data[1:]
            if not rows:
                raise ValueError("Legal metadata alone cannot prove zero supply")
        else:
            if not isinstance(data, list) or not data:
                raise ValueError("Expected nonempty exposed-jobs array")
            rows = data
        listings = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Non-object feed item")
            if source == "remotive":
                identity, url, title = row.get("id"), row.get("url"), row.get("title")
            elif source == "remoteok":
                identity, url, title = row.get("id"), row.get("url"), row.get("position")
            elif source == "workingnomads":
                identity, url, title = row.get("url"), row.get("url"), row.get("title")
            else:
                identity, url, title = row.get("guid"), row.get("guid"), row.get("title")
            listings.append(
                _listing(
                    row,
                    source,
                    identity=identity,
                    url=url,
                    title=title,
                    description=row.get("description"),
                )
            )
    identifiers = [row["id"] for row in listings]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate source identifiers in one response")
    return {
        "listings": listings,
        "returned_count": len(listings),
        "reported_total": reported_total,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None if source == "himalayas_global" else None,
        "continuation_basis": (
            "official_nextCursor"
            if source == "himalayas_global"
            else "snapshot_no_verified_pagination"
        ),
        "source_metadata": metadata,
        "date_basis": "raw_source_timestamps_preserved; timezone_and_frozen_interval_not_reconciled",
        "limits": LIMITS[source],
    }


def capabilities() -> dict:
    return {
        "status": "ok",
        "sources": [
            {
                "source": source,
                "endpoint": endpoint(source),
                "documentation": DOCUMENTATION[source],
                "requires_credentials": False,
                "cursor_supported": source == "himalayas_global",
                "limits": LIMITS[source],
            }
            for source in SOURCES
        ],
        "coverage_complete": False,
        "reviewed_by_model": False,
    }


def query(source: str, cursor: str | None = None, fetch=None) -> dict:
    result = {
        "source": source,
        "status": "source_limited",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "coverage_complete": False,
        "reviewed_by_model": False,
    }
    try:
        url = endpoint(source, cursor)
        result["url"] = url
        body = (fetch or read)(url)
        result.update(parse_snapshot(source, body, cursor), status="ok")
    except HTTPError as exc:
        result["error"] = f"HTTP {exc.code}; public source access limited"
    except Exception as exc:
        # Transport exceptions can include URLs or server text. Keep them local;
        # the public result exposes only safe diagnostic types and known messages.
        result["error"] = (
            "Source response or arguments failed validation"
            if isinstance(exc, ValueError)
            else type(exc).__name__
        )
        result["error_type"] = type(exc).__name__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", choices=list(SOURCES))
    parser.add_argument("--cursor")
    parser.add_argument("--capabilities", action="store_true")
    args = parser.parse_args()
    if args.capabilities:
        if args.source or args.cursor:
            parser.error("--capabilities cannot be combined with source or cursor")
        result = capabilities()
    elif args.source:
        result = query(args.source, args.cursor)
    else:
        parser.error("source or --capabilities is required")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
