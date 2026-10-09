"""Egypt board parsers, URL boundaries and pagination; no candidate filtering.

Independently written from observed public pages. The MIT Forasna upstream was
inspected for context, but its applicant-count filter and offset loop are not used.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit

from lxml import html

BOARD_URLS = {
    "wuzzuf": "https://wuzzuf.net/search/jobs",
    "forasna": "https://forasna.com/" + quote("وظائف-خالية"),
    "arabjobs": "https://www.arabjobs.com/en/jobs/search/",
}
WORK_MODELS = {
    "Full Time": "full_time",
    "Part Time": "part_time",
    "Freelance / Project": "freelance",
    "Shift Based": "shift_based",
    "Internship": "internship",
    "يوم كامل": "full_time",
    "نصف يوم": "part_time",
    "عمل حر": "freelance",
    "عمل من المنزل": "home_work_hours_unknown",
    "موسمية": "seasonal_hours_unknown",
    "كل الوقت": "full_time",
    "Full Time / Part Time": "mixed_hours_unknown",
}
WUZZUF_NATIVE_MODELS = {
    "full_time",
    "part_time",
    "freelance_project",
    "internship",
    "shift_based",
    "volunteering",
}


def clean_text(node):
    """Keep word boundaries across block tags, Arabic paragraphs and HTML breaks."""
    if node is None:
        return ""
    blocks = {
        "br",
        "li",
        "p",
        "div",
        "section",
        "ul",
        "ol",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "tr",
        "td",
    }

    def parts(element):
        if element.text:
            yield element.text
        for child in element:
            if (
                not isinstance(child.tag, str)
                or child.tag in {"script", "style"}
                or child.get("hidden") is not None
            ):
                if child.tail:
                    yield child.tail
                continue
            if child.tag in blocks:
                yield " "
            yield from parts(child)
            if child.tag in blocks:
                yield " "
            if child.tail:
                yield child.tail

    return " ".join("".join(parts(node)).split())


def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(p.path, safe="/%"), p.query, p.fragment))


def board_page_url(source, page=1, work_model=None):
    if source not in BOARD_URLS or not 1 <= page <= 10000:
        raise ValueError("Unsupported board or page")
    work_model = "freelance_project" if work_model == "freelance" else work_model
    if work_model and (source != "wuzzuf" or work_model not in WUZZUF_NATIVE_MODELS):
        raise ValueError("Only verified WUZZUF native work models supported")
    if source == "wuzzuf":
        params = {"filters[country][0]": "Egypt"}
        if work_model:
            params["filters[job_types][0]"] = work_model
        if page > 1:
            params["start"] = page - 1
    elif source == "forasna":
        if page != 1:
            raise ValueError(
                "Forasna page offsets are not a verified numbered contract; use the native browser Next control"
            )
        params = {}
    else:
        params = {"pageIndex": page, "filterJobCountry": "EG", "sortType": "2"}
    return BOARD_URLS[source] + ("?" + urlencode(params) if params else "")


def validate_board_url(source, url, detail=False):
    """Keep browser imports, detail reads and continuations inside public scope."""
    p = urlsplit(url)
    if (
        source not in BOARD_URLS
        or p.scheme != "https"
        or p.hostname != urlsplit(BOARD_URLS[source]).hostname
        or p.username is not None
        or p.password is not None
        or p.port
        or p.fragment
    ):
        raise ValueError("Only canonical HTTPS public URLs on the selected board are allowed")
    path = unquote(p.path)
    if detail:
        patterns = {
            "wuzzuf": r"/jobs/p/[a-z0-9]{12}-[^/]+",
            "forasna": r"/job/p/[^/]+-\d+",
            "arabjobs": r"/en/jobs/j/[^/]+/[^/]+/\d+",
        }
        # Forasna's observed title slugs can contain an encoded slash (%2F).
        # It remains one URL segment; decoding it before route validation
        # incorrectly rejects legitimate public job IDs.
        detail_path = p.path if source == "forasna" else path
        if p.query or not re.fullmatch(patterns[source], detail_path):
            raise ValueError("Unrecognized public detail path")
    else:
        q = parse_qs(p.query, keep_blank_values=True)
        if source == "wuzzuf":
            allowed = {"filters[country][0]", "filters[job_types][0]", "start"}
            valid = (
                path == "/search/jobs"
                and q.get("filters[country][0]") == ["Egypt"]
                and (
                    "filters[job_types][0]" not in q
                    or q["filters[job_types][0]"][0] in WUZZUF_NATIVE_MODELS
                )
            )
        elif source == "forasna":
            allowed = {"start"}
            valid = path == "/وظائف-خالية"
        else:
            allowed = {"pageIndex", "filterJobCountry", "sortType"}
            valid = (
                path == "/en/jobs/search/"
                and q.get("filterJobCountry") == ["EG"]
                and q.get("sortType", ["2"]) == ["2"]
            )
        if not valid or set(q) - allowed or any(len(v) != 1 for v in q.values()):
            raise ValueError(
                "Geography-only/native work-model URL required; no keyword/title filters"
            )
        for key in {"start", "pageIndex"} & set(q):
            if not q[key][0].isdigit() or not 0 <= int(q[key][0]) <= 200000:
                raise ValueError("Invalid pagination value")
    return canonical(url)


def filter_signature(source, url):
    p = urlsplit(validate_board_url(source, url))
    q = parse_qs(p.query)
    return (
        p.path,
        tuple(sorted((k, tuple(v)) for k, v in q.items() if k not in {"start", "pageIndex"})),
    )


def source_id(source, url):
    validate_board_url(source, url, detail=True)
    path = unquote(urlsplit(url).path)
    return (
        path.split("/p/")[1].split("-")[0]
        if source == "wuzzuf"
        else re.search(r"(\d+)$", path).group(1)
    )


def field_values(card, label):
    return [
        clean_text(x)
        for x in card.xpath(".//h5[span]")
        if clean_text(x.xpath("./span")[0]).rstrip(":") == label
    ]


def parse_board_page(source, body, url):
    validate_board_url(source, url)
    doc = html.fromstring(body)
    if source == "wuzzuf":
        anchors = doc.xpath('//h2/a[contains(@href,"/jobs/p/")]')
    elif source == "forasna":
        anchors = doc.xpath('//h2[contains(concat(" ",@class," ")," job-title ")]/a')
    else:
        anchors = doc.xpath('//h3/a[contains(@href,"/en/jobs/j/")]')
    if not anchors:
        raise ValueError("Listing structure absent; empty/challenge page is not zero supply")
    listings = []
    for a in anchors:
        card = a.getparent().getparent()
        if source in {"wuzzuf", "forasna"}:
            card = card.getparent()
        href = canonical(urljoin(url, a.get("href")))
        tags = [clean_text(x) for x in card.xpath(".//a")]
        labels = [tag for tag in tags if tag in WORK_MODELS]
        if source == "arabjobs":
            labels = [x.split(":", 1)[-1].strip() for x in field_values(card, "Job Type")]
        models = list(dict.fromkeys(WORK_MODELS.get(x, "unknown") for x in labels))
        times = card.xpath(".//time")
        dates = card.xpath('.//*[contains(@class,"right-side-block-footer")]//h5')
        listings.append(
            {
                "id": source_id(source, href),
                "url": href,
                "title": clean_text(a),
                "card_text": clean_text(card),
                "employment_labels": labels,
                "employment_models": models,
                "hours_verified": False,
                "source_date_raw": [dict(x.attrib) | {"text": clean_text(x)} for x in times]
                or [clean_text(x) for x in dates],
            }
        )
    pagination = []
    next_urls = []
    position_key = "pageIndex" if source == "arabjobs" else "start"
    current = int(
        parse_qs(urlsplit(url).query).get(position_key, ["1" if source == "arabjobs" else "0"])[0]
    )
    for a in doc.xpath("//a[@href]"):
        href = a.get("href")
        if source == "arabjobs" and re.fullmatch(r"javascript:PagerGo\(\d+\)", href):
            href = board_page_url(source, int(re.search(r"\d+", href).group()))
        else:
            href = canonical(urljoin(url, href))
        try:
            validate_board_url(source, href)
        except ValueError:
            continue
        if filter_signature(source, href) != filter_signature(source, url):
            continue
        position = int(
            parse_qs(urlsplit(href).query).get(
                position_key, ["1" if source == "arabjobs" else "0"]
            )[0]
        )
        pagination.append({"text": clean_text(a), "url": href, "position": position})
        if position > current:
            next_urls.append((position, href))
    # Follow the smallest observed forward continuation, never number of cards.
    next_url = min(next_urls)[1] if next_urls else None
    next_control_href = (
        next((x["url"] for x in pagination if x["text"] == "التالى"), None)
        if source == "forasna"
        else None
    )
    total_nodes = doc.xpath('//*[contains(concat(" ",@class," ")," search-jobs-count ")]')
    range_nodes = doc.xpath('//nav[@aria-label="Pagination"]')
    total = None
    active_pages = doc.xpath('//li[contains(concat(" ",@class," ")," pag-current ")]/span')
    rendered_page_number = (
        int(clean_text(active_pages[0]))
        if active_pages and clean_text(active_pages[0]).isdigit()
        else None
    )
    if total_nodes:
        total = int(re.sub(r"\D", "", clean_text(total_nodes[0])))
    elif range_nodes:
        match = re.search(r"Showing\s+\d+\s*-\s*\d+\s+of\s+([\d,]+)", clean_text(range_nodes[0]))
        if match:
            total = int(match.group(1).replace(",", ""))
    return {
        "listings": listings,
        "reported_total": total,
        "rendered_page_number": rendered_page_number,
        "url_pagination_position": current,
        "next_url": None if source == "forasna" else next_url,
        "observed_forward_href": next_url if source == "forasna" else None,
        "observed_next_control_href": next_control_href,
        "next_browser_action": {
            "kind": "click_visible_next_then_verify_resulting_url_page_number_and_stable_ids",
            "label": "التالى",
        }
        if next_control_href
        else None,
        "pagination_links": pagination,
        "page_fingerprint": hashlib.sha256(
            "\n".join(sorted(x["id"] for x in listings)).encode()
        ).hexdigest(),
        "description_basis": "listing_card_only_full_detail_required",
        "date_basis": "source_display_date_or_relative_text_timezone_and_original_publication_unverified",
        "limits": [
            "Live supply can drift. Reconcile stable IDs, source totals and every required partition.",
            "Forasna rendered Next clicks and advertised href offsets can disagree; browser continuation requires a native click and verification of resulting URL, active page and IDs.",
        ]
        if source == "forasna"
        else [
            "Live supply can drift; no page or absent next link proves a complete time interval."
        ],
    }


def parse_board_detail(source, body):
    doc = html.fromstring(body)
    headings = doc.xpath("//h2|//h3|//div[contains(@class,'panel-heading')]")
    names = {
        "wuzzuf": ["Job Description", "Job Requirements", "Job Details"],
        "forasna": ["تفاصيل الوظيفة", "متطلبات الوظيفة", "الراتب ونوع العمل", "مميزات الوظيفة"],
        "arabjobs": ["Job Description", "Job Requirements"],
    }[source]
    sections = {}
    for name in names:
        matched = [x for x in headings if clean_text(x) == name]
        if not matched:
            continue
        h = matched[0]
        container = h.getparent()
        if source == "forasna":
            container = container.getparent()
        if source == "arabjobs" and name == "Job Description":
            container = h.getnext()
        sections[name] = {
            "text": clean_text(container),
            "html": html.tostring(container, encoding="unicode"),
        }
    if any(
        name not in sections or not sections[name]["text"] or sections[name]["text"] == name
        for name in names[:2]
    ):
        raise ValueError("Both full description and requirements sections must be present")
    title_nodes = doc.xpath("//h1") or doc.xpath("//h3")
    header_nodes = doc.xpath("//header[@data-public-source-header]")
    return {
        "title": clean_text(title_nodes[0]) if title_nodes else None,
        "source_header_text": clean_text(header_nodes[0]) if header_nodes else None,
        "source_notice": [clean_text(x) for x in doc.xpath("//footer[@data-source-notice]")],
        "sections": sections,
        "availability_status": "not_verified",
        "source_description_quality": "sparse"
        if len(sections[names[0]]["text"]) < 40
        else "present",
        "source_date_raw": doc.xpath('//*[@itemprop="datePosted"]/@content|//time/@datetime'),
        "description_basis": "source_description_and_requirements_sections_not_yet_reviewed",
        "date_basis": "source_date_timezone_and_original_publication_must_be_verified",
    }
