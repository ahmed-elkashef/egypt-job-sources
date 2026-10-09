# Source access and content policy

The MIT license covers this project's authored software and documentation.
Retrieved listings and briefs remain third-party content. Publishing an adapter
is not permission to republish a platform's database or override its terms.

## Access behavior

- Use public endpoints or public page content that you are authorized to view.
  The optional Upwork API reader requires separately approved API access and
  an authorized local token; it never turns account membership into API approval.
- Stop on explicit access denial, authentication requirements, rate limits or
  challenge pages. The project provides no proxy rotation, fingerprint
  impersonation, CAPTCHA solving, credential harvesting or challenge bypass.
- The public DOM handoff operates on selected source-page content. It does not
  export cookies, session storage, hidden account state, application forms,
  messages or applicant records. Check a capture before saving it.
- Keep captured pages and responses in local private storage. Do not commit real
  source datasets, captured HTML, credentials or private candidate information.
- Preserve source URLs, attribution, proprietary notices and raw date evidence.
  A successful request does not establish eligibility, freshness or a complete
  market census.

## Source-specific conditions

### WUZZUF

The adapter uses a currently observed public frontend JSON:API contract. This is
an undocumented, unofficial integration and may change without notice.

[WUZZUF's policies](https://wuzzuf.net/policies) limit the use of website materials
to personal, non-commercial informational purposes and restrict modification,
redistribution and public or commercial reuse. Preserve its source notices and
keep acquired materials private. The release contains independently authored
code and synthetic tests, with no WUZZUF listing dataset or frontend assets.

### Forasna, ArabJobs, Bayt and Mostaql

These adapters parse public source pages. Access may be blocked or changed, and
the project makes no claim that a site's content is open licensed. Source terms,
content rights and restrictions remain applicable. Forasna currently requires
an authorized browser DOM capture when ordinary HTTP is denied; that fallback
does not broaden access permission.

### Himalayas

Follow the [official API documentation](https://himalayas.app/api). When displaying
a listing, identify Himalayas as the original source and link to its canonical
listing URL. The documented service prohibits submitting Himalayas jobs to
third-party job sites such as Jooble, Neuvoo, Google Jobs or LinkedIn Jobs. Respect
rate limits and cache responses where appropriate.

The global browse reader uses the official unfiltered cursor feed, with a
maximum of 20 jobs per request. Data refreshes daily. Keep `salaryPeriod` and
currency with each salary amount. The official repository's MIT license covers
examples and documentation; its separate job-data conditions still apply.

### Jobicy

Follow [Jobicy's official fair-use documentation](https://github.com/Jobicy/remote-jobs-api#fair-use).
Keep Jobicy as the original source and preserve the canonical Jobicy job URL.
Cache responses where appropriate. Start new automated polling or synchronization
passes no more frequently than once per hour; sequential cursor requests may
complete a single synchronization pass. Do not misrepresent listings, create
spam networks or overload the service.

The MIT license on Jobicy's example repository covers its code and examples,
rather than ownership of employer content or other third-party data.

### Remotive

Follow the [official public API documentation](https://github.com/remotive-com/remote-jobs-api).
Retain Remotive attribution and the canonical listing link. The public feed
delays jobs by 24 hours and advises at most four fresh requests daily; excessive
polling is blocked. Do not submit listings to third-party job aggregators or
display them behind signup/email collection. No unrestricted historical feed
or paid inventory access is inferred.

### Remote OK

Retain the legal notice returned at the beginning of the
[official JSON feed](https://remoteok.com/api). Display the Remote OK name and
a followable canonical link when showing a listing. Its logo requires separate
written permission. The public response is a recent snapshot with no verified
historical pagination, and descriptions may be abbreviated.

### We Work Remotely

The [official RSS policy](https://weworkremotely.com/remote-job-rss-feed) permits
use of its public feeds with links attributed to We Work Remotely. The adapter
reads the all-category RSS feed. A feed description or broad region flag does
not prove complete employer text or actual applicant eligibility.

### Working Nomads

The [official site](https://www.workingnomads.com/jobs) links to its exposed-jobs
API. This public subset does not establish subscription inventory coverage.
The [source terms](https://www.workingnomads.com/terms-and-conditions) restrict
commercial exploitation and using the service to build a competing product.
Publishing independent adapter code does not grant rights to republish that
service or its listing database.

### Freelancer.com

The project reader uses anonymous public active-project and detail endpoints,
with full-description projections. Source-marked nonpublic or deleted content
is excluded. No bidding, messaging, milestone, payment or account operation is
exposed. The [official developer portal](https://developer.freelancer.com/)
and platform terms govern API/content use. Public readability is not a general
license for database redistribution. Posted budgets remain client terms,
without a claim of earnings, eligibility or payment protection.

The official SDK was reviewed as a research reference and is not a dependency.
Its LGPL-3.0 license applies to that SDK; no SDK implementation was copied into
this project's MIT code.

### Upwork

Use the fixed read operations only with approved API access and an authorized
token supplied through local environment/secret storage. The
[official approval policy](https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork)
sets account/application requirements and supports personal/internal use,
without commercial API use or third-party developer test accounts. Ordinary
membership does not satisfy those requirements.

Review the [current API schema](https://www.upwork.com/developer/documentation/graphql/api/docs/index.html)
and its terms before use. Source limits and cache restrictions remain
applicable. This release has not validated approved-token live behavior; it
does not obtain, renew or request API credentials, use saved-search RSS, expose
arbitrary GraphQL, submit proposals or contact clients. Publishing the code
does not publish Upwork data or grant platform API access.

## Contributions

Tests must use synthetic fixtures. Describe source behavior with small invented
payloads, rather than checking in real employer descriptions or frontend bundles.
Record upstream code reuse and retain required copyright and license notices.
Never infer that a source allows unrestricted data reuse because an independently
written scraper has an open-source license.

## Official employer boards — 0.3.0

Greenhouse, Lever and Ashby are employer-specific published-job interfaces, not geographic job indexes. Use exact confirmed board tokens; never guess an employer's token from its domain. No application POST, candidate APIs, applicant profiles or internal postings are accessed. Full returned public description fields and provider timestamp semantics are preserved. Code licensing does not grant redistribution rights to job content. Public source snapshots cannot establish original frozen-interval or regional completeness. Official contracts: https://docs.greenhouse.io/job-board.html ; https://github.com/lever/postings-api ; https://developers.ashbyhq.com/docs/public-job-posting-api . Checked 9 October 2026.
