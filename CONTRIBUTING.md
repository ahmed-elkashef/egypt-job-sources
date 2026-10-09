# Contributing

Changes to source adapters, Arabic text handling, pagination validation, and failure reporting are welcome.

1. Open an issue describing the source and observed behavior without attaching credentials, cookies, private account panels, job-seeker profiles, or a scraped corpus.
2. Use a small **synthetic** fixture that reproduces the structure. Replace real titles, employer names, job IDs, project IDs, dates, and descriptions with constructed examples. Preserve only the technical case, such as an encoded slash or duplicate pagination ID.
3. Keep acquisition separate from eligibility, fit review, or complete market coverage. A block or changed structure must remain an explicit limitation, never an empty success or mock live data.
4. Preserve read-only source boundaries. Do not add login/session export, applications, bids, contact actions, stealth, proxy evasion, or CAPTCHA bypass.
5. Run the offline tests, lint, format check, and package build listed in the README. Do not make live platform requests in CI.

For a potential security defect, avoid posting exploit payloads that expose a real user's data. A minimal synthetic report is sufficient; use the repository owner's GitHub profile to find a private reporting channel if one is available.

If you adapt or copy third-party code, identify the exact repository, commit, license, and affected files, and preserve the required notices. Research references should be credited as references; do not describe this independent implementation as a fork.
