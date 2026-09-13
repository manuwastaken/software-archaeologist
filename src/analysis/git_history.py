from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
import git
import os


@dataclass
class CommitSummary:
    hexsha : str
    author : str
    authored_date : str
    message: str

@dataclass
class BlameSegment:
    start_line : int
    end_line: int
    commit_hash : str
    author : str
    date : str
    summary : str

@dataclass
class CommitDetail:
    hexsha:str
    author:str
    date:str
    message:str
    files_changed: list[str]
    diff_text: str

class GitHistoryAnalyzer:
    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
           raise FileNotFoundError(f"Repository directory not found: {self.repo_path}")
        try:
           self.repo = git.Repo(self.repo_path)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError) as e:
            raise ValueError(f"Path '{self.repo_path}' is not a valid Git repository") from e 

    def get_commits(self, file_path: str | None = None, limit: int = 5) -> list[CommitSummary]:
        """Fetch the most recent commits for a specific file or the entire repository."""
        commit_summary_list = []
        clean_path = Path(file_path).as_posix() if file_path else None
        try:
            commits = self.repo.iter_commits(paths=clean_path, max_count=limit)
            for c in commits:
                cs = CommitSummary(
                    hexsha=c.hexsha[:7],
                    author=c.author.name if c.author else "unknown",
                    authored_date=datetime.fromtimestamp(c.authored_date).isoformat(),
                    message=c.summary
                )
                commit_summary_list.append(cs)
        except Exception:
            return []
        
        return commit_summary_list
    
    def get_blame(self, file_path: str, start_line: int, end_line: int) -> list[BlameSegment]:
        """Inspect who modified lines start_line to end_line and in what commits."""
        blame_segment_list = []
        current_line = 1
        clean_path = Path(file_path).as_posix()
        try:
            blame_data = self.repo.blame("HEAD", clean_path)
            if not blame_data:
                return []
            
            for (c,l) in blame_data:
                block_start = current_line
                block_end = current_line + len(l) - 1

                if (block_start <= end_line and block_end >= start_line): 
                    seg_start = max(block_start, start_line)
                    seg_end = min(block_end, end_line) 
                    bd = BlameSegment(
                        start_line= seg_start,
                        end_line= seg_end,
                        commit_hash= c.hexsha[:7],
                        author= c.author.name if c.author else "unknown",
                        date= datetime.fromtimestamp(c.authored_date).isoformat(),
                        summary= c.summary
                    )
                    blame_segment_list.append(bd)
                current_line = block_end + 1
        except Exception:
            return []
        return blame_segment_list

    def get_diff(self, commit_hash: str, max_lines: int = 60) -> CommitDetail:
        """Fetch the unified diff patch and modified files for a specific commit."""
        try:
            commit = self.repo.commit(commit_hash)
        except Exception as e:
            raise ValueError(f"Commit '{commit_hash}' not found in repository.") from e

        if commit.parents:
            diff_index = commit.parents[0].diff(commit, create_patch=True)
        else:
            diff_index = commit.diff(git.NULL_TREE, create_patch=True)

        files_changed = [
            d.b_path or d.a_path 
            for d in diff_index 
            if (d.b_path or d.a_path)
        ]

        diff_lines = []
        for d in diff_index:
            if d.diff:
                patch = d.diff.decode("utf-8", errors="replace")
                diff_lines.extend(patch.splitlines())

        if len(diff_lines) > max_lines:
            truncated_body = "\n".join(diff_lines[:max_lines])
            diff_text = f"{truncated_body}\n... [Diff truncated: {len(diff_lines) - max_lines} more lines modified]"
        else:
            diff_text = "\n".join(diff_lines) if diff_lines else "No code changes (empty commit or binary files)."

        return CommitDetail(
            hexsha=commit.hexsha[:7],
            author=commit.author.name if commit.author else "Unknown",
            date=datetime.fromtimestamp(commit.authored_date).isoformat(),
            message=commit.message.strip(),
            files_changed=files_changed,
            diff_text=diff_text
        )