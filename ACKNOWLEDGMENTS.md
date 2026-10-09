# Acknowledgments and provenance

Thank you to the maintainers who made Egyptian job-source research easier to
understand. These adapters and the MCP wrapper were implemented independently.
The initial release contains no copied third-party scraper code and carries no
upstream fork history. A reference repository was cloned for inspection; the
public projects are independent implementations, rather than GitHub forks.

## Community references

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

## Public source documentation

- [Himalayas Remote Jobs API](https://himalayas.app/api): official API contract and source-attribution requirements.
- [Jobicy Remote Jobs API](https://github.com/Jobicy/remote-jobs-api): official cursor, taxonomy and fair-use documentation.
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
included in the initial release. Test payloads are synthetic.

Access and data reuse remain subject to the source's terms, rate limits and
applicable rights. See [SOURCE_POLICY.md](SOURCE_POLICY.md). There is no
affiliation with or endorsement by any source platform.
