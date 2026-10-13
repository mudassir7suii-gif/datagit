from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
import json
import csv
import io
import re
import time
import pandas as pd
from datagit.config import settings

EXPORT_COLUMNS = [
    "Organization", "Name", "Full_Name", "Description", "Language",
    "Stars", "Forks", "Open_Issues", "URL", "Crawled_At"
]

class DataExporter:
    """Exports structured repository data with streaming support and retention policy."""

    @staticmethod
    def _get_safe_path(filename: str, ext: str) -> Path:
        base = filename[:-len(ext)-1] if filename.endswith(f".{ext}") else filename
        clean_base = re.sub(r"[^\w\-]", "_", base)
        if not clean_base or clean_base == "_":
            clean_base = "datagit_export"
        return settings.export_dir / f"{clean_base}.{ext}"

    @staticmethod
    def repo_to_dict(r) -> Dict[str, Any]:
        return {
            "Organization": r.owner,
            "Name": r.name,
            "Full_Name": r.full_name,
            "Description": r.description,
            "Language": r.language,
            "Stars": r.stars,
            "Forks": r.forks,
            "Open_Issues": r.open_issues,
            "URL": r.url,
            "Crawled_At": r.crawled_at.isoformat() if r.crawled_at else None
        }

    @classmethod
    def stream_csv(cls, query, chunk_size: int = 500) -> Generator[str, None, None]:
        """Streams CSV data chunk by chunk without unbounded memory loads per Constitution Principle 4."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        offset = 0
        while True:
            chunk = query.offset(offset).limit(chunk_size).all()
            if not chunk:
                break
            for repo in chunk:
                writer.writerow(cls.repo_to_dict(repo))
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
            offset += chunk_size

    @classmethod
    def stream_json(cls, query, chunk_size: int = 500) -> Generator[str, None, None]:
        """Streams JSON array chunk by chunk."""
        yield "[\n"
        offset = 0
        first_item = True
        while True:
            chunk = query.offset(offset).limit(chunk_size).all()
            if not chunk:
                break
            for repo in chunk:
                item_json = json.dumps(cls.repo_to_dict(repo), default=str)
                if not first_item:
                    yield ",\n" + item_json
                else:
                    yield item_json
                    first_item = False
            offset += chunk_size
        yield "\n]"

    @classmethod
    def to_csv(cls, data: List[Dict[str, Any]], filename: str) -> Path:
        filepath = cls._get_safe_path(filename, "csv")
        if not data:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                f.write("")
            return filepath

        keys = list(data[0].keys())
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        return filepath

    @classmethod
    def to_json(cls, data: List[Dict[str, Any]], filename: str) -> Path:
        filepath = cls._get_safe_path(filename, "json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return filepath

    @classmethod
    def to_parquet(cls, data: List[Dict[str, Any]], filename: str) -> Path:
        filepath = cls._get_safe_path(filename, "parquet")
        if not data:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(data)
        df.to_parquet(filepath, index=False, engine="pyarrow")
        return filepath

    @classmethod
    def cleanup_old_exports(cls, max_age_hours: int = 24) -> int:
        """Deletes exported files older than max_age_hours per Constitution Principle 4."""
        now = time.time()
        max_age_sec = max_age_hours * 3600
        removed = 0
        for p in settings.export_dir.glob("datagit_*.*"):
            if p.is_file():
                if now - p.stat().st_mtime > max_age_sec:
                    try:
                        p.unlink()
                        removed += 1
                    except Exception:
                        pass
        return removed
