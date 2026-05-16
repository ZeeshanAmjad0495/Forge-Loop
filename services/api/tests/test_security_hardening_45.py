"""#45 batch 6: H4/L3 workspace confinement + M2 project-scoped approvals."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.repositories import InMemoryApprovalRepository
from app.models import Approval
from app.services.workspace_paths import (
    WorkspacePathError,
    assert_workspace_safe,
    is_dangerous_path,
)


# --- H4 / L3 -------------------------------------------------------------

@pytest.mark.parametrize("p", ["/etc", "/etc/cron.d", "/usr/bin", "/", "/root"])
def test_h4_system_trees_blocked(p):
    assert is_dangerous_path(Path(p)) is not None
    with pytest.raises(WorkspacePathError):
        assert_workspace_safe(p)


def test_h4_home_credential_dirs_blocked():
    ssh = str(Path.home() / ".ssh")
    aws = str(Path.home() / ".aws" / "credentials")
    assert is_dangerous_path(Path(ssh)) is not None
    assert is_dangerous_path(Path(aws).parent) is not None
    with pytest.raises(WorkspacePathError):
        assert_workspace_safe(ssh)


def test_h4_normal_dev_paths_allowed(tmp_path):
    # tmp workspaces and ~/Documents-style dev repos must keep working.
    ws = tmp_path / "proj"
    ws.mkdir()
    assert is_dangerous_path(ws.resolve()) is None
    assert assert_workspace_safe(str(ws)) == ws.resolve()
    dev = Path.home() / "Documents" / "somerepo"
    assert is_dangerous_path(dev) is None


# --- M2 ------------------------------------------------------------------

def _appr(pid: str, tid: str) -> Approval:
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    return Approval(
        id=f"a-{pid}-{tid}", project_id=pid, target_type="dev_task",
        target_id=tid, status="approved", requested_by="t@t",
        created_at=now, updated_at=now,
    )


def test_m2_approval_lookup_is_project_scoped():
    repo = InMemoryApprovalRepository()
    repo.save(_appr("projA", "dt1"))
    # legacy (no project_id) still finds it
    assert repo.find_approved_for_target("dev_task", "dt1") is not None
    # correct project finds it
    assert repo.find_approved_for_target("dev_task", "dt1", "projA") is not None
    # different project must NOT satisfy the gate (cross-project bypass)
    assert repo.find_approved_for_target("dev_task", "dt1", "projB") is None
