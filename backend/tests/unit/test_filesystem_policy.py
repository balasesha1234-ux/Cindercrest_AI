"""Unit tests verifying policy enforcement on filesystem tools."""

from pathlib import Path

from backend.app.agent.policy import AgentPolicyEngine
from backend.app.agent.schema import PolicyDecision
from backend.app.agent.tools.filesystem import FilesystemGuard


def test_policy_denies_filesystem_tools_in_privacy_mode() -> None:
    policy = AgentPolicyEngine()
    res1 = policy.evaluate_action("fs.search", {"query": "test"}, privacy_mode=True)
    assert res1.decision == PolicyDecision.DENY
    assert "privacy mode" in res1.reason.lower()

    res2 = policy.evaluate_action("fs.read_text", {"path": "docs/STATUS.md"}, privacy_mode=True)
    assert res2.decision == PolicyDecision.DENY


def test_policy_denies_read_outside_approved_directory(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved"
    approved_dir.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    policy = AgentPolicyEngine(fs_guard=guard)

    res = policy.evaluate_action("fs.read_text", {"path": str(outside_file)})
    assert res.decision == PolicyDecision.DENY
    assert "outside approved" in res.reason.lower()


def test_policy_allows_read_inside_approved_directory(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved"
    approved_dir.mkdir()
    valid_file = approved_dir / "valid.md"
    valid_file.write_text("# Valid Document", encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    policy = AgentPolicyEngine(fs_guard=guard)

    res = policy.evaluate_action("fs.read_text", {"path": str(valid_file)})
    assert res.decision == PolicyDecision.ALLOW
