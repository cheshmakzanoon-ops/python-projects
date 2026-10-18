import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "ci_status.py"
spec = importlib.util.spec_from_file_location("ci_status", MODULE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_queued_run_remains_queued_and_unrelated_metadata_is_not_emitted():
    value = {
        "payload": {
            "allWorkflowRunsRoute": {
                "workflowRuns": [
                    {
                        "id": "123",
                        "description": {"linkUrl": "/owner/repo/commit/abcdef"},
                        "state": {"status": "WORKFLOW_RUN_STATUS_QUEUED"},
                        "runUrl": "https://github.com/owner/repo/actions/runs/123",
                        "title": "Build",
                        "unneeded_internal_channel": "not-for-reports",
                    }
                ]
            }
        }
    }
    page = '<script type="application/json">' + json.dumps(value) + "</script>"
    runs = module.from_html(page)
    assert len(runs) == 1
    assert runs[0]["commit"] == "abcdef"
    assert runs[0]["state"]["status"] == "WORKFLOW_RUN_STATUS_QUEUED"
    assert "unneeded_internal_channel" not in json.dumps(runs)


def test_missing_or_malformed_page_does_not_claim_success():
    assert module.from_html('<script type="application/json">bad json</script>') == []
    assert module.from_html("<html>Not a workflow report</html>") == []
