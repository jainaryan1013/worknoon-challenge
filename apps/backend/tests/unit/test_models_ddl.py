"""Schema shape: the migrated DB matches the §4 DDL contract."""

from __future__ import annotations

from sqlalchemy import inspect

EXPECTED_TABLES = {
    "customers",
    "orders",
    "order_items",
    "refunds",
    "conversations",
    "messages",
    "agent_steps",
    "policy_documents",
    "policy_rules",
}


def test_all_tables_present(engine):
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables


def test_refunds_have_no_uniqueness_on_order_or_item(engine):
    """Partial quantity requires multiple refunds per item: no unique index."""
    insp = inspect(engine)
    unique_cols = {tuple(u["column_names"]) for u in insp.get_unique_constraints("refunds")}
    index_cols = {tuple(i["column_names"]) for i in insp.get_indexes("refunds") if i["unique"]}
    forbidden = {("order_id",), ("order_item_id",)}
    assert not (forbidden & unique_cols)
    assert not (forbidden & index_cols)


def test_agent_steps_step_no_unique_per_conversation(engine):
    insp = inspect(engine)
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("agent_steps")}
    assert ("conversation_id", "step_no") in uniques


def test_money_columns_are_numeric(engine):
    insp = inspect(engine)
    for table, col in [("orders", "total_amount"), ("order_items", "unit_price"), ("refunds", "amount")]:
        column = next(c for c in insp.get_columns(table) if c["name"] == col)
        assert "NUMERIC" in str(column["type"]).upper()
