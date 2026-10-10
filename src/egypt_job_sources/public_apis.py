"""Complete public API pages for Arbeitnow and The Muse, with no job filters.

Unlike summary wrappers, these adapters preserve each native HTML body. The Muse
requires app registration beyond testing; anonymous live calls are test-only.
No page constitutes a historical census or an individual model review.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener

from .remote import MAX_BYTES, TIMEOUT_SECONDS, NoRedirects, _count, _identity, _json, _string

BASES = {
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
    "themuse": "https://www.themuse.com/api/public/jobs",
}
DOCS = {
    "arbeitnow": "https://www.arbeitnow.com/blog/job-board-api",
    "themuse": "https://www.themuse.com/developers/api/v2",
}


def endpoint(source: str, page: int | None = None) -> str:
    if source not in BASES:
        raise ValueError("Unsupported public API source")
    if page is None:
        page = 0 if source == "themuse" else 1
    page = _count(page, "page")
    if source == "arbeitnow" and page < 1:
        raise ValueError("Arbeitnow pages begin at one")
    return BASES[source] + "?" + urlencode({"page": page})


def validate_endpoint(source: str, url: str) -> tuple[str, int]:
    if source not in BASES or not isinstance(url, str):
        raise ValueError("Unsupported public API source or endpoint")
    parts, base = urlsplit(url), urlsplit(BASES[source])
    if (
        parts.scheme != "https"
        or parts.netloc != base.netloc
        or parts.path != base.path
        or parts.fragment
        or parts.username
        or parts.password
        or parts.port
    ):
        raise ValueError("URL outside the fixed public API scope")
    query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    if not parts.query and source == "arbeitnow":
        return url, 1
    if set(query) != {"page"} or len(query["page"]) != 1:
        raise ValueError("Only a source page is permitted")
    value = query["page"][0]
    if not value.isascii() or not value.isdigit():
        raise ValueError("Invalid source page")
    page = int(value)
    if url != endpoint(source, page):
        raise ValueError("Noncanonical source page")
    return url, page


def _posting_url(source: str, value) -> str:
    value = _string(value, "native posting URL")
    parts = urlsplit(value)
    # The official Germany feed also returns the footer-linked UK, France and
    # Switzerland sister sites. Preserve these actual native posting URLs.
    hosts = (
        {"www.arbeitnow.com", "www.arbeitnow.co.uk", "www.arbeitnow.fr", "www.arbeitnow.ch"}
        if source == "arbeitnow"
        else {"www.themuse.com"}
    )
    if (
        parts.scheme != "https"
        or parts.netloc not in hosts
        or parts.username
        or parts.password
        or parts.port
        or parts.fragment
        or parts.query
        or not parts.path.startswith("/jobs/")
        or parts.path == "/jobs/"
        or any(ord(c) < 33 or ord(c) == 127 for c in value)
    ):
        raise ValueError("Invalid native posting URL")
    return value


def parse_page(source: str, body: bytes | str, request_url: str) -> dict:
    _, requested_page = validate_endpoint(source, request_url)
    data = _json(body)
    if not isinstance(data, dict):
        raise ValueError("Expected native page object")
    rows = data.get("data" if source == "arbeitnow" else "results")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Expected native listing array")
    if source == "arbeitnow":
        links, meta = data.get("links"), data.get("meta")
        if not isinstance(links, dict) or "next" not in links or not isinstance(meta, dict):
            raise ValueError("Missing Arbeitnow continuation metadata")
        current = _count(meta.get("current_page"), "current page")
        if current != requested_page:
            raise ValueError("Response page does not match request")
        next_url = links["next"]
        if next_url is not None:
            _, next_page = validate_endpoint(source, next_url)
            if next_page <= current or not rows:
                raise ValueError("Stalled or empty nonterminal page")
        native_total = meta.get("total")
        if native_total is not None:
            native_total = _count(native_total, "native total")
        publication_field = "created_at"
    else:
        current = _count(data.get("page"), "current page")
        page_count = _count(data.get("page_count"), "page count")
        if current != requested_page:
            raise ValueError("Response page does not match request")
        if len(rows) > 20:
            raise ValueError("The Muse exceeded its documented twenty-result page")
        if rows and current >= page_count:
            raise ValueError("Nonempty page outside reported page range")
        if not rows and current < page_count:
            raise ValueError("Empty page inside reported page range")
        # The official contract defines zero-based page/page_count pagination.
        next_url = endpoint(source, current + 1) if current + 1 < page_count else None
        native_total = data.get("total")
        if native_total is not None:
            native_total = _count(native_total, "native total")
        publication_field = "publication_date"
    listings = []
    for row in rows:
        identity = row.get("slug" if source == "arbeitnow" else "id")
        refs = row.get("refs") or {}
        url = row.get("url") if source == "arbeitnow" else refs.get("landing_page")
        title = row.get("title" if source == "arbeitnow" else "name")
        description = row.get("description" if source == "arbeitnow" else "contents")
        native_body_field = "description" if source == "arbeitnow" else "contents"
        listings.append(
            {
                "id": _identity(identity),
                "source": source,
                "url": _posting_url(source, url),
                "title": _string(title, "native title"),
                "description": _string(description, "complete native description"),
                # Retain the complete native HTML once rather than serializing it
                # twice. Original fields can be reconstructed exactly by adding
                # description under source_description_field to source_data.
                "source_data": {
                    key: value for key, value in row.items() if key != native_body_field
                },
                "source_description_field": native_body_field,
                "publication_raw": row.get(publication_field),
                "publication_basis": "native_field_not_observation; original_creation_semantics_need_validation",
                "description_basis": "complete_native_HTML_field_preserved_without_clipping_not_model_read",
                "attribution": {
                    "source": "Arbeitnow" if source == "arbeitnow" else "The Muse",
                    "url": url,
                    "link_scope": "source_posting",
                },
            }
        )
    if len({row["id"] for row in listings}) != len(listings):
        raise ValueError("Repeated identity within one native page")
    return {
        "source": source,
        "status": "ok",
        "request_url": request_url,
        "page": current,
        "next_url": next_url,
        "has_more": next_url is not None,
        "pagination_links": data.get("links") if source == "arbeitnow" else None,
        "pagination": data.get("meta")
        if source == "arbeitnow"
        else {"page": current, "page_count": data["page_count"], "basis": "documented_zero_based"},
        "reported_total": native_total,
        "returned_count": len(listings),
        "listings": listings,
        "coverage_complete": False,
        "reviewed_by_model": False,
        "documentation": DOCS[source],
        "limits": [
            "Moving public API pages are not a frozen historical census.",
            "Preserve native bodies and dates; country and part-time fit need separate screening.",
            "The Muse ranking is not chronological; no publication-date stopping boundary is proved."
            if source == "themuse"
            else "Remote metadata does not prove worldwide worker eligibility.",
            "The Muse requires registered app access beyond testing; 500 anonymous tests/hour, 3600 registered/hour."
            if source == "themuse"
            else "No official numeric rate limit is established; stop on access/rate errors.",
        ],
    }


def read(source: str, url: str, *, testing: bool = False, api_key: str | None = None) -> bytes:
    """One scope-checked GET. A Muse key is never included in returned metadata/errors."""
    validate_endpoint(source, url)
    if source == "themuse" and not testing and not api_key:
        raise ValueError("The Muse requires app registration beyond testing")
    if api_key and source != "themuse":
        raise ValueError("Arbeitnow does not require credentials")
    transport_url = url + "&" + urlencode({"api_key": api_key}) if api_key else url
    request = Request(
        transport_url,
        headers={
            "User-Agent": "EgyptJobSources (+https://github.com/ahmed-elkashef/egypt-job-sources)",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with build_opener(NoRedirects()).open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != transport_url:
                raise ValueError("Unexpected source status or redirect")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or int(length) > MAX_BYTES):
                raise ValueError("Invalid or oversized source response")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("Oversized source response")
            return body
    except HTTPError as exc:
        # urllib exceptions embed URLs; strip the credential-bearing transport URL.
        raise HTTPError(
            url, exc.code, "Public API refused the request", exc.headers, exc.fp
        ) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=BASES)
    parser.add_argument("--page", type=int)
    parser.add_argument("--next-url", help="Echo only the returned native continuation URL")
    parser.add_argument("--testing", action="store_true", help="The Muse anonymous live test only")
    args = parser.parse_args()
    if args.page is not None and args.next_url is not None:
        parser.error("Choose page or returned next URL")
    url = args.next_url or endpoint(args.source, args.page)
    try:
        body = read(
            args.source,
            url,
            testing=args.testing,
            api_key=os.environ.get("THEMUSE_API_KEY") if args.source == "themuse" else None,
        )
        result = parse_page(args.source, body, url)
        result["retrieved_at"] = datetime.now(timezone.utc).isoformat()
        result["access_scope"] = (
            "registered_app"
            if args.source == "themuse" and os.environ.get("THEMUSE_API_KEY")
            else "anonymous_test_only"
            if args.source == "themuse"
            else "official_public_API"
        )
    except Exception as exc:
        # Never stringify arbitrary transport errors that may include credentials.
        safe_headers = {}
        if isinstance(exc, HTTPError):
            for key in (
                "Retry-After",
                "Date",
                "RateLimit-Limit",
                "RateLimit-Remaining",
                "RateLimit-Reset",
            ):
                value = exc.headers.get(key) if exc.headers else None
                if value is not None:
                    safe_headers[key] = value
        result = {
            "source": args.source,
            "status": "source_limited",
            "error_type": type(exc).__name__,
            "http_status": exc.code if isinstance(exc, HTTPError) else None,
            "safe_response_headers": safe_headers,
            "coverage_complete": False,
            "reviewed_by_model": False,
        }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
