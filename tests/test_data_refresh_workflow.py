# ruff: noqa
from pathlib import Path


WORKFLOW = Path(".github/workflows/data-refresh.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_data_refresh_workflow_is_manual_only() -> None:
    workflow = _workflow_text()

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow


def test_data_refresh_workflow_has_bounded_required_inputs() -> None:
    workflow = _workflow_text()

    assert "prefecture:" in workflow
    assert "default: 埼玉県" in workflow
    assert "max_queries:" in workflow
    assert "default: '1'" in workflow
    assert 'if ! [[ "$MAX_QUERIES" =~ ^[1-9][0-9]*$ ]]' in workflow


def test_data_refresh_workflow_cannot_write_repository_contents() -> None:
    workflow = _workflow_text()

    assert "permissions:\n  contents: read" in workflow
    assert "contents: write" not in workflow
    assert "git commit" not in workflow
    assert "git push" not in workflow
    assert "create-pull-request" not in workflow


def test_data_refresh_workflow_preserves_failure_evidence() -> None:
    workflow = _workflow_text()

    assert "continue-on-error: true" in workflow
    assert workflow.count("if: always()") >= 3
    assert "actions/upload-artifact@v4" in workflow
    assert "artifacts/logs/refresh.log" in workflow
    assert "artifacts/logs/verify.log" in workflow
    assert "artifacts/snapshot-report.json" in workflow
    assert "artifacts/data-changes.diff" in workflow
    assert "artifacts/git-status.txt" in workflow


def test_data_refresh_workflow_enforces_snapshot_quality_gate() -> None:
    workflow = _workflow_text()

    assert "python batch/verify_data.py" in workflow
    assert 'if [ "$REFRESH_OUTCOME" != "success" ]' in workflow
    assert 'if [ "$VERIFY_OUTCOME" != "success" ]' in workflow
    assert "repository data was not committed" in workflow
    assert "json_snapshot_id" in workflow
    assert "sqlite_snapshot_id" in workflow
    assert "manifest_snapshot_id" in workflow
