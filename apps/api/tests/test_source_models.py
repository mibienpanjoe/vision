import uuid

import pytest
from app.models.access import Principal
from app.models.works import Document, IngestionJob, Work
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_original_and_job_linkage_and_owner_scoped_creation_identity(database):
    with Session(database) as db:
        owner = Principal(username="source_owner", password_hash="unused synthetic account")
        db.add(owner)
        db.flush()
        work = Work(owner_id=owner.id, title="Synthetic original", idempotency_key="create-one", request_hash="a" * 64)
        db.add(work)
        db.flush()
        document = Document(work_id=work.id, source_ref=uuid.uuid4().hex, sha256="b" * 64, format="txt", byte_count=10)
        db.add(document)
        db.flush()
        job = IngestionJob(document_id=document.id, correlation_id=uuid.uuid4().hex)
        db.add(job)
        db.commit()
        assert job.status == "queued" and job.stage == "awaiting_parser" and job.dispatched_at is None
        assert document.revision == 1 and document.work_id == work.id
        db.add(Work(owner_id=owner.id, title="Duplicate", idempotency_key="create-one", request_hash="c" * 64))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
