import time
import logging
from datagit.storage.database import SessionLocal, init_db
from datagit.storage.models import CrawlJob
from datagit.crawler.orchestrator import CrawlOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("datagit.worker")

def run_worker(poll_interval: float = 2.0, once: bool = False):
    """Polls database for queued background jobs and processes them with CrawlOrchestrator."""
    init_db()
    orchestrator = CrawlOrchestrator()
    logger.info("DataGit Background Job Worker started. Listening for queued crawl jobs...")

    while True:
        db = SessionLocal()
        try:
            job = (
                db.query(CrawlJob)
                .filter(CrawlJob.status == "queued")
                .order_by(CrawlJob.created_at.asc())
                .first()
            )
            if job:
                job_id = job.id
                target = job.target
                logger.info(f"Consuming Job #{job_id} (Target: {target}, Depth: {job.depth})")
                db.close()
                try:
                    orchestrator.run_job(job_id)
                    logger.info(f"Job #{job_id} completed successfully.")
                except Exception as e:
                    logger.error(f"Job #{job_id} failed: {e}")
            else:
                db.close()
                if once:
                    break
                time.sleep(poll_interval)
        except Exception as e:
            logger.error(f"Worker iteration error: {e}")
            try:
                db.close()
            except Exception:
                pass
            if once:
                break
            time.sleep(poll_interval)

if __name__ == "__main__":
    run_worker()
