"""ToolContext — the server-side trust boundary (docs/components/03 §2).

Identity is NOT model-controlled. `verified_customer_id` and `conversation_id`
are injected by the agent loop from server-side conversation state, never from
tool arguments. A tool reads identity from here, so an attacker cannot pass
someone else's customer id as a parameter.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass
class ToolContext:
    db: Session
    conversation_id: uuid.UUID | None
    verified_customer_id: uuid.UUID | None = None
