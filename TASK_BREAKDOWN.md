# DataGit Task Breakdown — Execution Backlog

## Epic P0.1 — Security Perimeter
- [x] Add auth dependencies to jobs, crawl, export, rate-limit, admin, and write routes
- [x] Reject unauthenticated and unauthorized access with consistent errors
- [x] Require DATAGIT_JWT_SECRET and other prod secrets; fail startup if missing
- [x] Configure explicit CORS allowed origins
- [x] Rate-limit sign-in and sign-up; add lockout threshold
- [x] Implement/harden password policy and email verification flow
- [x] Switch session delivery to httpOnly Secure SameSite cookies (or document interim XSS controls)
- [x] Encrypt GitHub tokens at rest; redact secrets in logs
- [x] Add audit events for login, crawl create, export, token add/revoke
- [x] Tests: unauthenticated access, invalid token, auth brute-force behavior

## Epic P0.2 — Async Crawler Foundation
- [x] POST crawl/jobs only enqueues; returns job id immediately
- [x] Worker process consumes jobs and runs orchestrator
- [x] Job states: queued, running, completed, failed (with error payload)
- [x] Remove synchronous crawl from request thread
- [x] Delete or archive legacy datagit.py / dual paths
- [x] Tests: enqueue, worker success, worker failure + status accuracy

## Epic P0.3 — Rate-Limit Safety
- [x] Redis-backed shared TokenManager / quota state
- [x] Hydrate limits from GitHub /rate_limit
- [x] Inter-request pacing + jitter
- [x] 403/429 retry with exponential backoff and job-level surfacing
- [x] Multi-worker verification that quotas are not independently over-consumed
- [x] Tests: simulated 429, shared counter correctness

## Epic P1.1 — Database & Integrity
- [x] Provision Postgres for deployed environments (docker-compose + PostgreSQL 16 + Alembic)
- [x] Introduce Alembic; generate baseline migration
- [x] Add unique constraints for commits and issues
- [x] Batch commits in orchestrator
- [x] Workspace_id tenancy columns + query isolation
- [x] Mark missing/private repos on fetch errors
- [x] Tests: duplicate insertion blocked, migration upgrade/downgrade smoke

## Epic P1.2 — Incremental & Targets
- [x] Support target types: user, org, repo (`owner/repo`)
- [x] Fix detect_target_type / routing
- [x] Use content_hash and timestamps/ETags to skip unchanged entities
- [x] Ensure job re-run is idempotent
- [x] Tests: single-repo crawl, incremental no-op update

## Epic P1.3 — Export & Search Scale
- [x] Stream exports in chunks (JSON/CSV/Parquet)
- [x] Store large exports in object storage with signed download
- [x] Export respects all active filters
- [x] Replace ILIKE-only search with FTS/indexed search
- [x] Export retention cleanup job
- [x] Tests: large export memory bound, filter parity

## Epic P1.4 — Job UX & Dashboard Core
- [x] Job center: list, detail, progress, logs, cancel, retry
- [x] Pagination or infinite scroll for repos
- [x] Repo detail drawer/page (overview, commits, issues)
- [x] Shared filter model for search + export
- [x] Session expiry handling in frontend
- [x] Empty/loading/error states for jobs and lists

## Epic P2.1 — Onboarding & GitHub Connection
- [x] Marketing landing page with clear one-liner and CTA
- [x] Guided first-run: connect GitHub → crawl → results → export
- [x] GitHub App installation flow
- [x] PAT fallback with scope warnings
- [x] Workspace token quota display

## Epic P2.2 — Automation Surface
- [x] API keys (create, revoke, last-used)
- [x] Versioned OpenAPI document
- [x] CLI: login, crawl, jobs, export, search
- [x] Docs site: quickstart, auth, depths, limits, schemas
- [x] Interactive API playground
- [x] Privacy policy, terms, delete-account, export-own-data

## Epic P2.3 — Quality & Delivery
- [x] CI: lint, unit/integration tests, migrate, build
- [x] Preview environments for PRs
- [x] Structured logging + core metrics (queue depth, job outcomes, GitHub remaining)
- [x] Basic status page
- [x] Performance budgets documented and checked on critical paths

## Epic P3.1 — Commercialization
- [x] Usage metering (crawls, API calls, storage)
- [x] Plan limits enforced server-side
- [x] Stripe checkout, portal, webhooks
- [x] In-app upgrade and invoices

## Epic P3.2 — Retention Features
- [x] Webhooks for job and export lifecycle
- [x] Python SDK
- [x] TypeScript SDK
- [x] Saved searches + alert notifications
- [x] Health/activity scores
- [x] Optional summary generation (paid)
- [x] Vector/embeddings export path

## Epic P3.3 — Governance
- [x] Admin abuse controls and token revoke tools
- [x] SLO dashboard and monthly review ritual
- [x] Feature flags for crawler experiments
- [x] Positioning/comparison content aligned to ICPs

## Release Gates
- **Gate A (P0 complete):** external testers allowed on private beta
- **Gate B (P1 complete):** public beta with data-loss risk accepted as low
- **Gate C (P2 complete):** paid launch eligible
- **Gate D (P3 core):** expand self-serve growth spend
