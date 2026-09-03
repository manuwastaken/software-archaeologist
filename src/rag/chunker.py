import os
from dataclasses import dataclass
from typing import Any
from src.database.models import File, Symbol

@dataclass
class CodeChunk:
    chunk_id: str
    content: str
    metadata: dict[str, Any]

class CodeChunker:

    @staticmethod
    def read_file_lines(file_abs_path: str) -> list[str]:
        if not os.path.isfile(file_abs_path):
            return []
        try:
            with open(file_abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.readlines()
        except Exception as e:
            print(f"Error reading file {file_abs_path}: {e}")
            return []

    @staticmethod
    def build_header(file_path: str, symbol_name: str, symbol_type: str, start_line: int, end_line: int, parent_class: str | None = None) -> str:
        header = f"File: {file_path}\n"
        header += f"Symbol: {symbol_name} ({symbol_type})\n"
        if parent_class:
            header += f"Parent Class: {parent_class}\n"
        header += f"Lines: {start_line}-{end_line}"
        return header

    @staticmethod
    def create_file_overview_chunk(file: File, lines: list[str]) -> CodeChunk | None:
        overview_lines = []
        counter = 0

        for line in lines:
            stripped = line.strip()
            # Stop at first class/def or when counter reaches 50 lines
            if stripped.startswith("class ") or stripped.startswith("def ") or counter >= 50:
                break
            overview_lines.append(line)
            counter += 1

        overview_code = "".join(overview_lines).strip()
        if not overview_code:
            return None

        # Context Header + Code
        content = f"File: {file.path}\nType: file_overview\nLines: 1-{counter}\n\n{overview_code}"

        return CodeChunk(
            chunk_id=f"{file.id}_overview",
            content=content,
            metadata={
                "file_id": file.id,
                "repository_id": file.repository_id,
                "file_path": file.path,
                "symbol_name": None,
                "symbol_type": "file_overview",
                "parent_class": None,
                "start_line": 1,
                "end_line": counter,
            }
        )

    @staticmethod
    def create_symbol_chunks(file: File, lines: list[str]) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []

        for symbol in file.symbols:
            # 1. Skip imports (captured in file overview)
            if symbol.symbol_type == "import":
                continue

            # 2. Class Summary (stop before first method)
            elif symbol.symbol_type == "class":
                child_methods = [
                    s for s in file.symbols
                    if s.symbol_type == "method" and s.parent_class == symbol.name
                ]
                if child_methods:
                    first_method_start = min(m.start_line for m in child_methods)
                    chunk_end_line = first_method_start - 1
                else:
                    chunk_end_line = symbol.end_line

                start_idx = max(0, symbol.start_line - 1)
                end_idx = min(len(lines), chunk_end_line)
                snippet = "".join(lines[start_idx:end_idx]).strip()

                if not snippet:
                    continue

                header = CodeChunker.build_header(
                    file_path=file.path,
                    symbol_name=symbol.name,
                    symbol_type="class",
                    start_line=symbol.start_line,
                    end_line=chunk_end_line
                )
                content = f"{header}\n\n{snippet}"

                chunks.append(
                    CodeChunk(
                        chunk_id=f"{file.id}_{symbol.id}",
                        content=content,
                        metadata={
                            "file_id": file.id,
                            "repository_id": file.repository_id,
                            "file_path": file.path,
                            "symbol_name": symbol.name,
                            "symbol_type": "class",
                            "parent_class": None,
                            "start_line": symbol.start_line,
                            "end_line": chunk_end_line,
                        }
                    )
                )

            # 3. Functions and Methods
            elif symbol.symbol_type in ("function", "method"):
                start_idx = max(0, symbol.start_line - 1)
                end_idx = min(len(lines), symbol.end_line)
                snippet = "".join(lines[start_idx:end_idx]).strip()

                if not snippet:
                    continue

                header = CodeChunker.build_header(
                    file_path=file.path,
                    symbol_name=symbol.name,
                    symbol_type=symbol.symbol_type,
                    start_line=symbol.start_line,
                    end_line=symbol.end_line,
                    parent_class=symbol.parent_class
                )
                content = f"{header}\n\n{snippet}"

                chunks.append(
                    CodeChunk(
                        chunk_id=f"{file.id}_{symbol.id}",
                        content=content,
                        metadata={
                            "file_id": file.id,
                            "repository_id": file.repository_id,
                            "file_path": file.path,
                            "symbol_name": symbol.name,
                            "symbol_type": symbol.symbol_type,
                            "parent_class": symbol.parent_class,
                            "start_line": symbol.start_line,
                            "end_line": symbol.end_line,
                        }
                    )
                )

        return chunks

    @classmethod
    def chunk_file(cls, file_record: File, repo_clone_path: str) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        file_abs_path = os.path.join(repo_clone_path, file_record.path)
        lines = cls.read_file_lines(file_abs_path)

        if not lines:
            return chunks

        overview_chunk = cls.create_file_overview_chunk(file_record, lines)
        if overview_chunk:
            chunks.append(overview_chunk)

        symbol_chunks = cls.create_symbol_chunks(file_record, lines)
        chunks.extend(symbol_chunks)

        return chunks