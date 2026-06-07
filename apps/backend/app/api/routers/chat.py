"""POST /api/chat — SSE stream of the agent loop (docs/components/05 §3).

Router-owns-commit: the streaming generator opens its OWN DB session and commits
only after run_turn finishes, so the per-item row lock spans the whole turn and
a client disconnect still persists the trace + any binding refund.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent import events, loop
from app.api.deps import get_db, get_llm
from app.db.session import SessionLocal
from app.repositories import conversations as conversations_repo
from app.schemas.chat import ChatRequest

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # pairs with nginx proxy_buffering off (spec #7)
    "Connection": "keep-alive",
}


def _bearer_token(authorization: str | None) -> str | None:
    """Extract the capability token from an `Authorization: Bearer <token>`
    header. Returns None for any malformed/absent header."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _stream(conversation_id, message: str, selection, llm) -> Iterator[str]:
    db: Session = SessionLocal()
    gen = loop.run_turn(db, llm, conversation_id, message, selection=selection)
    try:
        for ev in gen:
            yield ev.format()
        db.commit()
    except GeneratorExit:
        # Client disconnected: drive the loop to completion server-side, then
        # commit so the trace + refund persist regardless of the socket.
        gen.close()
        db.commit()
        raise
    except Exception:  # noqa: BLE001 - surface a safe SSE error, never a 500 mid-stream
        gen.close()
        db.rollback()
        yield events.error(
            "internal_error", "The assistant hit an unexpected error."
        ).format()
        yield events.done().format()
    finally:
        db.close()


@router.post("/chat")
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    llm=Depends(get_llm),
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    # Per-conversation capability gate: the caller must present the session
    # token minted at conversation creation. Mismatch/missing → the same opaque
    # 404 as a non-existent conversation (don't reveal existence).
    token = _bearer_token(authorization)
    if conversations_repo.get_for_session(db, body.conversation_id, token) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "conversation_not_found", "message": "Conversation not found."},
        )

    selection = [s.model_dump() for s in body.selection] if body.selection else None
    return StreamingResponse(
        _stream(body.conversation_id, body.message, selection, llm),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
