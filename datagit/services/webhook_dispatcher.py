import json
import hmac
import hashlib
import uuid
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from datagit.storage.database import SessionLocal
from datagit.storage.models import Webhook

logger = logging.getLogger("datagit.webhooks")

class WebhookDispatcher:
    """Asynchronous Webhook Event Dispatcher with HMAC-SHA256 Signatures."""

    @classmethod
    def compute_signature(cls, secret: str, payload_bytes: bytes) -> str:
        return f"sha256={hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()}"

    @classmethod
    def _send_http_post(cls, url: str, headers: Dict[str, str], payload_bytes: bytes, timeout: int = 5) -> bool:
        req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return 200 <= resp.status < 300
        except Exception as e:
            logger.warning(f"Webhook delivery failed for {url}: {e}")
            return False

    @classmethod
    def dispatch_event(
        cls,
        event_name: str,
        data: Dict[str, Any],
        user_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        async_dispatch: bool = True
    ) -> int:
        """Dispatches an event to all matching active webhooks."""
        def _dispatch_task():
            db: Session = SessionLocal()
            try:
                query = db.query(Webhook).filter(Webhook.is_active == True)
                if user_id is not None:
                    query = query.filter(Webhook.user_id == user_id)
                elif workspace_id is not None:
                    query = query.filter(Webhook.workspace_id == workspace_id)

                webhooks = query.all()
                matching_webhooks: List[Webhook] = []
                for wh in webhooks:
                    allowed_events = [e.strip().lower() for e in wh.events.split(",") if e.strip()]
                    if "*" in allowed_events or event_name.lower() in allowed_events:
                        matching_webhooks.append(wh)

                if not matching_webhooks:
                    return

                delivery_id = str(uuid.uuid4())
                timestamp_str = datetime.now(timezone.utc).isoformat()
                payload_dict = {
                    "id": delivery_id,
                    "event": event_name,
                    "timestamp": timestamp_str,
                    "data": data
                }
                payload_bytes = json.dumps(payload_dict, default=str).encode("utf-8")

                for wh in matching_webhooks:
                    sig = cls.compute_signature(wh.secret, payload_bytes)
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": "DataGit-Webhooks/1.0",
                        "X-DataGit-Event": event_name,
                        "X-DataGit-Delivery": delivery_id,
                        "X-DataGit-Signature": sig
                    }
                    success = cls._send_http_post(wh.url, headers, payload_bytes)
                    wh.last_triggered_at = datetime.now(timezone.utc)
                    if success:
                        wh.failure_count = 0
                    else:
                        wh.failure_count = (wh.failure_count or 0) + 1

                db.commit()
            except Exception as e:
                logger.error(f"Error dispatching webhook event '{event_name}': {e}", exc_info=True)
            finally:
                db.close()

        if async_dispatch:
            thread = threading.Thread(target=_dispatch_task, daemon=True)
            thread.start()
            return 1
        else:
            _dispatch_task()
            return 1

    @classmethod
    def test_webhook(cls, webhook: Webhook) -> Dict[str, Any]:
        """Sends a synchronous ping event to verify webhook URL and secret connectivity."""
        delivery_id = str(uuid.uuid4())
        payload_dict = {
            "id": delivery_id,
            "event": "ping",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "message": "DataGit webhook test delivery",
                "webhook_id": webhook.id
            }
        }
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        sig = cls.compute_signature(webhook.secret, payload_bytes)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "DataGit-Webhooks/1.0",
            "X-DataGit-Event": "ping",
            "X-DataGit-Delivery": delivery_id,
            "X-DataGit-Signature": sig
        }

        success = cls._send_http_post(webhook.url, headers, payload_bytes, timeout=4)
        return {
            "delivery_id": delivery_id,
            "success": success,
            "signature": sig,
            "url": webhook.url
        }

webhook_dispatcher = WebhookDispatcher()
