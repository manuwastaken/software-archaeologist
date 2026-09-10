from unittest.mock import MagicMock
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Repository, File, Symbol
from src.agents.tools import build_archaeon_tools


def test_codebase_search_tool():
    """Verify semantic vector search tool formats matches and handles empty results."""
    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1, 0.2, 0.3]

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "chunk_1",
            "content": "class SymbolVisitor:\n    pass",
            "similarity_score": 0.89,
            "metadata": {
                "file_path": "src/analysis/ast_parser.py",
                "symbol_name": "SymbolVisitor",
                "symbol_type": "class",
                "start_line": 15,
                "end_line": 40,
            },
        }
    ]

    tools = build_archaeon_tools(
        repository_id="repo-123",
        db=MagicMock(),
        vector_store=mock_vector_store,
        embedding_service=mock_embedding,
        clone_path="dummy/path",
    )
    codebase_search = tools[0]
    assert codebase_search.name == "codebase_search"

    # 1. Success case
    output = codebase_search.invoke({"query": "where is SymbolVisitor defined", "top_k": 2})
    assert "src/analysis/ast_parser.py" in output
    assert "SymbolVisitor (class)" in output
    assert "Lines: 15 - 40" in output
    assert "class SymbolVisitor" in output
    assert "Score: 0.89" in output
    mock_embedding.embed_query.assert_called_once_with("where is SymbolVisitor defined")
    mock_vector_store.search.assert_called_once_with([0.1, 0.2, 0.3], "repo-123", 2)

    # 2. Empty results case
    mock_vector_store.search.return_value = []
    output_empty = codebase_search.invoke({"query": "non_existent_concept"})
    assert "No relevant code found for query: 'non_existent_concept'" in output_empty

    # 3. Defensive error handling case
    mock_embedding.embed_query.side_effect = RuntimeError("Embedding API timeout")
    output_error = codebase_search.invoke({"query": "will fail"})
    assert "Error searching codebase: Embedding API timeout" in output_error


def test_symbol_lookup_tool():
    """Verify symbol lookup queries database models and handles missing symbols."""
    # Set up in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    repo = Repository(id="repo-abc", url="https://github.com/example/repo", status="completed")
    session.add(repo)
    session.commit()

    file_rec = File(
        id="file-1",
        repository_id=repo.id,
        path="src/utils/helpers.py",
        file_size=500,
        line_count=60,
    )
    session.add(file_rec)
    session.commit()

    sym_class = Symbol(
        id="sym-1",
        file_id=file_rec.id,
        name="DataProcessor",
        symbol_type="class",
        parent_class="BaseProcessor",
        start_line=10,
        end_line=50,
        docstring="Processes ingested data batches.",
    )
    sym_func = Symbol(
        id="sym-2",
        file_id=file_rec.id,
        name="clean_text",
        symbol_type="function",
        parent_class=None,
        start_line=52,
        end_line=60,
        docstring="Sanitizes string inputs.",
    )
    session.add_all([sym_class, sym_func])
    session.commit()

    tools = build_archaeon_tools(
        repository_id=repo.id,
        db=session,
        vector_store=MagicMock(),
        embedding_service=MagicMock(),
        clone_path="dummy/path",
    )
    symbol_lookup = tools[1]
    assert symbol_lookup.name == "symbol_lookup"

    # 1. Exact class lookup
    res_class = symbol_lookup.invoke({"name": "DataProcessor"})
    assert "Symbol: DataProcessor (class)" in res_class
    assert "File: src/utils/helpers.py" in res_class
    assert "Lines: 10-50" in res_class
    assert "Parent Class: BaseProcessor" in res_class
    assert "Processes ingested data batches." in res_class

    # 2. Lookup with symbol_type filter
    res_func = symbol_lookup.invoke({"name": "clean_text", "symbol_type": "function"})
    assert "Symbol: clean_text (function)" in res_func
    assert "Lines: 52-60" in res_func

    # 3. Filter mismatch returns not found
    res_mismatch = symbol_lookup.invoke({"name": "clean_text", "symbol_type": "class"})
    assert "Symbol 'clean_text' not found" in res_mismatch

    # 4. Non-existent symbol
    res_missing = symbol_lookup.invoke({"name": "NonExistentClass"})
    assert "Symbol 'NonExistentClass' not found" in res_missing

    session.close()


def test_file_read_tool(tmp_path: Path):
    """Verify file reading line slicing, security checks, and line bounding."""
    repo_dir = tmp_path / "cloned_repo"
    repo_dir.mkdir()

    # Create a dummy source file with 30 numbered lines
    src_file = repo_dir / "service.py"
    lines = [f"line {i} of code\n" for i in range(1, 31)]
    src_file.write_text("".join(lines), encoding="utf-8")

    tools = build_archaeon_tools(
        repository_id="repo-xyz",
        db=MagicMock(),
        vector_store=MagicMock(),
        embedding_service=MagicMock(),
        clone_path=str(repo_dir),
    )
    file_read = tools[2]
    assert file_read.name == "file_read"

    # 1. Valid range reading
    res = file_read.invoke({"file_path": "service.py", "start_line": 5, "end_line": 8})
    assert "Lines 5-8 of 30" in res
    assert "5: line 5 of code" in res
    assert "8: line 8 of code" in res
    assert "9: line 9 of code" not in res

    # 2. Clamped end_line exceeding total lines
    res_clamped = file_read.invoke({"file_path": "service.py", "start_line": 28, "end_line": 50})
    assert "Lines 28-30 of 30" in res_clamped
    assert "30: line 30 of code" in res_clamped

    # 3. Path traversal security check
    res_traversal = file_read.invoke({"file_path": "../../secret.txt", "start_line": 1, "end_line": 5})
    assert "Path traversal detected" in res_traversal

    # 4. Missing file
    res_missing = file_read.invoke({"file_path": "missing_file.py", "start_line": 1, "end_line": 5})
    assert "File 'missing_file.py' does not exist" in res_missing

    # 5. Invalid line numbers (start > end or start < 1)
    res_invalid = file_read.invoke({"file_path": "service.py", "start_line": 10, "end_line": 5})
    assert "Invalid line range" in res_invalid

    res_zero = file_read.invoke({"file_path": "service.py", "start_line": 0, "end_line": 5})
    assert "Invalid line range" in res_zero

    # 6. Max line limit exceeded (requesting > 100 lines)
    res_too_many = file_read.invoke({"file_path": "service.py", "start_line": 1, "end_line": 105})
    assert "Maximum allowed is 100 lines per read" in res_too_many
