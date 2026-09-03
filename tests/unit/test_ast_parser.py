import tempfile
import pathlib
from src.analysis.ast_parser import parse_python_file

SAMPLE_CODE = """
import os
from datetime import datetime

class SampleService:
    \"\"\"Sample service class docstring.\"\"\"
    def __init__(self, name: str):
        self.name = name

    def process_data(self):
        \"\"\"Process method docstring.\"\"\"
        return True

def standalone_function(x: int) -> int:
    \"\"\"Standalone function docstring.\"\"\"
    return x * 2
"""

def test_ast_parser_extraction():
    """Test extracting classes, functions, methods, and imports from code."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CODE)
        temp_path = f.name

    try:
        parsed = parse_python_file(temp_path)

        # 1. Check Classes
        classes = parsed["classes"]
        assert len(classes) == 1
        assert classes[0]["name"] == "SampleService"
        assert "Sample service class docstring" in classes[0]["docstring"]

        # 2. Check Functions & Methods
        functions = parsed["functions"]
        assert len(functions) == 3  # __init__, process_data, standalone_function

        methods = [f for f in functions if f["type"] == "method"]
        standalone = [f for f in functions if f["type"] == "function"]

        assert len(methods) == 2
        assert any(m["name"] == "__init__" for m in methods)
        assert any(m["name"] == "process_data" for m in methods)
        assert methods[0]["parent_class"] == "SampleService"

        assert len(standalone) == 1
        assert standalone[0]["name"] == "standalone_function"
        assert standalone[0]["parent_class"] is None

        # 3. Check Imports
        imports = parsed["imports"]
        assert len(imports) == 2
        assert any(imp["module"] == "os" for imp in imports)
        assert any(imp["module"] == "datetime" for imp in imports)

    finally:
        pathlib.Path(temp_path).unlink(missing_ok=True)
