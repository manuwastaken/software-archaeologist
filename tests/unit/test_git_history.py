from pathlib import Path
import pytest
import git

from src.analysis.git_history import GitHistoryAnalyzer, CommitSummary, BlameSegment, CommitDetail


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Creates a temporary local Git repository with two commits for testing."""
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()

    repo = git.Repo.init(repo_dir)

    # Configure author metadata for the test repository
    with repo.config_writer() as writer:
        writer.set_value("user", "name", "Archaeon Tester")
        writer.set_value("user", "email", "tester@example.com")

    # 1. First commit: create src/auth.py with 5 lines
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    auth_file = src_dir / "auth.py"
    initial_content = (
        "def authenticate(user, password):\n"
        "    if not user:\n"
        "        return False\n"
        "    return True\n"
        "# end of auth v1\n"
    )
    auth_file.write_text(initial_content, encoding="utf-8")
    repo.index.add(["src/auth.py"])
    commit1 = repo.index.commit("feat: initial authentication implementation")

    # 2. Second commit: add token verification lines
    updated_content = (
        initial_content +
        "def verify_token(token):\n"
        "    if token == 'valid':\n"
        "        return True\n"
        "    return False\n"
        "# end of auth v2\n"
    )
    auth_file.write_text(updated_content, encoding="utf-8")
    repo.index.add(["src/auth.py"])
    commit2 = repo.index.commit("feat: add verify_token method")

    return repo_dir, commit1, commit2


def test_git_history_analyzer_init(temp_git_repo, tmp_path):
    """Verify repository path validation in analyzer constructor."""
    repo_dir, _, _ = temp_git_repo

    # Valid repository
    analyzer = GitHistoryAnalyzer(repo_dir)
    assert analyzer.repo is not None

    # Non-existent directory
    with pytest.raises(FileNotFoundError):
        GitHistoryAnalyzer(tmp_path / "does_not_exist")

    # Existing directory that is NOT a git repo
    non_git_dir = tmp_path / "not_git"
    non_git_dir.mkdir()
    with pytest.raises(ValueError, match="not a valid Git repository"):
        GitHistoryAnalyzer(non_git_dir)


def test_get_commits(temp_git_repo):
    """Verify commit logs retrieval for whole repo and specific files."""
    repo_dir, commit1, commit2 = temp_git_repo
    analyzer = GitHistoryAnalyzer(repo_dir)

    # 1. Get all commits
    commits = analyzer.get_commits(limit=5)
    assert len(commits) == 2
    assert commits[0].hexsha == commit2.hexsha[:7]
    assert commits[0].message == "feat: add verify_token method"
    assert commits[0].author == "Archaeon Tester"

    assert commits[1].hexsha == commit1.hexsha[:7]
    assert commits[1].message == "feat: initial authentication implementation"

    # 2. Filter by file_path
    file_commits = analyzer.get_commits(file_path="src/auth.py", limit=5)
    assert len(file_commits) == 2

    # 3. Non-existent file in git history returns empty list
    missing_commits = analyzer.get_commits(file_path="non_existent.py")
    assert missing_commits == []


def test_get_blame(temp_git_repo):
    """Verify line-range blame grouping contiguous segments by commit."""
    repo_dir, commit1, commit2 = temp_git_repo
    analyzer = GitHistoryAnalyzer(repo_dir)

    # Lines 1-5 belong to commit1
    blame_first_half = analyzer.get_blame("src/auth.py", start_line=1, end_line=5)
    assert len(blame_first_half) == 1
    assert blame_first_half[0].commit_hash == commit1.hexsha[:7]
    assert blame_first_half[0].start_line == 1
    assert blame_first_half[0].end_line == 5
    assert blame_first_half[0].author == "Archaeon Tester"

    # Lines 6-10 belong to commit2
    blame_second_half = analyzer.get_blame("src/auth.py", start_line=6, end_line=10)
    assert len(blame_second_half) == 1
    assert blame_second_half[0].commit_hash == commit2.hexsha[:7]
    assert blame_second_half[0].start_line == 6
    assert blame_second_half[0].end_line == 10

    # Range covering both commits (lines 3 to 8)
    blame_overlap = analyzer.get_blame("src/auth.py", start_line=3, end_line=8)
    assert len(blame_overlap) == 2
    assert blame_overlap[0].commit_hash == commit1.hexsha[:7]
    assert blame_overlap[0].start_line == 3
    assert blame_overlap[0].end_line == 5

    assert blame_overlap[1].commit_hash == commit2.hexsha[:7]
    assert blame_overlap[1].start_line == 6
    assert blame_overlap[1].end_line == 8

    # Non-existent file returns empty
    assert analyzer.get_blame("missing.py", 1, 10) == []


def test_get_diff(temp_git_repo):
    """Verify diff inspection for both root and secondary commits."""
    repo_dir, commit1, commit2 = temp_git_repo
    analyzer = GitHistoryAnalyzer(repo_dir)

    # 1. Diff of commit2 (modifying commit)
    detail2 = analyzer.get_diff(commit2.hexsha)
    assert detail2.hexsha == commit2.hexsha[:7]
    assert detail2.author == "Archaeon Tester"
    assert "src/auth.py" in detail2.files_changed
    assert "verify_token" in detail2.diff_text

    # 2. Diff of commit1 (root commit without parents)
    detail1 = analyzer.get_diff(commit1.hexsha)
    assert detail1.hexsha == commit1.hexsha[:7]
    assert "src/auth.py" in detail1.files_changed
    assert "authenticate" in detail1.diff_text

    # 3. Non-existent commit hash raises ValueError
    with pytest.raises(ValueError, match="not found in repository"):
        analyzer.get_diff("000000000000")
