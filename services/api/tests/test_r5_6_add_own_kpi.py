"""The MCP tool add_own_kpi passes the names kpis.add_definition reads (found by the backup and restore test, 16 Nov
2026: the tool sent entity_type and attribute, the KPI code reads entity_type_code and attribute_code, so every KPI an
AI tried to add was refused with "Choose the entity type the KPI counts or adds up")."""

import asyncio

from eax import kpis, mcp_more, mcp_ops


def test_add_own_kpi_hands_the_kpi_code_the_names_it_reads(monkeypatch):
    seen = {}

    async def operate(tool, args, confirm, preview, apply, label=""):
        seen["apply"] = apply
        return {}
    monkeypatch.setattr(mcp_ops, "operate", operate)
    monkeypatch.setattr(kpis, "add_definition", lambda conn, model, user, body: seen.setdefault("body", body))
    asyncio.run(mcp_more.add_own_kpi("m", "Applications on Windows", "sum", "ApplicationComponent", attribute="Cost",
                                     filter_attribute="OS", filter_op="equals", filter_value="Windows"))
    seen["apply"](None, None)
    b = seen["body"]
    assert b["entity_type_code"] == "ApplicationComponent" and b["attribute_code"] == "Cost"
    assert b["filter_attribute"] == "OS" and b["filter_op"] == "equals" and b["filter_value"] == "Windows"
    assert "entity_type" not in b and "attribute" not in b
