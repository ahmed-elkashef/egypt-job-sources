# Official employer ATS readers

The `egypt_job_sources.ats` module reads an explicitly identified employer's
public Greenhouse, Lever or Ashby board. It does not infer a board token from a
domain, discover employers, apply, access applicants or select jobs for a person.
Keep live output outside Git. Its fixtures are entirely synthetic.

## Commands

Replace `VERIFIED_BOARD_TOKEN` and `SOURCE_POSTING_ID` with values established
from the employer's official careers page and returned source response.

```sh
python -m egypt_job_sources.ats --capabilities
python -m egypt_job_sources.ats --source greenhouse --board VERIFIED_BOARD_TOKEN
python -m egypt_job_sources.ats --source greenhouse --board VERIFIED_BOARD_TOKEN --job-id SOURCE_POSTING_ID
python -m egypt_job_sources.ats --source lever --board VERIFIED_BOARD_TOKEN --skip 0 --limit 100
python -m egypt_job_sources.ats --source lever --board VERIFIED_BOARD_TOKEN --region eu --skip 100 --limit 100
python -m egypt_job_sources.ats --source lever --board VERIFIED_BOARD_TOKEN --job-id SOURCE_POSTING_ID
python -m egypt_job_sources.ats --source ashby --board VERIFIED_BOARD_TOKEN
```

Lever alone accepts `--region global|eu` and `--skip`/`--limit`. Its limit is a
page size, not a board census cap. Use the returned `pagination.next_skip` after
every nonempty response, including a short page. A successful empty response
marks `page_exhaustion_observed`; moving offset inventory still needs cross-page
identity reconciliation. No native total or stable historical snapshot is
invented. Ashby has no documented individual public detail endpoint.

Lever board reads also accept repeated `--commitment 'EXACT_OBSERVED_LABEL'`
arguments. Use one to twenty distinct nonempty labels, at most 200 characters
each, from this verified employer board's native `categories.commitment`
taxonomy. Values are repeated native parameters with case-sensitive OR matching;
repeat the exact same set on every continuation. Other providers, individual
details and capability requests refuse these filters.

Filtered responses preserve full text, raw counts and offsets, with
`source_filters` and returned-label verification. Known contradictory labels
fail as a source limitation; missing/non-string/mixed metadata stays
undetermined without dropping rows. Even an empty filtered terminal keeps
`board_snapshot_complete=false`. Retain the broad board's unknown, other-label
and contradictory full-time complement before assessing complete supply.
No universal type vocabulary, part-time hours or country eligibility is inferred.

Greenhouse returns its whole public job-post list with `content=true` and checks
`meta.total` against its returned count. Details request pay-transparency fields,
without application questions. Posting `id` and `internal_job_id` are separate:
one underlying job may have several public posts, while prospect posts have a
null internal ID. [Official Job Board API](https://docs.greenhouse.io/job-board.html).

Lever retains the combined body, all requirements/benefit lists, closing content
and salary-description text. Its global/EU hosts and public list/detail routes
are fixed. [Official Postings API](https://github.com/lever/postings-api).

Ashby preserves HTML/plaintext, secondary locations and compensation units.
`isListed=false` content is excluded with a digest/count receipt. Identity uses
the canonical public job URL because the documented public schema does not
require a native posting-ID field. `publishedAt` is **last published**, not
guaranteed first publication. [Official public API](https://developers.ashbyhq.com/docs/public-job-posting-api).

## Result and source limits

Every successful page contains `listings`, `returned_count`, native pagination
evidence and limits. A detail contains one `listing`. Each posting preserves
complete returned `description`, `description_html`, `description_sections`,
whitelisted native `source_data`, stable identity and raw date/location/work-model/
compensation fields. Missing description text retains the card with
`missing_full_description`; it does not silently omit supply.

`board_snapshot_complete` describes a valid whole Greenhouse/Ashby response.
It never certifies Egyptian, remote-eligible, historical or weekly market supply.
`coverage_complete` and `reviewed_by_model` always remain false. Greenhouse list
updates and optional undocumented Lever timestamps are not original-publication
proof. Remote/contract/internship labels do not prove Egypt access or part-time
hours. Do those checks after reading the full posting; do not add keyword,
title, skill, seniority, salary or candidate filters to acquisition.

Only fixed anonymous HTTPS GET endpoints are fetched. Cross-host redirects,
unsupported query parameters, credentials, malformed JSON, count contradictions and
schema failures return `source_limited` with exit code 2 and **no empty inventory
or fabricated count**. Valid successful empty responses remain explicit `ok`
observations for that board. The transport has a 35-second timeout and 25 MiB
response limit; exceeding a bound fails instead of clipping text.

## Employer seed authority

A consuming application should maintain its own versioned seed registry with
employer identity, official domain/careers URL, provider, exact board token,
Lever region, discovery-evidence URL, verification date and verification state.
Obtain seeds from the declared geography/sector census and direct employer
links. A global software-company registry is not the Egyptian labor market;
missing employers and unsupported ATS types remain separate source gaps.

Record each board/page's endpoint, observation time, returned/source counts,
IDs, missing descriptions and continuation/exhaustion evidence. Read surviving
Greenhouse details for `first_published` when the original publication date is
needed. Track first observation, original publication, update and republication
separately. Do not merge development probes into a frozen sourcing interval.
