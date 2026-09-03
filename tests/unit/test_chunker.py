import tempfile
import pathlib
from src.database.models import File, Symbol
from src.rag.chunker import CodeChunker

SAMPLE_SOURCE = """
import os
import sys

CONFIG_TIMEOUT = 30

class PaymentProcessor:
    \"\"\"Handles payments.\"\"\"
    currency = "USD"

    def process(self, amount: float):
        return True

def standalone_helper():
    return 42
"""

def test_code_chunker_semantic_slicing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_name = "test_module.py"
        file_path = pathlib.Path(tmp_dir) / file_name
        file_path.write_text(SAMPLE_SOURCE, encoding="utf-8")

        # Mock File record
        file_record = File(
            id="f-123",
            repository_id="repo-456",
            path=file_name,
            file_size=len(SAMPLE_SOURCE),
            line_count=len(SAMPLE_SOURCE.splitlines())
        )

        # Mock Symbols for that file
        cls_sym = Symbol(
            id="s-cls",
            file_id="f-123",
            name="PaymentProcessor",
            symbol_type="class",
            parent_class=None,
            start_line=7,
            end_line=13
        )
        method_sym = Symbol(
            id="s-method",
            file_id="f-123",
            name="process",
            symbol_type="method",
            parent_class="PaymentProcessor",
            start_line=11,
            end_line=13
        )
        func_sym = Symbol(
            id="s-func",
            file_id="f-123",
            name="standalone_helper",
            symbol_type="function",
            parent_class=None,
            start_line=14,
            end_line=16
        )
        file_record.symbols = [cls_sym, method_sym, func_sym]

        # Run Chunker
        chunks = CodeChunker.chunk_file(file_record, tmp_dir)

        # Assertions
        assert len(chunks) >= 3

        # 1. Overview chunk should contain imports
        overview = next(c for c in chunks if c.metadata["symbol_type"] == "file_overview")
        assert "CONFIG_TIMEOUT = 30" in overview.content
        assert overview.metadata["file_path"] == file_name

        # 2. Class summary should stop before method
        cls_chunk = next(c for c in chunks if c.metadata["symbol_type"] == "class")
        assert "PaymentProcessor" in cls_chunk.content
        assert "def process" not in cls_chunk.content  # Method is chunked separately!

        # 3. Method chunk should have parent_class in header & metadata
        method_chunk = next(c for c in chunks if c.metadata["symbol_name"] == "process")
        assert "Parent Class: PaymentProcessor" in method_chunk.content
        assert method_chunk.metadata["parent_class"] == "PaymentProcessor"