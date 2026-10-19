import asyncio

import pytest
from app.api.v1 import works
from app.core.errors import PublicError
from starlette.requests import Request


def test_slow_upload_times_out_before_creating_any_source(monkeypatch):
    monkeypatch.setattr(works, "UPLOAD_SECONDS", 0.01)

    async def receive():
        await asyncio.sleep(1)
        return {"type": "http.request", "body": b"never consumed", "more_body": False}

    request = Request({"type": "http", "method": "POST", "path": "/v1/works", "query_string": b"",
                       "headers": [(b"content-type", b"multipart/form-data; boundary=x")]}, receive)
    with pytest.raises(PublicError) as error:
        asyncio.run(works.upload(request, "synthetic", None, None))
    assert error.value.status == 408 and error.value.code == "SOURCE_TIMEOUT"
