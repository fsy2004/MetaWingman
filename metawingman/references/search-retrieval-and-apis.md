# Search, retrieval, APIs, and accounts

## Contents

1. Search design
2. Source coverage
3. API automation
4. Licensed sources and browser sessions
5. Full-text retrieval
6. Secret and audit policy

## Search design

Build concepts from the question and eligibility criteria, then combine controlled vocabulary, synonyms, spelling variants, acronyms, former names, drug/test aliases, and validated design filters. Test recall against sentinel eligible studies and inspect noise. Peer-review consequential strategies with PRESS when feasible.

Translate separately for every platform. Preserve the exact executed syntax; a conceptual strategy is not a reproducible search.

## Source coverage

Select sources by domain and review profile. Common biomedical layers include:

- PubMed/MEDLINE and another bibliographic implementation when justified;
- CENTRAL and Embase for intervention reviews when access exists;
- Web of Science or Scopus for citation discovery;
- ClinicalTrials.gov, WHO ICTRP, regulatory records, and sponsor results for trials;
- CINAHL, PsycINFO, ERIC, EconLit, IEEE Xplore, or domain indexes;
- CNKI, Wanfang, SinoMed, regional indexes, theses, preprints, conference proceedings, and grey literature when eligibility warrants;
- backward references, forward citations, related-article searching, included-author searching, and existing-review cross-checks.

Database coverage is an empirical project fact. Never claim a source was searched from a plan, login, subscription, or API capability.

## API automation

The bundled scripts support an open, auditable backend:

| Service | Purpose | Credential |
|---|---|---|
| NCBI E-utilities | PubMed search and metadata; PMC links | `NCBI_EMAIL`, optional `NCBI_API_KEY`; identify tool and respect rate limits |
| Europe PMC REST | broad biomedical metadata, OA status, full-text XML | optional contact email |
| ClinicalTrials.gov API v2 | registry search and structured study records | none; capture API version timestamp |
| Crossref REST | DOI metadata verification and enrichment | `CROSSREF_EMAIL`; optional Plus token |
| Unpaywall API v2 | verified OA locations for DOI records | `UNPAYWALL_EMAIL` required |
| OpenAlex API | citation discovery and open scholarly graph | `OPENALEX_API_KEY` when required by current service; optional email/contact parameter |
| Zotero Web API | library import, collections, attachments, metadata | user-created key and library ID; least privilege |

Run small test queries before large retrieval. Batch requests, retry transient failures with backoff, cache raw responses, record server timestamps, and never silently truncate a result set. Compare API count with retrieved unique records and fail when they differ.

## Licensed sources and browser sessions

Embase, Scopus, Web of Science, CENTRAL interfaces, publisher platforms, and institutional discovery services may require subscriptions, accounts, or interactive sessions. Use only APIs/export mechanisms allowed by the user's license. When no approved API exists:

1. prepare the exact query and export instructions;
2. let the user or an authorized signed-in browser execute it;
3. import the untouched export;
4. record platform, database, query, date, count, format, filename, and hash;
5. never simulate coverage from another database.

Do not automate CAPTCHA solving, evade rate limits, share credentials, or scrape contrary to terms.

## Full-text retrieval

Use this order:

1. existing user-provided or institutional files;
2. PMC/Europe PMC open-access services;
3. Unpaywall-resolved OA repository or publisher copy with license metadata;
4. Crossref/publisher TDM link when the license permits;
5. institutional link resolver or authorized manual download;
6. author/repository request.

Store `report_id`, DOI/PMID/PMCID, source URL, access route, license, timestamp, MIME type, byte count, SHA-256, and retrieval status. Quarantine HTML error pages mislabeled as PDFs. Never redistribute copyrighted full text through Git.

## Secret and audit policy

- Read secrets from environment variables or an approved secret manager.
- Never echo secrets, include them in URLs written to logs, store them in YAML/CSV, commit `.env`, or pass them to an unapproved external model.
- Redact authorization headers and cookies from raw logs.
- Store a credential capability manifest containing provider, owner, permitted scopes, rate limit, expiry/rotation note, and last test date, but no secret value.
- Require explicit user authorization before creating accounts, purchasing access, changing subscriptions, or granting new scopes.
