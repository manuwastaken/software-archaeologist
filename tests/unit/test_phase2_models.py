from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, Repository, File, Symbol

def test_file_and_symbol_models():
    """Test File and Symbol database models and relationships."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Create Repository
    repo = Repository(url="https://github.com/example/phase2-repo", status="processing")
    session.add(repo)
    session.commit()
    session.refresh(repo)

    # 2. Create File linked to Repository
    file_record = File(
        repository_id=repo.id,
        path="src/main.py",
        file_size=1024,
        line_count=45
    )
    session.add(file_record)
    session.commit()
    session.refresh(file_record)

    assert file_record.id is not None
    assert file_record.repository_id == repo.id

    # 3. Create Symbols linked to File
    class_symbol = Symbol(
        file_id=file_record.id,
        name="MainApp",
        symbol_type="class",
        parent_class=None,
        start_line=1,
        end_line=20,
        docstring="Main app class",
        metadata_json={"base_classes": []}
    )
    func_symbol = Symbol(
        file_id=file_record.id,
        name="run",
        symbol_type="method",
        parent_class="MainApp",
        start_line=5,
        end_line=15,
        docstring="Run method",
        metadata_json={"args": ["self"]}
    )
    session.add_all([class_symbol, func_symbol])
    session.commit()

    # 4. Query relationships
    saved_file = session.query(File).filter(File.id == file_record.id).first()
    assert len(saved_file.symbols) == 2
    assert saved_file.repository.url == "https://github.com/example/phase2-repo"

    session.close()
