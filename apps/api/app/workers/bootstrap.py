import dramatiq
from app.services.dispatch import configured_broker
from app.services.ingestion.parse import execute_ingestion
from app.services.probe import execute_probe

broker = configured_broker()
if broker is None:
    raise RuntimeError("Configure REDIS_URL before starting a worker")
dramatiq.set_broker(broker)


@dramatiq.actor(queue_name="probes", max_retries=2, min_backoff=1000, max_backoff=5000, time_limit=5000)
def probe(job_id: str) -> None:
    execute_probe(job_id)


# PDF layout extraction is CPU-bound; Docling's own document timeout (600 s)
# fails it first, so this limit only catches a stuck worker.
@dramatiq.actor(queue_name="ingestion", max_retries=2, min_backoff=1000, max_backoff=5000, time_limit=900_000)
def ingest(job_id: str) -> None:
    execute_ingestion(job_id)
