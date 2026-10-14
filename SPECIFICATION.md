# DataGit Specification — Developer SaaS

## 1. Product Summary
DataGit is a multi-tenant SaaS that crawls GitHub users, organizations, and repositories; stores structured data; provides search and analytics; and exports AI-ready datasets via dashboard, CLI, and API.

**One-liner:** Turn any GitHub org or repo into clean, exportable, AI-ready datasets — without writing a crawler.

## 2. Ideal Customers
- AI / RAG builders needing code and repo corpora
- Data and platform teams tracking org ecosystems
- Security and OSINT researchers (within ToS)
- OSS program offices and internal developer platforms
- Analysts comparing stacks, activity, and health

## 3. Success Criteria (10/10 Bar)
A developer can:
1. Understand the product in 30 seconds
2. Connect GitHub in under 2 minutes
3. Crawl an org/repo without babysitting rate limits
4. Watch job progress and trust the result
5. Search, filter, and export clean data
6. Automate via CLI/API
7. Trust security, isolation, and uptime
8. Know pricing and limits before committing

## 4. Functional Requirements

### 4.1 Security & Trust
- JWT/session auth on jobs, crawl, export, rate-limit, admin, and all writes
- Required secrets in production (`DATAGIT_JWT_SECRET`, DB, encryption keys, Stripe, etc.)
- Explicit CORS origins only
- Auth rate limiting, lockouts, strong passwords, email verification; 2FA roadmap
- Prefer httpOnly + Secure + SameSite cookies for session tokens
- Encrypt GitHub tokens at rest; support rotation; never log secrets
- Audit log: actor, action, target, timestamp, outcome
- Privacy policy, terms, account/data deletion, export-of-own-data, retention policy

### 4.2 Crawler as a Service
- Background-only execution: enqueue → worker → status transitions
- Shared rate-limit store (Redis); hydrate from GitHub `/rate_limit`
- Pacing, jitter, exponential backoff on 403/429
- PAT pools and GitHub App installations per workspace
- Incremental logic via content_hash, ETags, updated_at/pushed_at
- Targets: user, organization, single repo (`owner/repo`)
- Job UX: queued, running, succeeded, failed, retries, logs, cancel, re-run
- Idempotent job execution (no duplicate commits/issues/repos on retry)

### 4.3 Data Integrity & Scale
- Alembic (or equivalent) migrations only — no production `create_all`
- Unique constraints: e.g. `(repo_id, sha)`, `(repo_id, github_number)`
- Batched DB commits
- Postgres as SaaS default; SQLite allowed for local/dev only
- Streaming/chunked exports (JSON, CSV, Parquet)
- Scalable search (FTS or external index); no unbounded `ILIKE '%term%'`
- Detect and mark deleted or privatized repos
- Workspace tenancy: members, roles, isolated data and credentials

### 4.4 Developer Experience
- Public marketing landing: problem, solution, demo, pricing, docs CTA
- Onboarding path: sign up → connect GitHub → first crawl → results → export
- GitHub App install flow (preferred over raw PAT for teams)
- CLI: `login`, `crawl`, `jobs`, `export`, `search` (scriptable, CI-friendly)
- Versioned public REST API + OpenAPI; API keys; optional GraphQL later
- Webhooks: job completed/failed, rate-limit low, export ready
- SDKs: Python and TypeScript
- Docs: quickstart, auth, depths, rate limits, export schemas, examples, limits
- Interactive API playground

### 4.5 Product Surface (Dashboard)
- Pagination or infinite scroll (no hardcoded 30)
- Filters shared by search and export: language, stars, owner, topics, activity, license
- Repo detail: overview, commits, issues/PRs, file summary, health signals
- Job center with live progress, history, errors, logs, retry
- Saved searches and alerts
- Workspace settings: tokens, members, billing, retention, default depth
- Explicit empty, loading, and error states
- Clean session expiry handling (refresh or forced re-auth)

### 4.6 Intelligence Layer
- Versioned, documented export schemas with changelog
- Optional embeddings / vector export path
- Optional repo summaries (README + activity)
- Explainable health/activity scores
- NL query only after structured search and data quality are proven

### 4.7 Business & Operations
- Free tier with clear limits; paid tiers by seats and/or usage
- Visible quotas: crawls, API calls, storage
- Stripe billing, invoices, self-serve upgrade
- Status page
- Observability: metrics, traces, errors, GitHub API health, queue depth
- SLOs: job start latency, export success rate, API availability
- Support channel (email and/or Discord) and docs issues
- Admin: abuse controls, token revoke, support tooling without unsafe impersonation defaults

## 5. Non-Functional Requirements
- No blocking crawl I/O in web request path
- Horizontal worker safety for rate limits
- p95 API latency budget (define numerically in plan)
- Memory-safe exports at 100k+ repo scale
- Automated tests for auth negatives, rate limits, job failure/rollback, export filters, CLI
- CI/CD: lint, test, migrate, deploy, preview environments
- Feature flags for risky crawler changes
- Remove dead code and dual sync/async paths
