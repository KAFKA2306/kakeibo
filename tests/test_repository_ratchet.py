from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_finance_flow_contract_exists() -> None:
    required = [
        "src/kakeibo/statement_types.py",
        "src/kakeibo/monthly_snapshot.py",
        "docs/canonical-flow.md",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f"canonical flow contract missing: {missing}"


def test_unrelated_weekly_research_workflow_is_not_reintroduced() -> None:
    workflow = ROOT / ".github/workflows/weekly-repo-research.yml"
    assert not workflow.exists(), (
        "weekly repository research is not part of the canonical finance flow"
    )


def test_canonical_contract_names_three_kpis() -> None:
    text = (ROOT / "docs/canonical-flow.md").read_text(encoding="utf-8")
    for metric in ("自動取込率", "分類・整合成功率", "手動補正量"):
        assert metric in text
