from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datagit.storage.models import FeatureFlag
from datagit.storage.database import SessionLocal

DEFAULT_FLAGS = {
    "experimental_search_crawling": {
        "enabled": True,
        "description": "Enable crawling repos via GitHub Global Search & Topics syntax"
    },
    "aggressive_pacing": {
        "enabled": False,
        "description": "Pace requests dynamically based on remaining rate limit"
    },
    "parallel_file_fetch": {
        "enabled": False,
        "description": "Fetch repo commits and issues using parallel async sub-tasks"
    },
    "deep_ast_parsing": {
        "enabled": False,
        "description": "Parse repository code syntax trees for automated classification"
    }
}

class FeatureFlagManager:
    @staticmethod
    def initialize_defaults():
        db: Session = SessionLocal()
        try:
            for flag_name, meta in DEFAULT_FLAGS.items():
                existing = db.query(FeatureFlag).filter(FeatureFlag.name == flag_name).first()
                if not existing:
                    db.add(FeatureFlag(
                        name=flag_name,
                        description=meta["description"],
                        is_enabled=meta["enabled"]
                    ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def is_enabled(flag_name: str, db: Optional[Session] = None) -> bool:
        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True
        try:
            flag = db.query(FeatureFlag).filter(FeatureFlag.name == flag_name).first()
            if flag:
                return flag.is_enabled
            return DEFAULT_FLAGS.get(flag_name, {}).get("enabled", False)
        except Exception:
            return DEFAULT_FLAGS.get(flag_name, {}).get("enabled", False)
        finally:
            if close_session:
                db.close()

    @staticmethod
    def get_all(db: Optional[Session] = None) -> List[Dict]:
        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True
        try:
            flags = db.query(FeatureFlag).all()
            if not flags:
                FeatureFlagManager.initialize_defaults()
                flags = db.query(FeatureFlag).all()
            return [
                {
                    "id": f.id,
                    "name": f.name,
                    "description": f.description,
                    "is_enabled": f.is_enabled,
                    "updated_at": f.updated_at.isoformat() if f.updated_at else None
                }
                for f in flags
            ]
        finally:
            if close_session:
                db.close()

    @staticmethod
    def toggle(flag_name: str, enabled: bool, db: Optional[Session] = None) -> Optional[Dict]:
        close_session = False
        if db is None:
            db = SessionLocal()
            close_session = True
        try:
            flag = db.query(FeatureFlag).filter(FeatureFlag.name == flag_name).first()
            if not flag:
                flag = FeatureFlag(
                    name=flag_name,
                    description=DEFAULT_FLAGS.get(flag_name, {}).get("description", "Custom crawler feature flag"),
                    is_enabled=enabled
                )
                db.add(flag)
            else:
                flag.is_enabled = enabled
            db.commit()
            return {
                "id": flag.id,
                "name": flag.name,
                "description": flag.description,
                "is_enabled": flag.is_enabled,
                "updated_at": flag.updated_at.isoformat() if flag.updated_at else None
            }
        except Exception:
            db.rollback()
            raise
        finally:
            if close_session:
                db.close()
