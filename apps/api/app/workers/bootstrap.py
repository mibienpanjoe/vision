import dramatiq
from app.services.dispatch import configured_broker
from app.services.ingestion.parse import execute_ingestion
from app.services.narrative.pipeline import execute_narrative
from app.services.probe import execute_probe
from app.services.visualization.render import execute_render

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


# Provider calls are individually bounded (120 s, three calls per batch); this
# limit only catches a stuck worker. Stages are idempotent under redelivery.
@dramatiq.actor(queue_name="narrative", max_retries=2, min_backoff=1000, max_backoff=5000, time_limit=3_600_000)
def narrate(job_id: str) -> None:
    execute_narrative(job_id)


# Image calls are charged and not idempotent at the provider: no retries, and a
# redelivered claimed job settles as acceptance unknown instead of calling again.
@dramatiq.actor(queue_name="render", max_retries=0, time_limit=300_000)
def render(job_id: str) -> None:
    execute_render(job_id)
