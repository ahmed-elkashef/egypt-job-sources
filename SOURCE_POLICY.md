# Source access and content policy

The MIT license covers this project's authored software and documentation.
Retrieved listings and briefs remain third-party content. Publishing an adapter
is not permission to republish a platform's database or override its terms.

## Access behavior

- Use public endpoints or public page content that you are authorized to view.
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

### Jobicy

Follow [Jobicy's official fair-use documentation](https://github.com/Jobicy/remote-jobs-api#fair-use).
Keep Jobicy as the original source and preserve the canonical Jobicy job URL.
Cache responses where appropriate. Start new automated polling or synchronization
passes no more frequently than once per hour; sequential cursor requests may
complete a single synchronization pass. Do not misrepresent listings, create
spam networks or overload the service.

The MIT license on Jobicy's example repository covers its code and examples,
rather than ownership of employer content or other third-party data.

## Contributions

Tests must use synthetic fixtures. Describe source behavior with small invented
payloads, rather than checking in real employer descriptions or frontend bundles.
Record upstream code reuse and retain required copyright and license notices.
Never infer that a source allows unrestricted data reuse because an independently
written scraper has an open-source license.
