# DataGit 🚀

> **Turn GitHub repositories into reliable, structured, and intelligent data at scale.**

DataGit is an open-source GitHub data crawler, structured processing pipeline, and intelligence platform. Built in compliance with the **DataGit Constitution**, prioritizing GitHub API rate-limit respect, security by default, and high-quality structured data.

---

## 🌟 Key Features (Phase 1 MVP)

- **First-Class CLI**: Search, crawl, export, and check system status directly from the terminal.
- **Rate-Limit Intelligence**: Automatic `X-RateLimit-*` header inspection, token budgets, and multi-token rotation.
- **Structured Storage**: Versioned relational database schemas (SQLite / PostgreSQL) with data deduplication (`content_hash`).
- **Deep & Configurable Crawling**: Multi-depth extraction (Metadata, Commits, Issues/PRs) with automatic user vs. organization routing.
- **Multi-Format Exports**: One-click exports to **CSV**, **JSON**, and **Apache Parquet**.
- **REST API Gateway**: High-speed FastAPI backend with JWT authentication and bcrypt password hashing.
- **Modern Web Dashboard**: Next.js 16 (Turbopack) + Tailwind CSS dashboard with live search, metrics, and ingestion triggers.

---

## 📁 Architecture Overview

```
Datagit/
├── datagit/                    # Core Python Engine & CLI
│   ├── api/                    # FastAPI REST API Gateway & JWT Auth
│   ├── cli/                    # First-Class Command Line Interface
│   ├── crawler/                # Rate-Limited GitHub API Client & Orchestrator
│   ├── storage/                # Database Models, Engine, and CSV/JSON/Parquet Exporters
│   ├── search/                 # Structured & Full-Text Search Engine
│   ├── core/                   # Token & Rate Limit Pool Manager
│   └── config.py               # Central Settings & Environment Config
├── datagit-frontend/           # Next.js 16 (App Router) + Tailwind Web Dashboard
├── tests/                      # Automated Unit & Integration Test Suite
├── requirements.txt            # Python Dependencies
└── datagit.db                  # Local SQLite Database (pre-indexed with 4,500+ repos)
```

---

## 🛠️ Getting Started

### 1. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the First-Class CLI

```bash
# Check status, rate limits, and dataset insights
python -m datagit.cli.main status

# Search repositories
python -m datagit.cli.main search anthropic --min-stars 1000 --limit 10

# Export dataset to Parquet, JSON, or CSV
python -m datagit.cli.main export --format parquet --owner google --filename google_repos

# Crawl an organization or user
python -m datagit.cli.main crawl vercel --depth metadata --pages 3
```

### 3. Start the REST API Gateway

```bash
python main.py
# API runs on http://127.0.0.1:8000
# Interactive Swagger Documentation: http://127.0.0.1:8000/docs
```

### 4. Start the Web Dashboard

```bash
cd datagit-frontend
npm run dev
# Dashboard available on http://localhost:3000
```

---

## 🧪 Running Tests

```bash
python -m unittest discover tests
```
