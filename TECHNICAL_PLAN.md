# DataGit Technical Plan — Path to 10/10 SaaS

## Architecture Direction
- **API / Dashboard:** FastAPI (or current stack) + Next.js
- **Workers:** dedicated job consumers (same repo or worker service)
- **Queue:** Redis-backed (RQ / Celery / BullMQ / ARQ — pick one and standardize)
- **Rate limits:** Redis shared state + GitHub `/rate_limit`
- **DB:** Postgres (SaaS), SQLAlchemy + Alembic
- **Search:** Postgres FTS or OpenSearch/Meilisearch when justified
- **Object storage:** S3-compatible for exports
- **Auth:** session cookies preferred; API keys for automation
- **Billing:** Stripe
- **Obs:** OpenTelemetry + metrics + structured logs

## Priority Roadmap

### P0 — Safe to use at all
**Outcome:** No anonymous abuse; crawls cannot take down the API; GitHub tokens are not burned casually.

1. AuthZ on all sensitive routes (jobs, crawl, export, rate-limit, admin, writes)
2. Fail closed on missing production secrets
3. Fix CORS (explicit origins)
4. Auth endpoint rate limiting + basic lockout
5. Move crawls fully async (enqueue job only in HTTP path)
6. Shared rate-limit state in Redis
7. Real GitHub rate-limit hydration
8. Pacing + jitter + 403/429 backoff
9. Session/token storage hardening (httpOnly cookies path)
10. Encrypt GitHub tokens at rest
11. Minimal audit log for crawl/export/credential events
12. Kill synchronous crawl path and legacy dual code paths

### P1 — Safe to use seriously
**Outcome:** Data is correct under concurrency; exports don’t OOM; users can trust jobs in the UI.

1. Postgres as primary SaaS database
2. Alembic migrations from current models
3. Unique constraints on commits/issues (and equivalent hot paths)
4. Batched writes in orchestrator
5. Streaming exports (JSON/CSV/Parquet)
6. Search indexes / FTS; remove full-table ILIKE pattern
7. content_hash / ETag incremental skips
8. Full target support: user, org, `owner/repo`
9. Job center UI: progress, history, errors, logs, cancel, retry
10. Pagination / infinite scroll
11. Filter parity between search and export
12. Deleted/private repo marking hooks
13. Workspace tenancy foundation (workspace_id on data + credentials)

### P2 — Worth paying for
**Outcome:** Professional onboarding, automation, and credibility.

1. Public landing page (value, demo, pricing CTA, docs)
2. GitHub App install flow
3. First-class CLI parity
4. API keys + versioned OpenAPI
5. Developer docs + quickstart + export schema docs
6. API playground
7. Usage metering UI (remaining quotas)
8. Repo detail views (commits, issues, health)
9. Workspace settings (members, tokens, defaults, retention)
10. Status page (even static + manual at first)
11. CI/CD with migrations and tests gated on merge
12. Privacy policy, terms, deletion/export-of-own-data

### P3 — Hard to leave
**Outcome:** Expansion revenue and retention.

1. Stripe billing + self-serve plans
2. Webhooks (job lifecycle, rate-limit, export ready)
3. Python + TypeScript SDKs
4. Saved searches + alerts
5. Embeddings / vector export path
6. Summaries and health scores (tiered)
7. Admin/abuse tooling
8. SLOs + error budgets reviewed monthly
9. Feature flags for crawler experiments
10. Comparison/positioning page and ICP messaging in-product

## Engineering Rules of Engagement
- P0 merges before any growth experiments.
- No feature in P2–P3 ships if it weakens P0 security or rate-limit guarantees.
- Every job-related feature includes failure-path tests.
- Schema changes require migrations + rollback notes.
- Public API is versioned; breaking changes need a new version or migration window.

## Initial SLO Targets (revise with real traffic)
- API availability: 99.5% monthly
- Job start latency (queue → running): p95 < 30s under normal load
- Export success rate: > 99% for datasets within plan limits
- p95 read API (metadata search): < 500ms on warm indexes
