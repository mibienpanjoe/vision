"""A bounded JSON route for small, non-provider operations."""

import asyncio

from fastapi import Request
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException


class BoundedJsonRoute(APIRoute):
    seconds: float | None = 10

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            received = 0

            async def receive():
                nonlocal received
                message = await request.receive()
                received += len(message.get("body", b""))
                if received > 32768:
                    raise HTTPException(413)
                return message

            try:
                async with asyncio.timeout(self.seconds):
                    return await original(Request(request.scope, receive))
            except TimeoutError:
                raise HTTPException(408) from None

        return handler


class BoundedBodyRoute(BoundedJsonRoute):
    """Body-capped like BoundedJsonRoute; provider-backed composition bounds its own time."""
    seconds = None
