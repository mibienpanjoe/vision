import dramatiq
from app.services.dispatch import configured_broker
from app.services.probe import execute_probe

broker = configured_broker()
if broker is None:
    raise RuntimeError("Configure REDIS_URL before starting a worker")
dramatiq.set_broker(broker)


@dramatiq.actor(queue_name="probes", max_retries=2, min_backoff=1000, max_backoff=5000, time_limit=5000)
def probe(job_id: str) -> None:
    execute_probe(job_id)
