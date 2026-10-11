from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import csv
import re
import pandas as pd
from datagit.config import settings

class DataExporter:
    """Exports structured repository data to CSV, JSON, and Parquet."""

    @staticmethod
    def _get_safe_path(filename: str, ext: str) -> Path:
        base = filename[:-len(ext)-1] if filename.endswith(f".{ext}") else filename
        # Replace path separators and illegal characters with underscore
        clean_base = re.sub(r"[^\w\-]", "_", base)
        if not clean_base or clean_base == "_":
            clean_base = "datagit_export"
        return settings.export_dir / f"{clean_base}.{ext}"

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
