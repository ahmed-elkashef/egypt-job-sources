# Acknowledgments and provenance

Thank you to the maintainers who made Egyptian, global remote and client-work
source research easier to understand. These adapters and the MCP wrapper were
implemented independently. Releases through 0.2.0 contain no copied third-party
connector implementation and carry no upstream fork history. One historical
reference repository was cloned for inspection. The public projects retain
their own source and history.

## Egypt community references

| Project and credited author | Reviewed revision | Contribution to our research |
| --- | --- | --- |
| [forasna.com-scraper](https://github.com/maboelfotoh/forasna.com-scraper), Muhammad Aboelfotoh | [`ce7e431`](https://github.com/maboelfotoh/forasna.com-scraper/tree/ce7e4312606504bcde7189a2cf657fede682f147) | Historical Forasna page and detail extraction reference; cloned and read for inspection. Current pagination and DOM handling were verified independently. |
| [pywuzzuf](https://github.com/hossam-elshabory/pywuzzuf), Hossam Elshabory | [`d6a9837`](https://github.com/hossam-elshabory/pywuzzuf/tree/d6a98378805210f292943376c6b13d3d6f585eff) | WUZZUF resource schema and endpoint reference. Our anonymous HTTP transport and current frontend contract were verified independently; its browser impersonation transport is not included. |
| [JobSpy](https://github.com/speedyapply/JobSpy), Cullen Watson and contributors | [`1fffbcd`](https://github.com/speedyapply/JobSpy/tree/1fffbcd4c1d822740157459fe527a916d3ce7a43) | Bayt adapter, country filtering and detail-retrieval reference. JobSpy is not a bundled dependency. |
| [Forasna-Jobs-Scraper](https://github.com/fadidow-scraper/Forasna-Jobs-Scraper), Fadi Dowara | [`15824ad`](https://github.com/fadidow-scraper/Forasna-Jobs-Scraper/tree/15824ada9d3e112e06a1e28b538dffff35b2044c) | Additional Forasna selector and traversal review. |
| [Wuzzuf-Jobs-Deep-Scraper](https://github.com/fadidow-scraper/Wuzzuf-Jobs-Deep-Scraper), Fadi Dowara | [`ad30ee7`](https://github.com/fadidow-scraper/Wuzzuf-Jobs-Deep-Scraper/tree/ad30ee7e9238fdde8a7b3d52f697c90064904bb1) | Additional WUZZUF detail and failure-handling review. |
| [wuzzuf-job-scraper](https://github.com/faress1212/wuzzuf-job-scraper), Fares Mohammed Sha'wat | [`7558178`](https://github.com/faress1212/wuzzuf-job-scraper/tree/75581788c3023fcf5cfec627115578c61e1039d9) | Additional WUZZUF search-card and pagination review. |
| [job-scraper](https://github.com/omarashour04/job-scraper), Omar Ashour | [`bb149f7`](https://github.com/omarashour04/job-scraper/tree/bb149f770a86a0333e192b20d44a439c7e5ef7d6) | Additional extraction and summary-versus-description review. Its browser automation and stealth dependencies are not included. |

Each reference above has an MIT license at the recorded revision. Exact license
links, copyright notices, full commit hashes and reuse roles are recorded in
[upstream-references.json](upstream-references.json). These credits acknowledge
research references; they do not claim endorsement or authorship of our code by
the referenced maintainers.

If future contributions copy or adapt upstream code, record the affected files,
retain the upstream copyright and full license notice, and update this provenance
record. Research citations alone are not a substitute for required notices on
copied software.

## Remote and client-work references added in 0.2.0

The following repositories and license files were reviewed as research references. They are
not bundled dependencies or fork parents, and no implementation was copied or
executed. Their differing licenses govern their own code, without changing this
independently authored project's MIT license.

| Project and credited author | Reviewed revision | License and research role |
| --- | --- | --- |
| [Himalayas remote-jobs-api](https://github.com/Himalayas-App/remote-jobs-api), Himalayas Remote Jobs Pty Ltd | [`17ad0bd`](https://github.com/Himalayas-App/remote-jobs-api/tree/17ad0bd7e96faa689ea0b43229618eeb828cfac6) | MIT examples/docs with separate job-data conditions; official API/schema reference. |
| [python-upwork-oauth2](https://github.com/upwork/python-upwork-oauth2), Upwork Corporation | [`9bee35b`](https://github.com/upwork/python-upwork-oauth2/tree/9bee35bdf1545051db1fc268691843332c1b9b71) | Apache-2.0; official OAuth/GraphQL research. API terms and approval remain separate. |
| [freelancer-sdk-python](https://github.com/freelancer/freelancer-sdk-python), Freelancer.com | [`17b8969`](https://github.com/freelancer/freelancer-sdk-python/tree/17b8969d7480f3b9ea38d32e499e6c9bb3dd28b8) | LGPL-3.0 (`LICENSE` and `COPYING.LESSER`); official project endpoint/projection reference. No SDK code copied. |
| [freelancer-mcp-server](https://github.com/godesigntech/freelancer-mcp-server), godesigntech | [`0cb2418`](https://github.com/godesigntech/freelancer-mcp-server/tree/0cb241848f0c2f3ad8d95b3fc06cf95854321b28) | MIT; project pagination, full-description and mutation-boundary review. |
| [upwork-mcp-server](https://github.com/AbbottDevelopments/upwork-mcp-server), Abbott Developments | [`ea94b76`](https://github.com/AbbottDevelopments/upwork-mcp-server/tree/ea94b76fb30a592b4689adf2f01d29d040eb1a19) | MIT; current-schema compatibility review. Its implementation was not adopted. |
| [contra-mcp-starter](https://github.com/alexandernevsky/contra-mcp-starter), Alexander Nevsky | [`453f3fb`](https://github.com/alexandernevsky/contra-mcp-starter/tree/453f3fb19b796421f82104444c5f06c328b8ccad) | MIT; official MCP/account-scope research. No Contra worker-inventory adapter is included. |
| [Upwork C# SDK](https://github.com/tryAGI/Upwork), tryAGI and contributors | [`2ad1d1d`](https://github.com/tryAGI/Upwork/tree/2ad1d1d53076f3a25404f3328bf9505d8dd172d7) | MIT; marketplace/OAuth documentation review. No C# runtime or code is bundled. |

Complete revisions, actual license links and research-only relationships are
retained in [upstream-references.json](upstream-references.json). Credits do not
claim endorsement or verified live operation of those projects.

## Public source documentation

- [Himalayas Remote Jobs API](https://himalayas.app/api): official API contract and source-attribution requirements.
- [Himalayas OpenAPI schema](https://himalayas.app/docs/openapi.json): global browse cursors and salary-period contract.
- [Jobicy Remote Jobs API](https://github.com/Jobicy/remote-jobs-api): official cursor, taxonomy and fair-use documentation.
- [Remotive API documentation](https://github.com/remotive-com/remote-jobs-api): public snapshot, delay and source-use policy. This README-only reference has no declared software license; no documentation text or implementation was copied.
- [Remote OK public feed](https://remoteok.com/api), [We Work Remotely RSS policy](https://weworkremotely.com/remote-job-rss-feed) and [Working Nomads](https://www.workingnomads.com/jobs): official feed discovery and source conditions.
- [Upwork API schema](https://www.upwork.com/developer/documentation/graphql/api/docs/index.html), [developer approval policy](https://support.upwork.com/hc/en-us/articles/115015857647-How-to-request-an-API-key-from-Upwork) and [Freelancer developer portal](https://developer.freelancer.com/): source access and fixed read-operation research.
- [Contra's official MCP](https://contra.com/features/mcp): capability landscape reference. Available talent/admin tooling is not proof of a worker job inventory.
- WUZZUF's public frontend resources and public pages were inspected to verify
  its current undocumented JSON:API contract. The adapter is unofficial; the
  source's [policies](https://wuzzuf.net/policies) remain applicable.
- Forasna, ArabJobs, Bayt and Mostaql public pages were inspected to verify URL,
  pagination and full-text boundaries. They are independent services, and their
  names and content remain owned by their respective rights holders.

## Software dependencies

The Python library uses [lxml](https://lxml.de/). The MCP server uses the
[Model Context Protocol TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
and [Zod](https://github.com/colinhacks/zod). Thank you to their maintainers and
contributors. Dependencies are installed through their package managers and
retain their own licenses; their source trees are not vendored in these projects.

## License boundary

The project MIT license covers the code and documentation authored for these
projects. It does not license job listings, client briefs, source-site assets,
logos, employer content or third-party dependencies. No real vacancy dataset,
browser capture, credential, private person profile or upstream source bundle is
included in these releases. Test payloads are synthetic.

Access and data reuse remain subject to the source's terms, rate limits and
applicable rights. See [SOURCE_POLICY.md](SOURCE_POLICY.md). There is no
affiliation with or endorsement by any source platform.

## Employer-board documentation added in 0.3.0

The independent Greenhouse, Lever and Ashby readers use the providers' public documentation: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), and [Ashby Public Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api). No third-party ATS implementation is copied or bundled. Provider documentation and vacancy-content rights remain separate from this project's MIT code license.
