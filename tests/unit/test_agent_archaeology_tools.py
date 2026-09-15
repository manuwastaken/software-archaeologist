from pathlib import Path
from unittest.mock import MagicMock
import pytest
import git

from src.agents.tools import build_archaeon_tools


@pytest.fixture
def temp_git_repo_for_tools(tmp_path: Path):
    """Creates a temporary Git repo with commits for testing agent tools."""
    repo_dir = tmp_path / "agent_test_repo"
    repo_dir.mkdir()
    repo = git.Repo.init(repo_dir)

    with repo.config_writer() as writer:
        writer.set_value("user", "name", "Archaeon Agent Tester")
        writer.set_value("user", "email", "agent_tester@example.com")

    # Commit 1
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    code_file = src_dir / "app.py"
    code_file.write_text("def run():\n    return 42\n", encoding="utf-8")
    repo.index.add(["src/app.py"])
    c1 = repo.index.commit("feat: initial app implementation")

    # Commit 2
    code_file.write_text("def run():\n    return 42\n\ndef stop():\n    return True\n", encoding="utf-8")
    repo.index.add(["src/app.py"])
    c2 = repo.index.commit("feat: add stop function")

    return repo_dir, c1, c2


def test_agent_git_tools_exist_and_invoke(temp_git_repo_for_tools):
    """Verify that build_archaeon_tools returns all 6 tools including the 3 new git archaeology tools."""
    repo_dir, c1, c2 = temp_git_repo_for_tools

    tools = build_archaeon_tools(
        repository_id="repo-test",
        db=MagicMock(),
        vector_store=MagicMock(),
        embedding_service=MagicMock(),
        clone_path=str(repo_dir),
    )

    # Must now have 6 tools: codebase_search, symbol_lookup, file_read, git_commit_log, git_line_blame, git_commit_diff
    assert len(tools) == 6
    tool_names = [t.name for t in tools]
    assert "git_commit_log" in tool_names
    assert "git_line_blame" in tool_names
    assert "git_commit_diff" in tool_names

    # 1. Test git_commit_log
    commit_log_tool = next(t for t in tools if t.name == "git_commit_log")
    log_output = commit_log_tool.invoke({"file_path": "src/app.py", "limit": 5})
    assert "add stop function" in log_output
    assert "initial app implementation" in log_output
    assert c2.hexsha[:7] in log_output

    # 2. Test git_line_blame
    blame_tool = next(t for t in tools if t.name == "git_line_blame")
    blame_output = blame_tool.invoke({"file_path": "src/app.py", "start_line": 1, "end_line": 4})
    assert "Lines" in blame_output
    assert "Archaeon Agent Tester" in blame_output

    # 3. Test git_commit_diff
    diff_tool = next(t for t in tools if t.name == "git_commit_diff")
    diff_output = diff_tool.invoke({"commit_hash": c2.hexsha[:7], "max_lines": 50})
    assert "stop" in diff_output
    assert "src/app.py" in diff_output
