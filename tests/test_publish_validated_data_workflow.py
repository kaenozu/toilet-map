from pathlib import Path


WORKFLOW = Path(".github/workflows/publish-validated-data.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_publisher_is_manual_and_requires_run_id() -> None:
    workflow = _workflow_text()

    assert "workflow_dispatch:" in workflow
    assert "run_id:" in workflow
    assert "schedule:" not in workflow
    assert "workflow_run:" not in workflow


def test_publisher_validates_source_run_identity() -> None:
    workflow = _workflow_text()

    assert 'run_id must be a positive integer' in workflow
    assert 'Data refresh validation' in workflow
    assert "'.conclusion'" in workflow
    assert '"success"' in workflow
    assert "'.event'" in workflow
    assert '"workflow_dispatch"' in workflow
    assert "'.head_branch'" in workflow
    assert '"main"' in workflow
    assert "'.head_sha'" in workflow
    assert '"$GITHUB_SHA"' in workflow


def test_publisher_revalidates_artifact_and_snapshot() -> None:
    workflow = _workflow_text()

    assert "snapshot-report.json" in workflow
    assert "artifact snapshot IDs do not match" in workflow
    assert "artifact JSON and SQLite totals do not match" in workflow
    assert "python batch/verify_data.py" in workflow


def test_publisher_limits_repository_changes_to_snapshot_files() -> None:
    workflow = _workflow_text()

    assert "Unexpected changed files" in workflow
    assert "data/toilets.json.gz" in workflow
    assert "data/toilets.db" in workflow
    assert "data/snapshot.json" in workflow
    assert "peter-evans/create-pull-request@v8" in workflow
    assert "git push" not in workflow
