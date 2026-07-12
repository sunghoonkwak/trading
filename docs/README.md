# Documentation

Documentation is organized by its purpose, not by the tool or workflow that
created it. Store new documents in the following directories.

| Directory | Purpose |
| --- | --- |
| `docs/guides/` | Durable product, operating, and investment guidance for people. |
| `docs/plans/` | Implementation plans and execution-oriented work breakdowns. |
| `docs/specs/` | Design, requirements, and decision documents that precede implementation. |
| `docs/testing/` | Test strategy, audit records, and verification findings. |
| `docs/reference/` | Checked-in external schemas and API reference material. |

## Placement Rules

- Do not create tool-named documentation roots such as `docs/superpowers/`.
  A document created with any assistant or workflow belongs in the directory
  that matches its content.
- Keep plans and specs separate: a plan explains how work will be done; a spec
  records what or why is being decided.
- Name dated plans and specs with `YYYY-MM-DD-<topic>.md`. Preserve an existing
  historical filename when moving it unless a rename is necessary to prevent a
  collision.
- Add a concise source note when a document depends on another document or an
  external reference. Use repo-relative paths for internal documents.
- Never store credentials, account numbers, tokens, live API payloads, or
  private `KIS_config/` content under `docs/`.

## Current Entry Points

- [Implementation plans](plans/)
- [Design specifications](specs/)
- [Testing records](testing/)
- [Developer references](reference/)
- [Guides](guides/)
- [Layered architecture](architecture.md)

## Architecture Map

Production dependencies flow from `interfaces` to `application` and domain
ports. `infrastructure` implements those ports, while `src/main.py` is the
single composition root. `interfaces/web`, `interfaces/telegram`, and
`interfaces/scheduler` own transport behavior; strategy execution lives in
`application`, and KIS/Toss/file adapters remain in `infrastructure`.
