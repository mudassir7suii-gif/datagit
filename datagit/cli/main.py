import sys
from typing import Optional
import click
import csv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime, timezone
from datagit.config import settings
from datagit.storage.database import init_db, SessionLocal
from datagit.storage.models import CrawlJob, Repository
from datagit.storage.exporters import DataExporter
from datagit.crawler.orchestrator import CrawlOrchestrator
from datagit.crawler.github_client import GitHubClient
from datagit.search.engine import SearchEngine

console = Console()

@click.group()
def cli():
    """DataGit: Intelligent GitHub Repository Mining & Analytics CLI."""
    init_db()

@cli.command()
@click.argument("target")
@click.option("--depth", default="metadata", type=click.Choice(["metadata", "commits", "issues", "full"]), help="Crawl depth")
@click.option("--pages", default=3, type=int, help="Maximum pages to fetch (100 repos/page)")
@click.option("--token", default=None, help="Optional GitHub Personal Access Token")
def crawl(target: str, depth: str, pages: int, token: str):
    """Crawl a GitHub user or organization."""
    console.print(f"[bold cyan]Initiating crawl for:[/bold cyan] [yellow]{target}[/yellow] (depth: {depth}, max_pages: {pages})")
    
    target_type = "repo" if "/" in target else "org"
    db = SessionLocal()
    job = CrawlJob(target=target, target_type=target_type, depth=depth, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    client = None
    if token:
        from datagit.core.token_manager import TokenManager
        tm = TokenManager([token])
        client = GitHubClient(token_manager=tm)

    orchestrator = CrawlOrchestrator(client=client)

    with console.status(f"[bold green]Crawling {target} from GitHub API..."):
        try:
            completed_job = orchestrator.run_job(job.id, max_pages=pages)
            console.print(f"[bold green][OK] Crawl completed![/bold green] Found {completed_job.total_found} repos, saved {completed_job.items_crawled} items.")
        except Exception as e:
            console.print(f"[bold red][FAIL] Crawl failed:[/bold red] {e}")
            sys.exit(1)
        finally:
            db.close()

@cli.command()
@click.argument("keyword", required=False)
@click.option("--language", default=None, help="Filter by programming language")
@click.option("--owner", default=None, help="Filter by owner/organization")
@click.option("--min-stars", default=0, type=int, help="Minimum stars")
@click.option("--limit", default=15, type=int, help="Maximum results to display")
def search(keyword: str, language: str, owner: str, min_stars: int, limit: int):
    """Search structured repositories in local database."""
    db = SessionLocal()
    res = SearchEngine.query_repositories(
        db, keyword=keyword, language=language, owner=owner, min_stars=min_stars, limit=limit
    )
    db.close()

    table = Table(title=f"Repositories Search Results (Total Found: {res['total']})")
    table.add_column("Repository", style="cyan", min_width=25)
    table.add_column("Language", style="magenta", min_width=10)
    table.add_column("Stars", style="yellow", justify="right", no_wrap=True, min_width=8)
    table.add_column("Forks", justify="right", no_wrap=True, min_width=8)
    table.add_column("URL", style="blue")

    for r in res["items"]:
        table.add_row(
            r["full_name"],
            r["language"] or "-",
            f"{r['stars']:,}",
            str(r["forks"]),
            r["url"]
        )

    console.print(table)

@cli.command()
@click.option("--format", "export_format", default="csv", type=click.Choice(["csv", "json", "parquet"]), help="Output format")
@click.option("--search", "search_term", default=None, help="Filter export by keyword")
@click.option("--owner", default=None, help="Filter export by organization/owner")
@click.option("--language", default=None, help="Filter export by language")
@click.option("--min-stars", default=0, type=int, help="Minimum stars")
@click.option("--filename", default="datagit_export", help="Output filename base")
def export(export_format: str, search_term: str, owner: str, language: str, min_stars: int, filename: str):
    """Export stored repositories to CSV, JSON, or Parquet."""
    db = SessionLocal()
    query = db.query(Repository).filter(Repository.is_deleted.isnot(True))
    if search_term and search_term.strip():
        term = f"%{search_term.strip()}%"
        query = query.filter((Repository.name.ilike(term)) | (Repository.full_name.ilike(term)) | (Repository.description.ilike(term)))
    if owner:
        query = query.filter(Repository.owner.ilike(owner.strip()))
    if language:
        query = query.filter(Repository.language.ilike(language.strip()))
    if min_stars and min_stars > 0:
        query = query.filter(Repository.stars >= min_stars)
    repos = query.all()
    db.close()

    if not repos:
        console.print("[yellow]No repositories found matching export criteria.[/yellow]")
        return

    data = [DataExporter.repo_to_dict(r) for r in repos]

    if export_format == "csv":
        path = DataExporter.to_csv(data, filename)
    elif export_format == "json":
        path = DataExporter.to_json(data, filename)
    elif export_format == "parquet":
        path = DataExporter.to_parquet(data, filename)

    DataExporter.cleanup_old_exports(max_age_hours=24)
    console.print(f"[bold green][OK] Successfully exported {len(data)} repositories to:[/bold green] [cyan]{path}[/cyan]")

@cli.command()
def status():
    """Display system status, rate limits, and dataset statistics."""
    db = SessionLocal()
    insights = SearchEngine.get_insights(db)
    db.close()

    client = GitHubClient()
    rate_summary = client.token_manager.get_summary()

    console.print(Panel(
        f"[bold white]DataGit System Status & Intelligence[/bold white]\n\n"
        f"  * Total Repositories Stored: [bold green]{insights['total_repositories']:,}[/bold green]\n"
        f"  * Total Stars Indexed: [bold yellow]{insights['total_stars']:,}[/bold yellow]\n"
        f"  * Active Tokens in Pool: [bold cyan]{rate_summary['active_tokens_count']}[/bold cyan]\n"
        f"  * Total Rate Limit Remaining: [bold cyan]{rate_summary['total_remaining_requests']:,} / {rate_summary['total_limit']:,}[/bold cyan]",
        title="DataGit Status", border_style="cyan"
    ))

    if insights["top_languages"]:
        lang_table = Table(title="Top Programming Languages in Dataset")
        lang_table.add_column("Language", style="magenta")
        lang_table.add_column("Repository Count", justify="right", style="green")
        for item in insights["top_languages"]:
            lang_table.add_row(item["language"], str(item["count"]))
        console.print(lang_table)

def _safe_int(val, default: int = 0) -> int:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return int(val)
    val_str = str(val).replace(",", "").strip()
    try:
        return int(float(val_str))
    except (ValueError, TypeError):
        return default

def _extract_owner_from_url(url: str | None) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    clean = url.rstrip("/")
    parts = clean.split("/")
    if len(parts) >= 2 and "github.com" in clean:
        return parts[-2], parts[-1]
    return None, None

@cli.command("import-csv")
@click.argument("csv_path", default="ai_repos_dataset.csv")
def import_csv(csv_path: str):
    """Import an existing CSV dataset into DataGit's structured database."""
    console.print(f"[bold cyan]Importing repositories from {csv_path}...[/bold cyan]")
    db = SessionLocal()
    count = 0
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_org = row.get("Organization") or row.get("owner")
                raw_name = row.get("Name") or row.get("name")
                raw_url = row.get("URL") or row.get("url")

                url_owner, url_name = _extract_owner_from_url(raw_url)
                org = (raw_org.strip() if raw_org else None) or url_owner or "unknown"
                name = (raw_name.strip() if raw_name else None) or url_name
                if not name:
                    continue
                full_name = f"{org}/{name}"
                if db.query(Repository).filter(Repository.full_name == full_name).first():
                    continue

                repo = Repository(
                    owner=org,
                    name=name,
                    full_name=full_name,
                    description=row.get("Description") or row.get("description"),
                    language=row.get("Language") or row.get("language"),
                    stars=_safe_int(row.get("Stars") or row.get("stars")),
                    forks=_safe_int(row.get("Forks") or row.get("forks")),
                    open_issues=_safe_int(row.get("Open Issues") or row.get("open_issues")),
                    url=raw_url or f"https://github.com/{full_name}",
                    crawled_at=datetime.now(timezone.utc)
                )
                repo.content_hash = repo.generate_hash()
                db.add(repo)
                count += 1
                if count % 500 == 0:
                    db.commit()
            db.commit()
        console.print(f"[bold green][OK] Import finished![/bold green] Added {count:,} repositories to database.")
    except Exception as e:
        console.print(f"[bold red][FAIL] Import error:[/bold red] {e}")
    finally:
        db.close()

@cli.command()
@click.option("--email", prompt="Email address", help="User account email")
@click.option("--password", prompt=True, hide_input=True, help="User account password")
@click.option("--api-url", default="http://127.0.0.1:8000", help="DataGit API Gateway URL")
def login(email: str, password: str, api_url: str):
    """Authenticate with DataGit and store session credentials locally for CI/scripting."""
    import requests
    from pathlib import Path
    import json

    console.print(f"[bold cyan]Authenticating with DataGit API at {api_url}...[/bold cyan]")
    try:
        res = requests.post(
            f"{api_url.rstrip('/')}/api/auth/signin",
            json={"email": email.strip(), "password": password},
            timeout=10
        )
        if res.status_code != 200:
            console.print(f"[bold red][FAIL] Authentication failed ({res.status_code}):[/bold red] {res.text}")
            sys.exit(1)
        
        data = res.json()
        token = data.get("access_token")
        creds_dir = Path.home() / ".datagit"
        creds_dir.mkdir(parents=True, exist_ok=True)
        creds_file = creds_dir / "credentials.json"
        with open(creds_file, "w", encoding="utf-8") as f:
            json.dump({"email": email.strip(), "access_token": token, "api_url": api_url}, f, indent=2)
        
        console.print(f"[bold green][OK] Successfully authenticated as {email}![/bold green]")
        console.print(f"[dim]Credentials saved to {creds_file}[/dim]")
    except Exception as e:
        console.print(f"[bold red][FAIL] Connection error:[/bold red] {e}")
        sys.exit(1)

@cli.command()
@click.option("--limit", default=20, type=int, help="Maximum jobs to list")
@click.option("--cancel", "cancel_id", default=None, type=int, help="Job ID to cancel")
@click.option("--rerun", "rerun_id", default=None, type=int, help="Job ID to re-enqueue")
def jobs(limit: int, cancel_id: Optional[int], rerun_id: Optional[int]):
    """Inspect, cancel, or re-run background crawl jobs."""
    db = SessionLocal()
    try:
        if cancel_id:
            job = db.query(CrawlJob).filter(CrawlJob.id == cancel_id).first()
            if not job:
                console.print(f"[bold red]Job #{cancel_id} not found.[/bold red]")
                return
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            console.print(f"[bold green]Job #{cancel_id} has been cancelled.[/bold green]")
            return

        if rerun_id:
            job = db.query(CrawlJob).filter(CrawlJob.id == rerun_id).first()
            if not job:
                console.print(f"[bold red]Job #{rerun_id} not found.[/bold red]")
                return
            new_job = CrawlJob(
                target=job.target,
                target_type=job.target_type,
                depth=job.depth,
                status="queued"
            )
            db.add(new_job)
            db.commit()
            db.refresh(new_job)
            console.print(f"[bold green]Job #{rerun_id} re-enqueued as Job #{new_job.id} for {new_job.target}.[/bold green]")
            return

        job_list = db.query(CrawlJob).order_by(CrawlJob.id.desc()).limit(limit).all()
        table = Table(title=f"Background Crawl Jobs (Latest {len(job_list)})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Target", style="bold white")
        table.add_column("Type", style="dim")
        table.add_column("Depth", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Progress", justify="right")
        table.add_column("Started", style="dim")

        for j in job_list:
            status_style = "green" if j.status == "completed" else "yellow" if j.status in ("queued", "running") else "red"
            table.add_row(
                f"#{j.id}",
                j.target,
                j.target_type,
                j.depth,
                f"[{status_style}]{j.status}[/{status_style}]",
                f"{j.items_crawled} / {j.total_found if j.total_found > 0 else '-'}",
                j.created_at.strftime("%Y-%m-%d %H:%M") if j.created_at else "-"
            )
        console.print(table)
    finally:
        db.close()

if __name__ == "__main__":
    cli()
