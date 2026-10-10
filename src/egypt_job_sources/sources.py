#!/usr/bin/env python3
"""Read-only, paginated public source access for the Egypt market package.

No title, keyword, role or seniority argument is exposed. A page is evidence,
never a completed market census. HTTP/parse failures are not zero results.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lxml import html

from . import wuzzuf as wuzzuf_api
from .boards import (
    BOARD_URLS,
    board_page_url,
    clean_text,
    filter_signature,
    parse_board_detail,
    parse_board_page,
    source_id,
    validate_board_url,
)
from .mostaql import canonical_project_url, parse_mostaql_detail

SOURCES = {
    **BOARD_URLS,
    "bayt": "https://www.bayt.com/en/egypt/jobs/",
    "himalayas": "https://himalayas.app/jobs/api/search",
    "jobicy": "https://jobicy.com/api/v2/remote-jobs",
    "mostaql": "https://mostaql.com/projects",
}


def page_url(
    source: str, page: int = 1, cursor: str | None = None, work_model: str | None = None
) -> str:
    if source not in SOURCES or not 1 <= page <= 10000:
        raise ValueError("Unsupported source or invalid page")
    if source != "jobicy" and cursor is not None:
        raise ValueError("Only Jobicy accepts an opaque cursor")
    if source in BOARD_URLS:
        return board_page_url(source, page, work_model)
    if work_model:
        raise ValueError("Source does not support this verified native work-model argument")
    if source == "jobicy" and page != 1:
        raise ValueError("Jobicy uses returned cursors, not numbered pages")
    # Broad country inventory; do not impose candidate-specific employment filters.
    params = (
        {
            "country": "EG",
            "sort": "recent",
            "page": page,
        }
        if source == "himalayas"
        else {"page": page}
    )
    if source == "jobicy":
        params = {"count": 200}
        if cursor:
            params["cursor"] = cursor
    if source in {"bayt", "mostaql"} and page == 1:
        return SOURCES[source]
    return SOURCES[source] + "?" + urlencode(params)


def text(node) -> str:
    return clean_text(node)


def parse_page(source: str, body: str, url: str) -> dict:
    if source in BOARD_URLS:
        return parse_board_page(source, body, url)
    if source in {"himalayas", "jobicy"}:
        data = json.loads(body)
        if not isinstance(data.get("jobs"), list) or data.get("success") is False:
            raise ValueError("Source response has no valid jobs array")
        jobs = data["jobs"]
        cursor = data.get("nextCursor")
        if source == "jobicy" and data.get("hasMore") is True and not cursor:
            raise ValueError("Source reports more jobs without a continuation cursor")
        # Preserve original fields, full HTML descriptions and exact restrictions.
        # Empty restrictions are uncertain, not automatically Egypt-eligible.
        return {
            "listings": jobs,
            "next_cursor": cursor,
            "has_more": data.get("hasMore"),
            "reported_total": data.get("totalCount"),
            "returned_offset": data.get("offset"),
            "returned_limit": data.get("limit"),
            "applied_filters": data.get("appliedFilters"),
            "description_basis": "source_full_description_field_not_yet_reviewed",
            "date_basis": "source_pubDate_timezone_and_original_publication_unverified",
            "limits": [
                "Public Jobicy feed is a moving seven-day window; older missed supply unavailable.",
                "Jobicy Fair Use permits fresh polling no more than hourly; cursor pages within one pass are permitted.",
            ]
            if source == "jobicy"
            else [
                "Country result may include worldwide listings; verify each description and time zone.",
                "Preserve Himalayas attribution and canonical links; do not export jobs to third-party listing aggregators.",
            ],
        }
    doc = html.fromstring(body)
    cards = (
        doc.xpath("//li[@data-js-job]")
        if source == "bayt"
        else doc.xpath('//h2[a[contains(@href,"/project/")]]')
    )
    if not cards:
        raise ValueError("Expected listing structure absent; cannot infer zero results")
    listings = []
    for card in cards:
        if source == "bayt":
            anchors = card.xpath('.//a[@data-js-aid="jobID"]')
            if not anchors:
                raise ValueError("Bayt card lacks a canonical detail link")
            a = anchors[0]
            dates = card.xpath(
                ".//*[@data-automation-jobactivedate]/@data-automation-jobactivedate"
            )
            locations = card.xpath('.//*[contains(@class,"jb-label-location")]')
            listings.append(
                {
                    "id": card.get("data-job-id"),
                    "title": text(a),
                    "url": urljoin(url, a.get("href")),
                    "card_text": text(card),
                    "location": text(locations[0]) if locations else None,
                    "source_activity_epoch": dates[0] if dates else None,
                }
            )
        else:
            a = card.xpath("./a")[0]
            parent = card.getparent()
            dates = parent.xpath(".//time/@datetime")
            listings.append(
                {
                    "id": re.search(r"/project/(\d+)", a.get("href")).group(1),
                    "title": text(a),
                    "url": a.get("href"),
                    "card_text": text(parent),
                    "source_date_without_offset": dates[0] if dates else None,
                }
            )
    page_links = []
    for a in doc.xpath("//a[@href]"):
        href = urljoin(url, a.get("href"))
        if urlsplit(href).hostname == urlsplit(url).hostname and re.search(r"[?&]page=\d+", href):
            page_links.append({"text": text(a), "url": href})
    return {
        "listings": listings,
        "pagination_links": page_links,
        "description_basis": "listing_card_only_full_detail_required",
        "date_basis": "active_or_updated_epoch_not_original_publication"
        if source == "bayt"
        else "source_datetime_no_offset_timezone_unverified",
        "limits": [
            "Live pagination may drift; deduplicate stable IDs and reconcile source totals.",
            "Card summaries are not full descriptions.",
        ],
    }


def detail_url(source: str, url: str) -> str:
    if source in BOARD_URLS:
        return validate_board_url(source, url, detail=True)
    if source == "mostaql":
        return canonical_project_url(url)[0]
    parts = urlsplit(url)
    allowed = (
        source == "bayt"
        and parts.hostname == "www.bayt.com"
        and re.fullmatch(r"/en/egypt/jobs/[^/]+-\d+/", parts.path)
    ) or (
        source == "mostaql"
        and parts.hostname == "mostaql.com"
        and re.match(r"^/project/\d+-", parts.path)
    )
    if (
        not allowed
        or parts.scheme != "https"
        or parts.query
        or parts.fragment
        or parts.username is not None
        or parts.password is not None
        or parts.port
    ):
        raise ValueError("Only canonical public detail URLs on the selected source are allowed")
    return url


def parse_detail(source: str, body: str, url: str | None = None) -> dict:
    if source in BOARD_URLS:
        return parse_board_detail(source, body, url)
    if source == "mostaql":
        return parse_mostaql_detail(body, url)
    doc = html.fromstring(body)
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
        except json.JSONDecodeError:
            continue
    if source == "bayt" and postings:
        posting = postings[0]
        if not str(posting.get("description", "")).strip():
            raise ValueError("JobPosting description absent")
        return {
            "posting": posting,
            "description_basis": "source_JobPosting_description_not_yet_reviewed",
            "date_basis": "JobPosting_datePosted_verify_source_semantics",
        }
    raise ValueError("Full description structure not verified")


class SourceFailure(RuntimeError):
    pass


def allowed_source_redirect(original_url, target_url):
    original, target = urlsplit(original_url), urlsplit(target_url)
    if (
        target.scheme != "https"
        or target.hostname != original.hostname
        or target.username is not None
        or target.password is not None
        or target.port is not None
        or target.fragment
    ):
        return False
    if (target.path, target.query) == (original.path, original.query):
        return True
    # ArabJobs canonicalizes the country/slug order. Only an unchanged public
    # detail identity may follow that alias; search filters must never drift.
    try:
        validate_board_url("arabjobs", original_url, detail=True)
        validate_board_url("arabjobs", target_url, detail=True)
        return source_id("arabjobs", original_url) == source_id("arabjobs", target_url)
    except ValueError:
        return False


class SameHostRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_source_redirect(req.full_url, newurl):
            raise SourceFailure(
                "Source URL changed during redirect; verify canonical route in browser"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "egypt-job-sources/0.1.0",
            "Accept": "application/json,text/html",
        },
    )
    with build_opener(SameHostRedirects()).open(request, timeout=35) as response:
        # Redirects cannot be used to turn the connector into a general fetcher.
        if not allowed_source_redirect(url, response.url):
            raise SourceFailure("Response URL changed; source scope must be verified")
        body = response.read(8_000_001)
        if len(body) > 8_000_000:
            raise SourceFailure("Response exceeds safety limit; record source limitation")
        return body.decode("utf-8")


def query(
    source: str,
    page: int = 1,
    cursor: str | None = None,
    url: str | None = None,
    taxonomy: bool = False,
    work_model: str | None = None,
    continuation_url: str | None = None,
) -> dict:
    if taxonomy and (source not in {"jobicy", "wuzzuf"} or url or continuation_url):
        raise ValueError(
            "Only Jobicy/WUZZUF taxonomy requests without detail/continuation are supported"
        )
    if cursor is not None and source != "jobicy":
        raise ValueError("Only Jobicy accepts an opaque cursor")
    requested = (
        detail_url(source, url)
        if url
        else (
            SOURCES["jobicy"] + "?get=locations"
            if taxonomy and source == "jobicy"
            else validate_board_url(source, continuation_url)
            if continuation_url
            else page_url(source, page, cursor, work_model)
        )
    )
    if source == "wuzzuf":
        if taxonomy:
            result = wuzzuf_api.base_result(wuzzuf_api.public_page_url())
            try:
                result.update(wuzzuf_api.query_taxonomy(), status="ok")
            except Exception as exc:
                result.update(
                    status="source_limited", error=f"{type(exc).__name__}: {str(exc)[:300]}"
                )
            return result
        if url:
            return wuzzuf_api.query_detail(requested)
        if continuation_url:
            params = parse_qs(urlsplit(requested).query)
            observed_model = params.get("filters[job_types][0]", [None])[0]
            if work_model and wuzzuf_api.model_name(work_model) != observed_model:
                raise ValueError("Continuation work model disagrees with requested partition")
            page = int(params.get("start", ["0"])[0]) + 1
            work_model = observed_model
        result = wuzzuf_api.query_page(page, work_model)
        result["requested_url"] = requested
        return result
    result = {
        "source": source,
        "requested_url": requested,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "coverage_complete": False,
        "reviewed_by_model": False,
    }
    try:
        body = read(requested)
        data = (
            json.loads(body)
            if taxonomy
            else parse_detail(source, body, requested)
            if url
            else parse_page(source, body, requested)
        )
        result.update(data)
        result["status"] = "ok"
    except Exception as exc:
        result.update(status="source_limited", error=f"{type(exc).__name__}: {str(exc)[:300]}")
        # No listings: [] here: failures must not resemble an exhausted source.
    return result


def parse_browser_capture(source: str, capture: dict) -> dict:
    """Parse selected public DOM sections acquired through the authorized browser.

    This function makes no network request and does not control a browser.
    Captures are operator evidence, not independent proof of their provenance.
    """
    result = {
        "source": source,
        "coverage_complete": False,
        "reviewed_by_model": False,
        "transport": "operator_authorized_browser_dom",
        "provenance": "operator_supplied_capture",
    }
    try:
        if not isinstance(capture, dict) or set(capture) != {"url", "kind", "captured_at", "html"}:
            raise ValueError(
                "Exactly the public URL, capture kind, timestamp and selected DOM HTML are required"
            )
        kind = capture["kind"]
        if kind not in {"page", "detail"}:
            raise ValueError("Capture kind must be page or detail")
        url = validate_board_url(source, capture["url"], detail=kind == "detail")
        observed = datetime.fromisoformat(capture["captured_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("Browser capture timestamp requires a UTC offset")
        body = capture["html"]
        if not isinstance(body, str) or len(body.encode()) > 8_000_000:
            raise ValueError("Browser capture must contain bounded public HTML")
        result.update(requested_url=url, observed_at=observed.isoformat())
        result.update(
            parse_detail(source, body, url) if kind == "detail" else parse_page(source, body, url)
        )
        if source == "forasna" and kind == "page":
            result["limits"].append(
                "Hydrated UI clicks advanced by 30 while hrefs advertised 20-step offsets on 2026-10-09; do not use href arithmetic as browser continuation."
            )
        result["status"] = "ok"
    except Exception as exc:
        result.update(status="source_limited", error=f"{type(exc).__name__}: {str(exc)[:300]}")
    return result


def crawl_board(source, max_pages=2, work_model=None, fetch=None, delay=1.0):
    """Bounded sequential probe using observed next links, with explicit stops.

    A capped probe never claims interval coverage. Save its response as a local
    checkpoint if needed; reconcile complete inventory separately.
    """
    if source not in BOARD_URLS or not 1 <= max_pages <= 1000:
        raise ValueError("Board and explicit page cap required")
    fetch = fetch or (lambda url: query(source, continuation_url=url))
    url = board_page_url(source, work_model=work_model)
    signature = filter_signature(source, url)
    pages, listings, fingerprints, visited = [], {}, set(), set()
    source_totals = []
    native_terminal_verified = False
    duplicate_count = 0
    stop = "page_cap"
    for _ in range(max_pages):
        if url in visited:
            stop = "pagination_loop"
            break
        if filter_signature(source, url) != signature:
            stop = "filter_drift"
            break
        visited.add(url)
        response = fetch(url)
        pages.append(response)
        if response.get("status") != "ok":
            stop = "source_limited"
            break
        # A response belongs to the requested page, including under test transports.
        if response.get("requested_url") != url:
            stop = "unexpected_page_response"
            break
        fingerprint = response.get("page_fingerprint")
        if not fingerprint or fingerprint in fingerprints:
            stop = "repeated_or_unverified_page"
            break
        fingerprints.add(fingerprint)
        source_total = response.get("reported_total")
        if source_total is not None:
            source_totals.append(source_total)
            if len(set(source_totals)) != 1:
                stop = "source_total_drift"
                break
        new_ids = 0
        for job in response["listings"]:
            if job["id"] in listings:
                duplicate_count += 1
            else:
                listings[job["id"]] = job
                new_ids += 1
        if not new_ids and not (
            source == "wuzzuf" and source_total == 0 and response.get("has_more") is False
        ):
            stop = "no_new_ids"
            break
        url = response.get("next_url")
        if not url:
            if source == "wuzzuf" and response.get("has_more") is False:
                native_terminal_verified = len(listings) == source_total
                stop = (
                    "source_terminal_count_verified"
                    if native_terminal_verified
                    else "terminal_count_mismatch"
                )
            else:
                stop = "no_observed_continuation_operator_must_reconcile"
            break
        if delay:
            time.sleep(delay)
    return {
        "source": source,
        "status": "source_limited"
        if stop
        in {
            "source_limited",
            "pagination_loop",
            "filter_drift",
            "unexpected_page_response",
            "repeated_or_unverified_page",
            "no_new_ids",
            "source_total_drift",
            "terminal_count_mismatch",
        }
        else "partial",
        "stop_reason": stop,
        "next_url": url,
        "unique_count": len(listings),
        "duplicate_count": duplicate_count,
        "source_totals_by_page": source_totals,
        "native_partition_pagination_verified": native_terminal_verified,
        "listings": list(listings.values()),
        "pages": pages,
        "coverage_complete": False,
        "reviewed_by_model": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", choices=SOURCES)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--cursor")
    p.add_argument("--detail-url")
    p.add_argument("--taxonomy", action="store_true")
    p.add_argument(
        "--work-model",
        choices=[
            "full_time",
            "part_time",
            "freelance",
            "freelance_project",
            "internship",
            "shift_based",
            "volunteering",
        ],
    )
    p.add_argument("--continuation-url")
    p.add_argument("--browser-capture-stdin", action="store_true")
    p.add_argument("--crawl", action="store_true")
    p.add_argument("--max-pages", type=int, default=2)
    args = p.parse_args()
    print(
        json.dumps(
            parse_browser_capture(args.source, json.load(sys.stdin))
            if args.browser_capture_stdin
            else crawl_board(args.source, args.max_pages, args.work_model)
            if args.crawl
            else query(
                args.source,
                args.page,
                args.cursor,
                args.detail_url,
                args.taxonomy,
                args.work_model,
                args.continuation_url,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
