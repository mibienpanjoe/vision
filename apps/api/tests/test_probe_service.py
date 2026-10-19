import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.access import Principal
from app.models.jobs import Job, JobAttempt
from app.services.probe import execute_probe

pytestmark = pytest.mark.integration


def test_probe_persists_one_result_and_ignores_duplicate_delivery(database):
    with Session(database) as db:
        owner = Principal(username="probe_owner", password_hash="unused test account")
        db.add(owner); db.flush()
        job = Job(owner_id=owner.id, idempotency_key="probe", request_hash="request", value=7,
                  correlation_id=uuid.uuid4().hex)
        db.add(job); db.flush(); job_id = job.id; db.commit()
    execute_probe(str(job_id))
    execute_probe(str(job_id))
    with Session(database) as db:
        result = db.get(Job, job_id)
        assert (result.status, result.result, result.attempts, result.stage) == ("succeeded", 8, 1, "complete")
        assert db.scalar(select(func.count()).select_from(JobAttempt).where(JobAttempt.job_id == job_id)) == 1
