import chromadb
from src.rag.chunker import CodeChunk

class ChromaVectorStore:
    def __init__(self, persist_dir: str = "./chroma_data"):
        # 1. Persistent Client saves to disk
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # 2. get_or_create ensures no crash on server restart
        self.collection = self.client.get_or_create_collection(
            name="codebase_chunks",
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: list[CodeChunk], embeddings: list[list[float]]):
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        
        # Sanitize metadata: convert None -> ""
        clean_metadatas = [
            {k: ("" if v is None else v) for k, v in c.metadata.items()}
            for c in chunks
        ]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=clean_metadatas,
            embeddings=embeddings
        )

    def search(self, query_embedding: list[float], repository_id: str, top_k: int = 5) -> list[dict]:
        results = self.collection.query(
                    query_embeddings= [query_embedding],
                    n_results= top_k,
                    where= {"repository_id": repository_id}
                )
        
        formatted_results = []
    
        # Check if we got any matches
        if not results or not results["ids"] or not results["ids"][0]:
            return formatted_results
        
        # Unpack the parallel lists
        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        for i in range(len(ids)):
            dist = distances[i]
            similarity = round(1.0 - dist, 4)
            formatted_results.append({
                "chunk_id": ids[i],
                "content": documents[i],
                "metadata": metadatas[i],
                "similarity_score": similarity
            })

        return formatted_results

    def delete_repository(self, repository_id: str):
        self.collection.delete(where={"repository_id": repository_id})
