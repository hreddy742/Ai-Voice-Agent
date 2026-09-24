from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parents[1].parent / "docs" / "developer"


def test_telephony_readiness_audit_keeps_outbound_disabled():
    text = (DOCS_ROOT / "porter-telephony-readiness-audit.mdx").read_text()

    assert "Outbound calls remain disabled" in text
    assert "explicit separate approval" in text
    assert "TCPA" in text
    assert "DNC" in text


def test_salesforce_sync_design_is_design_only():
    text = (DOCS_ROOT / "porter-salesforce-sync-design.mdx").read_text()

    assert "No Salesforce push is implemented" in text
    assert "approved_for_sync" in text
    assert "human reviewer" in text.lower()


def test_production_readiness_report_lists_blockers():
    text = (DOCS_ROOT / "porter-production-readiness-report.mdx").read_text()

    assert "Production outbound calling is not enabled" in text
    assert "KB content is placeholder" in text
    assert "Compliance blockers" in text
