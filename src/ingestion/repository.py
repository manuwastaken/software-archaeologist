from sqlalchemy.orm import Session
from src.database.engine import SessionLocal
from src.database.models import File, Repository, Job, Symbol
from src.ingestion.git import git_clone, git_extract_metadata, locate_py
from src.analysis.ast_parser import parse_python_file
import pathlib

def ingest_repository(repo_id: str, job_id: str, repo_url: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            print(f"Job with ID {job_id} not found.")
            return
        job.status = "processing"
        job.progress = 10

        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            print(f"Repository with ID {repo_id} not found.")
            return
        repo.status = "processing"
        db.commit()

        destination_path = f"data/repos/{repo_id}"
        git_clone(repo_url, destination_path)
        job.progress = 50
        db.commit()

        py_files = locate_py(destination_path)
        total_files = len(py_files)

        for i, py_file in enumerate(py_files, start=1):
            relative_path = pathlib.Path(py_file).relative_to(destination_path)
            
            # Read line count safely
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                line_count = sum(1 for _ in f)
                
            file_size = pathlib.Path(py_file).stat().st_size

            # 1. Create File Record
            file = File(
                repository_id=repo_id,
                path=str(relative_path),
                file_size=file_size,
                line_count=line_count
            )
            db.add(file)
            db.commit()
            db.refresh(file)

            # 2. Parse AST
            parsed_data = parse_python_file(py_file)
            symbols_to_create = []

            # 3. Process Classes
            for cls in parsed_data["classes"]:
                symbol = Symbol(
                    file_id=file.id,
                    name=cls["name"],
                    symbol_type="class",
                    parent_class=None,
                    docstring=cls["docstring"],
                    start_line=cls["start_line"],
                    end_line=cls["end_line"],
                    metadata_json={"base_classes": cls["base_classes"]}
                )
                symbols_to_create.append(symbol)

            # 4. Process Functions & Methods
            for func in parsed_data["functions"]:
                symbol = Symbol(
                    file_id=file.id,
                    name=func["name"],
                    symbol_type=func["type"],            # 'function' or 'method'
                    parent_class=func["parent_class"],   # Preserves parent class!
                    docstring=func["docstring"],
                    start_line=func["start_line"],
                    end_line=func["end_line"],
                    metadata_json={"args": func["args"]}
                )
                symbols_to_create.append(symbol)

            # 5. Process Imports
            for imp in parsed_data["imports"]:
                symbol = Symbol(
                    file_id=file.id,
                    name=imp["module"],
                    symbol_type="import",
                    parent_class=None,
                    docstring=None,
                    start_line=1,
                    end_line=1,
                    metadata_json={"imported_names": imp["imported_names"]}
                )
                symbols_to_create.append(symbol)

            # 6. Bulk Save Symbols
            if symbols_to_create:
                db.add_all(symbols_to_create)
                db.commit()

            # 7. Dynamic Progress Update
            if total_files > 0:
                progress = 50 + int((i / total_files) * 35)
                if progress > job.progress:
                    job.progress = progress
                    db.commit()
                
        name, filecount, default_branch, clone_path = git_extract_metadata(destination_path, repo)
        job.progress = 90
        db.commit()

        repo.name = name
        repo.file_count = filecount
        repo.default_branch = default_branch
        repo.clone_path = clone_path
        repo.status = "completed"

        job.status = "completed"
        job.progress = 100
        db.commit()

    except Exception as e:
        print(f"Error during ingestion: {e}")
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            job.progress = 0
        if repo:
            repo.status = "failed"
        db.commit()
    finally:
        db.close()
