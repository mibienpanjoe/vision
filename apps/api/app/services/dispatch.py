"""Durable publication intent: a failed enqueue remains visibly pending in SQL."""
import os
import uuid
from datetime import UTC, datetime

from app.models.jobs import Job
from dramatiq import Message
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, Retries, ShutdownNotifications, TimeLimit
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session


def configured_broker() -> RedisBroker | None:
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    return RedisBroker(url=url, namespace=os.environ.get("VISION_QUEUE_NAMESPACE", "vision"),
        socket_connect_timeout=2, socket_timeout=2,
        middleware=[AgeLimit(), TimeLimit(), ShutdownNotifications(), Retries(max_retries=2)])


def dispatch_pending(engine, job_id: uuid.UUID | None = None) -> int:
    broker = configured_broker()
    if broker is None:
        return 0
    sent = 0
    try:
        with Session(engine) as db, db.begin():
            query = select(Job).where(Job.status == "queued", Job.dispatched_at.is_(None))
            if job_id is not None:
                query = query.where(Job.id == job_id)
            for job in db.scalars(query.limit(50).with_for_update(skip_locked=True)):
                broker.enqueue(Message(queue_name="probes", actor_name="probe", args=(str(job.id),), kwargs={}, options={}))
                job.dispatched_at = datetime.now(UTC)
                sent += 1
        return sent
    except RedisError:
        # A publish may have reached Redis before a network failure. Redelivery
        # is allowed: execute_probe's SQL transaction prevents duplicate output.
        return 0
    finally:
        broker.close()


def dispatch_narratives(engine, job_id: uuid.UUID | None = None) -> int:
    from app.models.narrative_jobs import NarrativeJob

    broker = configured_broker()
    if broker is None:
        return 0
    try:
        with Session(engine) as db, db.begin():
            query = select(NarrativeJob).where(NarrativeJob.status == "queued", NarrativeJob.dispatched_at.is_(None))
            if job_id is not None:
                query = query.where(NarrativeJob.id == job_id)
            sent = 0
            for job in db.scalars(query.limit(50).with_for_update(skip_locked=True)):
                broker.enqueue(Message(queue_name="narrative", actor_name="narrate", args=(str(job.id),), kwargs={}, options={}))
                job.dispatched_at = datetime.now(UTC)
                sent += 1
        return sent
    except RedisError:
        return 0
    finally:
        broker.close()


def dispatch_ingestions(engine, job_id: uuid.UUID | None = None) -> int:
    from app.models.works import IngestionJob

    broker = configured_broker()
    if broker is None:
        return 0
    try:
        with Session(engine) as db, db.begin():
            query = select(IngestionJob).where(IngestionJob.status == "queued", IngestionJob.dispatched_at.is_(None))
            if job_id is not None:
                query = query.where(IngestionJob.id == job_id)
            sent = 0
            for job in db.scalars(query.limit(50).with_for_update(skip_locked=True)):
                broker.enqueue(Message(queue_name="ingestion", actor_name="ingest", args=(str(job.id),), kwargs={}, options={}))
                job.dispatched_at = datetime.now(UTC)
                sent += 1
        return sent
    except RedisError:
        return 0
    finally:
        broker.close()


def dispatch_renders(engine, job_id: uuid.UUID | None = None) -> int:
    from app.models.renders import RenderJob

    broker = configured_broker()
    if broker is None:
        return 0
    try:
        with Session(engine) as db, db.begin():
            query = select(RenderJob).where(RenderJob.status == "queued", RenderJob.dispatched_at.is_(None))
            if job_id is not None:
                query = query.where(RenderJob.id == job_id)
            sent = 0
            for job in db.scalars(query.limit(50).with_for_update(skip_locked=True)):
                broker.enqueue(Message(queue_name="render", actor_name="render", args=(str(job.id),), kwargs={}, options={}))
                job.dispatched_at = datetime.now(UTC)
                sent += 1
        return sent
    except RedisError:
        # A duplicate publish is harmless: the worker claims each job once.
        return 0
    finally:
        broker.close()


def dispatch_deletions(engine, work_id: uuid.UUID | None = None) -> int:
    from app.models.works import WorkDeletion

    broker = configured_broker()
    if broker is None:
        return 0
    try:
        with Session(engine) as db, db.begin():
            query = select(WorkDeletion).where(WorkDeletion.status != "completed", WorkDeletion.dispatched_at.is_(None))
            if work_id is not None:
                query = query.where(WorkDeletion.work_id == work_id)
            sent = 0
            for deletion in db.scalars(query.limit(50).with_for_update(skip_locked=True)):
                broker.enqueue(Message(queue_name="retention", actor_name="purge_work",
                                       args=(str(deletion.work_id),), kwargs={}, options={}))
                deletion.dispatched_at = datetime.now(UTC)
                sent += 1
        return sent
    except RedisError:
        return 0
    finally:
        broker.close()
