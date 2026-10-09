# Egypt Job Sources

Read-only Python adapters for Egyptian vacancies, global remote-job feeds, and client project briefs. The package preserves source descriptions, stable IDs, native pagination, and acquisition limits. It does not apply for jobs, send messages, submit bids, access applicant profiles, or decide whether a person is eligible.

This is an independently written project, **not a fork**. Upstream scraper projects were inspected as research references. See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for attribution and provenance, and [SOURCE_POLICY.md](SOURCE_POLICY.md) for source policies and checked dates.


### Direct employer boards

The optional ATS module reads only an employer's exact confirmed board token, with no role/keyword filters. It preserves complete returned descriptions and native identifiers. These providers are not a geographic employer universe.

```sh
python -m egypt_job_sources.ats --capabilities
python -m egypt_job_sources.ats --source greenhouse --board CONFIRMED_BOARD_TOKEN
python -m egypt_job_sources.ats --source lever --board CONFIRMED_BOARD_TOKEN --skip 0 --limit 100
python -m egypt_job_sources.ats --source ashby --board CONFIRMED_BOARD_TOKEN
```

Lever optionally accepts repeated `--commitment 'EXACT_OBSERVED_LABEL'` arguments (one to twenty distinct nonempty labels, at most 200 characters each). First read the broad verified board and inspect its native `categories.commitment` taxonomy; no universal labels are assumed. The [official provider contract](https://github.com/lever/postings-api) combines repeated values with case-sensitive OR matching. Repeat the exact same labels on every `next_skip` continuation. Responses retain `source_filters`, returned rows, full text and raw counts; known contradictory returned labels fail explicitly and missing/mixed commitment metadata remains undetermined. Preserve the unfiltered unknown, other-label and contradictory full-time complement before claiming supply coverage. Positive labels such as internships or fixed terms do not establish compatible hours or country eligibility. Commitment filters are refused for Greenhouse, Ashby and individual details. A filtered terminal page does not establish a whole-board snapshot.

Replace the placeholder with the token observed on the employer's official board. Lever continuation uses returned `next_skip`; Greenhouse/Ashby are whole-board responses. Source timestamps, hours, work-from-country eligibility and historical completeness still need review. A failed request is an explicit limitation, never an empty successful board.

## Install

Python 3.11 or newer is required. From a checkout:

```sh
git clone https://github.com/ahmed-elkashef/egypt-job-sources.git
cd egypt-job-sources
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`; the environment executables are under `.venv\Scripts`. All command examples below assume that environment is active. The sole runtime dependency is `lxml>=6,<7`. Public feeds and Freelancer project reads need no account credentials. Upwork is optional and requires an approved API application and an authorized token. No browser automation framework or session store is bundled. Releases distribute source and archives through GitHub; these instructions do not depend on a PyPI publication.

## Use

The Egypt inventory defaults to broad geography with no role, title, keyword, seniority, or candidate-specific employment filter.

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

### Global remote feeds

```sh
egypt-remote-sources --capabilities
egypt-remote-sources remotive
egypt-remote-sources remoteok
egypt-remote-sources weworkremotely
egypt-remote-sources workingnomads
egypt-remote-sources himalayas_global
egypt-remote-sources himalayas_global --cursor 'SOURCE_RETURNED_CURSOR'
```

These commands acquire broad feed responses without candidate or keyword filters. Every returned item survives; descriptions are not clipped to a summary length. Original fields remain in `source_data`, with source attribution and metadata alongside them. Himalayas global uses the official browse endpoint, distinct from the `egypt-job-sources himalayas` country search.

For Himalayas, pass the actual `next_cursor` from one result into the next request; do not invent offsets. Each call returns one page, at most 20 items. The other feeds are snapshots with no verified continuation contract: their `has_more` is `null`, which does not mean exhausted market supply. Source-level delays, recent-feed caps and paid inventory remain explicit limits.

### Worldwide client projects

```sh
egypt-freelance-sources --capabilities
egypt-freelance-sources --source freelancer --limit 20
egypt-freelance-sources --source freelancer --limit 20 --offset 20
egypt-freelance-sources --source freelancer --limit 100 --from-time '2026-01-01T12:00:00Z' --to-time '2026-01-03T12:00:00Z'
egypt-freelance-sources --source freelancer --project-id 123456789
egypt-freelance-sources --source upwork --limit 20
egypt-freelance-sources --source upwork --cursor 'SOURCE_RETURNED_CURSOR'
egypt-freelance-sources --source upwork --project-id 123456789
```

Project IDs are illustrative; use the identifier returned by the source. Freelancer uses anonymous active-project reads with full-description projections and returned count/offset metadata. Follow the actual `pagination.next_offset`; the example offset above illustrates syntax. Source-marked nonpublic or deleted records are excluded and recorded by ID/reason. Missing full descriptions remain an explicit evidence gate.

Freelancer's optional paired aware RFC3339 `--from-time` / `--to-time` constrain **update activity**, not first creation. Freeze the requested `[start,end)` interval and repeat the exact bounds on every returned-offset page. The request uses an enclosing integer-second native interval. Returned update timestamps must fit that interval or the reader fails explicitly. Every returned public row remains intact: `time_window_screening` separately classifies matching native `submitdate` / `time_submitted` against the exact submission window. Missing, invalid or conflicting timestamps remain `undetermined`; source submission dates do not prove first-ever creation or distinguish every repost. `requested_time_window`, `source_filters` and `source_filter_verification` retain that distinction. No date option is accepted for Upwork or project details.

Hourly `commitment.hours` is a billing limit, not a proven minimum attendance requirement. The [official hourly FAQ](https://www.freelancer.com/faq/topic.php?id=36) describes a default limit of 40 hours per week; [billing help](https://www.freelancer.com/support/employer/project/weekly-billing-for-hourly-projects?w=f) defines the maximum trackable hours. Read the actual brief before deciding that a project requires full-time availability.

Upwork sends only two fixed read queries to its official GraphQL endpoint. Supply `UPWORK_ACCESS_TOKEN` through your local environment or secret manager after developer approval and OAuth authorization for the appropriate account. Do not put a token in a command, checked-in configuration or bug report. This package does not collect credentials, create an API application, log in, refresh tokens or bypass approval. Without a token it returns `source_limited` before making a network request. Approved-token live behavior remains unverified in this release. Review the [official approval requirements](https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork), which are separate from ordinary marketplace membership.

`--limit` is a page size, not a market census cap. Offset/cursor pages, moving totals, full descriptions, exact hours, permitted geography, fees and payout access must be reconciled before treating a project as usable work. A fixed project budget is not an hourly salary or earned income. The freelance CLI exits with code 2 on `source_limited`; inspect its JSON diagnostic.

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
| Remotive | Official unfiltered public JSON snapshot | Public feed is delayed 24 hours. Advises at most four fresh fetches per day; no historical pagination is verified. Attribution, backlink and reuse conditions apply. |
| Remote OK | Official JSON snapshot with a separate legal metadata object | Recent bounded feed; no verified total or continuation. Descriptions may be abbreviated. Preserve source name and followable links. |
| We Work Remotely | Official all-category RSS | Current snapshot; no verified historical pagination. Source type/region flags can disagree with descriptions. Attribution required. |
| Working Nomads | Official footer-linked exposed-jobs API | Public exposed subset, with no verified total/pagination. Subscription supply is broader. Data reuse restrictions remain applicable. |
| Himalayas global | Official unfiltered browse API, using returned cursors | Maximum 20 per page, daily refresh, possible rate limiting. Preserve `salaryPeriod`, currency, restrictions and source attribution. |
| Freelancer.com | Anonymous active-project API and numeric project details | Mutable total/offset enumeration; not complete historical supply. Local/full-time projects can occur. Budgets, currencies, description gaps and public/deleted flags are retained. |
| Upwork | Fixed official marketplace search and content GraphQL operations | Approved API access and local authorized token required; live approved-token behavior is unverified. No saved-search RSS route, arbitrary queries or account mutations. |

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

The MIT license applies to this project's **code**. It does not license platform content, trademarks, or job descriptions. Review each platform's terms and applicable rules before use; permission to browse a page does not establish permission to redistribute its content. Preserve source links, notices, confidentiality flags, and original terms. Use modest sequential requests and a bounded development page cap; stop on blocks or challenges. Development caps never establish full source or interval coverage. There is no evasion, proxy rotation, impersonation, login collection, or challenge bypass.

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

### Source-provided job links

Remote feed descriptions are preserved independently of link completeness. Working Nomads may supply its native numeric `/job/go/` redirect link, which is retained without fetching its outbound destination. Himalayas may identify postings through `/companies/{company}/jobs/{posting}`. A Remote OK record that supplies only the generic board index keeps its stable ID and full text but has no exact posting URL; its explicit gate must be resolved before treating it as a verified application opportunity. Attribution to a source index is labeled separately. Foreign, credential-bearing, queried, fragmented and malformed links remain invalid.
