import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from state.app_state import GLOBAL_STATE

router = APIRouter(prefix="/api", tags=["Eventos"])

@router.get("/events")
async def sse_events(request: Request):
    async def event_generator():
        q = asyncio.Queue()
        GLOBAL_STATE.event_subscribers.append(q)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if q in GLOBAL_STATE.event_subscribers:
                GLOBAL_STATE.event_subscribers.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
