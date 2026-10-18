# DataGit Service Level Objectives (SLOs) & Reliability Engineering

This document establishes the operational Service Level Objectives (SLOs), Service Level Indicators (SLIs), error budgets, and the Monthly Reliability Review ritual for the DataGit SaaS platform per Epic P3.3.

---

## 1. Core Service Level Indicators & Objectives

| Objective / Service Target | SLI Measurement | SLO Target | Error Budget | Monitoring Source |
| :--- | :--- | :--- | :--- | :--- |
| **Crawl Job Start Latency** | Time from enqueue (`crawl_jobs.created_at`) to status transition to `running` | **p95 < 5.0 seconds** | 5% exceeding 5s | `crawl_jobs` timestamps |
| **Export Success Rate** | Ratio of successfully streamed & stored exports to total requested exports | **>= 99.5%** | 0.5% failed exports | `export_artifacts` & audit logs |
| **Search & API Query Latency**| p95 response time for `/api/search` and `/api/repositories` | **p95 < 200 ms** | 5% exceeding 200ms | Prometheus / API middleware |
| **GitHub Token Rate-Safety** | Percentage of crawl requests made without triggering unmanaged 403/429 lockout | **>= 99.9%** | 0.1% hard lockout rate | `rate_limit_states` & worker logs |
| **Platform Availability** | Successful HTTP responses (2xx/3xx/4xx business logic vs 5xx infrastructure failure) | **>= 99.9%** | 43m 49s downtime / month | Health check probe & status page |

---

## 2. Real-Time Telemetry & Monitoring Endpoints

DataGit exposes real-time SLI metrics via the authenticated administrative telemetry API:
- `GET /api/admin/slos`: Returns live aggregated SLI metrics computed from historical crawl jobs, export logs, and rate-limit states.
- `GET /api/status`: Public unauthenticated health and system availability probe.

---

## 3. Monthly Reliability Review Ritual

On the **first Tuesday of every calendar month**, the engineering team conducts the DataGit Reliability Review:

### Review Checklist:
1. **Error Budget Consumption Analysis:**
   - Inspect total remaining error budget for Crawl Start Latency, Export Success Rate, and API p95.
   - If error budget consumed > 50% in any category, freeze non-essential feature deployment and prioritize reliability tasks.
2. **Rate Limit & Token Pool Health:**
   - Review active workspace token pools, average consumption per worker, and retry pacing jitter effectiveness.
3. **Storage Retention & Disk Usage:**
   - Verify that automated export artifact cleanup jobs have purged expired artifacts (> 7 days).
4. **Action Item Tracking:**
   - Document any incident post-mortems and schedule corrective engineering items in the next sprint backlog.
