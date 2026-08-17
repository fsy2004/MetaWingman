# Privacy and data flow

MetaWingman is local-first for review state, hashes, provenance, deterministic calculations, and R analysis. The repository and skills-only plugin do not operate a hosted service and do not collect telemetry.

## Data that stays local by default

- project state, protocol, reviewer assignments, event ledger, provenance graph, and benchmark manifests;
- database exports imported by the user;
- PDFs and supplements stored in a review project;
- extraction candidates, appraisal dossiers, analysis inputs/outputs, and claims;
- credentials and institutional browser sessions, which are never copied into the project.

## Data that may leave the machine

- public search queries and identifiers sent to selected scholarly APIs;
- DOI and OA-resolution requests sent to Crossref or Unpaywall;
- content explicitly sent through the host application's selected model or tool provider;
- files uploaded by a user through an explicitly authorized service.

Before sending private, licensed, unpublished, confidential, or personal data to a remote model or tool, the user must verify institutional policy, consent or lawful basis, provider retention and training settings, geographic processing, and the database or publisher license. Local deterministic tools remain available when remote processing is not authorized.

## Accounts and credentials

`credential_capabilities.json` records capability names, environment-variable names, owners, scopes, and status. It never records values. Public scholarly APIs are preferred; commercial database credentials remain in the user's institution-approved interface or secret store.

## Retention and deletion

MetaWingman itself has no central retention system. Files remain wherever the user creates the review project or generated bundle. Users control backups, access permissions, retention, deletion, and any provider-side retention created through external services.
