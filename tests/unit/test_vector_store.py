import tempfile
from src.rag.chunker import CodeChunk
from src.rag.vector_store import ChromaVectorStore

def test_chroma_vector_store_filtering():
    # ignore_cleanup_errors=True tells Python on Windows not to crash if ChromaDB holds a file handle
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_chroma_dir:
        store = ChromaVectorStore(persist_dir=tmp_chroma_dir)

        # 2 dummy 4-dimensional vectors
        dummy_v1 = [1.0, 0.0, 0.0, 0.0]
        dummy_v2 = [0.0, 1.0, 0.0, 0.0]

        chunks = [
            CodeChunk(
                chunk_id="chunk-repo-A",
                content="Code for Repo A",
                metadata={"repository_id": "repo-A", "file_path": "a.py", "symbol_name": "foo"}
            ),
            CodeChunk(
                chunk_id="chunk-repo-B",
                content="Code for Repo B",
                metadata={"repository_id": "repo-B", "file_path": "b.py", "symbol_name": None}
            ),
        ]

        store.add_chunks(chunks, [dummy_v1, dummy_v2])

        # Query targeting only Repo A
        results_a = store.search(query_embedding=dummy_v1, repository_id="repo-A", top_k=5)
        assert len(results_a) == 1
        assert results_a[0]["chunk_id"] == "chunk-repo-A"
        assert results_a[0]["metadata"]["repository_id"] == "repo-A"

        # Query targeting Repo B
        results_b = store.search(query_embedding=dummy_v2, repository_id="repo-B", top_k=5)
        assert len(results_b) == 1
        assert results_b[0]["chunk_id"] == "chunk-repo-B"
        assert results_b[0]["metadata"]["symbol_name"] == ""