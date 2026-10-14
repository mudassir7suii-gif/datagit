# DataGit Constitution

## Mission
DataGit turns GitHub organizations and repositories into clean, exportable, AI-ready datasets — without forcing developers to build or babysit a crawler.

## Product Standard
We ship a developer SaaS that people can depend on: secure by default, reliable under load, honest about limits, and valuable within the first five minutes.

## Non-Negotiable Principles

### 1. Security & Trust First
- Every sensitive or expensive operation requires authentication and authorization.
- Production fails closed if required secrets are missing.
- CORS is explicit. Credentials and wildcards never mix.
- GitHub tokens are encrypted at rest, tightly scoped, rotatable, and never logged.
- We keep audit trails for crawls, exports, and credential use.
- Privacy, deletion, and data-export rights are product features, not afterthoughts.

### 2. The Crawler Is the Product
- Crawls are background jobs only. HTTP workers never block on GitHub I/O.
- Rate-limit state is shared across all workers and grounded in GitHub’s real quotas.
- We pace requests, apply jitter, and survive 403/429 without burning accounts.
- Incremental updates must actually skip unchanged data.
- Re-running a job must be idempotent.

### 3. Data Integrity Over Speed Theater
- Schema changes go through migrations.
- Uniqueness constraints prevent silent duplicates.
- Writes are batched. Exports stream. Search uses real indexes.
- Multi-tenant isolation is mandatory for SaaS.

### 4. Developer Experience Is Revenue
- Value is obvious before login.
- Time-to-first-successful-crawl is under five minutes.
- CLI, API, and dashboard stay equivalent in capability.
- Docs, examples, and limits are accurate and current.

### 5. Operable Business
- Usage is metered and visible.
- Pricing maps to cost drivers (crawl volume, retention, API, seats).
- We measure reliability with SLOs, not vibes.
- Support and abuse controls exist before scale surprises us.

## Definition of Done (Company Bar)
A change is not done until it is secure, observable, tested at the failure paths that matter, and explainable to a customer in one sentence.
