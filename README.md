# Egypt Job Sources

Read-only Python adapters for public Egyptian vacancies and freelance project briefs. The package preserves source descriptions, stable IDs, native pagination, and acquisition limits. It does not apply for jobs, send messages, submit bids, access applicant profiles, or decide whether a person is eligible.

This is an independently written project, **not a fork**. Upstream scraper projects were inspected as research references. See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for attribution and provenance, and [SOURCE_POLICY.md](SOURCE_POLICY.md) for source policies and checked dates.

## Install

Python 3.11 or newer is required. From a checkout:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`; the environment executables are under `.venv\Scripts`. All command examples below assume that environment is active. The sole runtime dependency is `lxml>=6,<7`. No browser automation framework, credentials, or session store is required.

## Use

The default inventory is broad: Egypt geography, with no role, title, keyword, seniority, or candidate-specific employment filter.

```sh
egypt-job-sources wuzzuf
egypt-job-sources wuzzuf --work-model full_time --page 2
egypt-job-sources wuzzuf --work-model part_time --crawl --max-pages 2
egypt-job-sources wuzzuf --taxonomy
egypt-job-sources arabjobs --page 2
egypt-job-sources himalayas --page 2
egypt-job-sources jobicy --cursor 'SOURCE_RETURNED_CURSOR'
```

Read a description using its public canonical URL:

```sh
egypt-job-sources wuzzuf --detail-url 'https://wuzzuf.net/jobs/p/SOURCE_PUBLIC_SLUG'
egypt-job-sources mostaql --detail-url 'https://mostaql.com/project/SOURCE_ID-SOURCE_SLUG'
```

The placeholder URLs above must be replaced with valid source-returned URLs. Detail fetches are restricted to canonical routes on the selected board; this is not an arbitrary URL fetcher. WUZZUF models are `full_time`, `part_time`, `freelance_project` (alias `freelance`), `internship`, `shift_based`, and `volunteering`. Unsupported source/model combinations fail explicitly.

Every result is JSON. Acquisition returns `status: "ok"` or `status: "source_limited"`. A blocked page or changed layout is a failure, never a successful empty inventory. Missing WUZZUF hydration retains the raw search ID and reports pending evidence. A capped crawl reports `partial` even when a native partition's terminal count reconciles: it still does not establish market or time-interval coverage.

`coverage_complete` and `reviewed_by_model` remain `false`. Raw publication dates are retained; missing timezones and ambiguous original-publication semantics are never converted into assumed UTC timestamps. Empty source requirements remain empty. Remote work and contractor labels do not establish country eligibility or working hours.

## Sources and limits

These observations were last validated on **2026-10-09**. Current access and markup can change. The test suite uses synthetic data and makes no live platform requests.

| Source | Acquisition | Material limits |
| --- | --- | --- |
| WUZZUF | Public frontend JSON:API search, native facets, 15-card pages, and authoritative full descriptions | Undocumented frontend contract; not a vendor-supported developer API. Search is a read-only POST. Dates have unverified timezones. |
| Forasna | Operator-supplied public DOM pages and full descriptions | Direct HTTP access was blocked. Hydrated Next clicks and advertised link offsets disagreed; click the visible Next control, then verify URL, active page and stable IDs. No inferred numbered-page crawler. |
| ArabJobs | Egypt inventory pages and description/requirements sections | Older records coexist with recent listings. Same-ID canonical detail redirects are accepted; scope or ID changes are rejected. Availability is not established by acquisition. |
| Bayt | Egypt inventory/JobPosting parser | Live access was blocked during validation. Parser support is not a claim of current successful acquisition. |
| Himalayas | Public API with broad Egypt geography | Country results may include worldwide jobs; inspect each description and restrictions. Preserve source attribution and canonical links; do not export to third-party listing aggregators. |
| Jobicy | Public remote-job API and source-returned cursors | Global moving feed, not an Egypt census; older missed supply may be unavailable. Fresh polling passes must be no more frequent than hourly; cursor pages within one pass are permitted. |
| Mostaql | Public project listings and scoped full briefs with budget, status, and delivery duration | A budget is a whole-project posted range, not earned income; fees, payment access, client authenticity, and delivery ability remain unverified. Bids and profiles are excluded. |

## Operator browser captures

When an ordinary authorized browser can read a public source but direct HTTP cannot, supply only selected public job-page DOM. Do not include cookies, browser storage, authentication tokens, private messages, account panels, applicant records, or unrelated profiles.

The capture JSON must contain exactly four fields:

```json
{
  "url": "https://forasna.com/وظائف-خالية",
  "kind": "page",
  "captured_at": "2026-10-09T12:00:00+02:00",
  "html": "<SELECTED PUBLIC DOM HTML>"
}
```

Use `kind: "detail"` for a full public vacancy. HTML is parsed as data; scripts are not executed. The supplied capture is operator evidence, not independent proof of browser provenance.

Parse a local capture without fetching a source:

```sh
egypt-job-sources forasna --browser-capture-stdin < public-capture.json
```

Alternatively, run the local handoff form, open the printed loopback URL in your browser, choose the source, and paste the capture JSON:

```sh
egypt-job-capture serve
egypt-job-capture show RECEIPT_SHA256
```

Stop the form with Ctrl+C. It binds only to `127.0.0.1`, requires the exact local Host and Origin for submissions, and rejects extra fields. Original captures are stored as immutable SHA-256 receipts and reparsed when read. The default cache is `~/.cache/egypt-job-sources/public-captures`; `EGYPT_JOBS_CAPTURE_DIR` can name another local directory. Neither command writes into this repository or the installed package directory.

## Responsible use and data boundaries

The MIT license applies to this project's **code**. It does not license platform content, trademarks, or job descriptions. Review each platform's terms and applicable rules before use; permission to browse a page does not establish permission to redistribute its content. Preserve source links, notices, confidentiality flags, and original terms. Use modest sequential requests and a bounded page cap; stop on blocks or challenges. There is no evasion, proxy rotation, impersonation, login collection, or challenge bypass.

This repository distributes no scraped corpus, real vacancy fixtures, credentials, account configuration, personal career profiles, or applicant data. Keep captured public HTML and live result JSON local and out of Git. Raw HTML returned by a parser is untrusted data: escape or sanitize it before rendering in another application.

## Development

```sh
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
ruff check src tests
ruff format --check src tests
python -m build
```

CI runs offline parser and boundary tests on Python 3.11, 3.12, and 3.13. See [CONTRIBUTING.md](CONTRIBUTING.md) for safe bug reports and fixtures.
