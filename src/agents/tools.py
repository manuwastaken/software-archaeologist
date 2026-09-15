from pathlib import Path
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analysis.git_history import GitHistoryAnalyzer
from src.database.models import File, Symbol
from src.rag.embeddings import GeminiEmbeddingService
from src.rag.vector_store import ChromaVectorStore


def build_archaeon_tools(
    repository_id: str,
    db: Session,
    vector_store: ChromaVectorStore,
    embedding_service: GeminiEmbeddingService,
    clone_path: str,
):
    @tool
    def codebase_search(query: str, top_k: int = 4) -> str:
        """Perform semantic vector search across the codebase to find relevant code snippets.
        Use this for conceptual questions, finding where features are implemented, or broad searches.
        """
        try:
            embedded_q = embedding_service.embed_query(query)
            vector = vector_store.search(embedded_q, repository_id, top_k)
            if not vector:
                return f"No relevant code found for query: '{query}'"
            
            codebase_list = []
            for index, v in enumerate(vector, 1):
                meta = v.get("metadata", {})
                file_path = meta.get("file_path", "Unknown")
                symbol = meta.get("symbol_name") or "N/A"
                symbol_type = meta.get("symbol_type", "Unknown")
                start = meta.get("start_line", "?") 
                end = meta.get("end_line", "?")
                score = v.get("similarity_score", 0.0)
                code = v.get("content", "").strip()
                codebase_chunk = (
                    f"--- Result {index} (Score: {score}) ---\n"
                    f"File: {file_path}\n"
                    f"Symbol: {symbol} ({symbol_type})\n"
                    f"Lines: {start} - {end}\n"
                    f"Content:\n{code}"
                )
                codebase_list.append(codebase_chunk)
            return "\n\n".join(codebase_list)
        except Exception as e:
            return f"Error searching codebase: {str(e)}"

    @tool
    def symbol_lookup(name: str, symbol_type: str | None = None) -> str:
        """Lookup exact definitions of classes, functions, or methods in the database.
        Returns file paths, line ranges, docstrings, and parent classes.
        """
        try:
            stmt = select(Symbol).join(File).where(
                File.repository_id == repository_id,
                Symbol.name == name
            )
            if symbol_type:
                stmt = stmt.where(Symbol.symbol_type == symbol_type)

            symbols = db.execute(stmt).scalars().all()

            if not symbols:
                return f"Symbol '{name}' not found in the codebase. Try codebase_search if you are unsure of the exact name."

            symbol_list = []
            for s in symbols:
                doc = s.docstring.strip() if s.docstring else "None"
                chunk = (
                    f"Symbol: {s.name} ({s.symbol_type})\n"
                    f"File: {s.file.path}\n"
                    f"Lines: {s.start_line}-{s.end_line}\n"
                    f"Parent Class: {s.parent_class or 'None'}\n"
                    f"Docstring: {doc}"
                )
                symbol_list.append(chunk)

            return "\n\n".join(symbol_list)

        except Exception as e:
            return f"Error looking up symbol '{name}': {str(e)}"

    @tool
    def file_read(file_path: str, start_line: int, end_line: int) -> str:
        """Read a specific range of lines from a file in the repository.
        start_line and end_line are 1-based and inclusive. Maximum range is 100 lines.
        """
        try:
            # 1. Resolve and validate path security
            repo_root = Path(clone_path).resolve()
            target_file = (repo_root / file_path).resolve()

            if not target_file.is_relative_to(repo_root):
                return "Error: Path traversal detected. Access denied."

            if not target_file.is_file():
                return f"Error: File '{file_path}' does not exist in the repository."

            # 2. Validate line numbers
            if start_line < 1 or end_line < start_line:
                return f"Error: Invalid line range {start_line}-{end_line}. start_line must be >= 1 and end_line >= start_line."

            max_lines = 100
            if (end_line - start_line + 1) > max_lines:
                return f"Error: Requested {end_line - start_line + 1} lines. Maximum allowed is {max_lines} lines per read."

            # 3. Read file safely
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()

            total_lines = len(all_lines)
            if start_line > total_lines:
                return f"Error: start_line {start_line} exceeds total file lines ({total_lines})."

            # 4. Slice lines (convert 1-based to 0-based index)
            actual_end = min(end_line, total_lines)
            selected_lines = all_lines[start_line - 1 : actual_end]

            # 5. Format with line numbers
            formatted_lines = []
            for i, line in enumerate(selected_lines, start=start_line):
                formatted_lines.append(f"{i}: {line.rstrip()}")

            header = f"--- {file_path} (Lines {start_line}-{actual_end} of {total_lines}) ---\n"
            return header + "\n".join(formatted_lines)

        except Exception as e:
            return f"Error reading file '{file_path}': {str(e)}"

    @tool
    def git_commit_log(file_path: str | None, limit : int = 5) -> str:
        """Allows the agent to answer questions like: "When was this file last changed and what features were committed recently?"""
        analyzer = GitHistoryAnalyzer(clone_path)
        try:
            commits = analyzer.get_commits(file_path=file_path, limit = limit)
            if commits == []:
                return "No git commits found for the specified path."
            commit_list = []
            for c in commits:
                hexsha = c.hexsha
                author_name = c.author
                date = c.authored_date
                message = c.message

                commit = (
                    f"Short hash: {hexsha}\n"
                    f"Author name: {author_name}\n"
                    f"Commit date: {date}\n"
                    f"Commit message: {message}"
                )
                commit_list.append(commit)
                
            return "\n\n".join(commit_list)
        
        except Exception as e:
            return f"Error: {e}"

    @tool
    def git_line_blame(file_path:str, start_line: int, end_line: int) -> str:
        """When an engineer asks: "Who wrote this function and why was this if-condition added?", the agent connects lines directly to historical commits."""
        analyzer = GitHistoryAnalyzer(clone_path)
        try:
            if start_line < 1 or end_line < start_line:
                return f"Error start line and end line doesnt make sense"

            blames = analyzer.get_blame(file_path=file_path, start_line=start_line, end_line= end_line)
            if blames == []:
                return "No blame information available for this line range."
            blame_list = []
            for b in blames:
                blame = (
                    f"Lines {b.start_line}-{b.end_line}\n"
                    f"Commit short hash: {b.commit_hash}\n"
                    f"Author name: {b.author}\n"
                    f"Commit Date: {b.date}\n"
                    f"Commit summary: {b.summary}"
                )
                blame_list.append(blame)

            return "\n\n".join(blame_list)

        except Exception as e:
            return f"Error:{e}"

    @tool
    def git_commit_diff(commit_hash: str, max_lines: int = 60) -> str:
        """Allows the agent to look inside a commit and explain the exact code additions (+) and deletions (-)."""
        analyzer = GitHistoryAnalyzer(clone_path)
        try:
            detail = analyzer.get_diff(commit_hash=commit_hash, max_lines=max_lines)
            files = "\n".join(
                f"- {file_path}"
                for file_path in detail.files_changed
            )

            return (
                f"Commit: {detail.hexsha}\n"
                f"Author: {detail.author}\n"
                f"Date: {detail.date}\n"
                f"Message:\n{detail.message}\n\n"
                f"Files changed:\n{files}\n\n"
                f"Diff:\n{detail.diff_text}"
            )

        except ValueError as e:
            return f"Error: {e}"

        except Exception as e:
            return f"Error: {e}"

    return [codebase_search, symbol_lookup, file_read, git_commit_log, git_line_blame, git_commit_diff]