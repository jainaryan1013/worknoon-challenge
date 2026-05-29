"""Model package. Importing it registers every table on Base.metadata, which
is what Alembic's env.py targets for autogenerate / check.
"""

from app.models.base import Base
from app.models.conversation import AgentStep, Conversation, Message
from app.models.crm import Customer, Order, OrderItem
from app.models.policy import PolicyDocument, PolicyRule
from app.models.refunds import Refund

__all__ = [
    "Base",
    "Customer",
    "Order",
    "OrderItem",
    "Refund",
    "Conversation",
    "Message",
    "AgentStep",
    "PolicyDocument",
    "PolicyRule",
]
