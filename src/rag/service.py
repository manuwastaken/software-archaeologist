import os
from google import genai
from src.rag.embeddings import GeminiEmbeddingService
from src.rag.vector_store import ChromaVectorStore

# Using Gemini 3.6 Flash for near-instant, high-reasoning code answers
LLM_MODEL = "gemini-3.6-flash"


class RAGService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.embedding_service = GeminiEmbeddingService(api_key=self.api_key)
        self.vector_store = ChromaVectorStore()

    def answer_question(self, repository_id: str, question: str, top_k: int = 5) -> dict:
        # 1. Embed query
        query_vector = self.embedding_service.embed_query(question)

        # 2. Retrieve Top-K matching chunks for this repository
        matches = self.vector_store.search(
            query_embedding=query_vector,
            repository_id=repository_id,
            top_k=top_k
        )

        # 3. Guard against empty results
        if not matches:
            return {
                "answer": "No relevant code chunks were found for this repository. Please make sure the repository has finished ingestion.",
                "citations": []
            }

        # 4. Assemble context snippets for the prompt
        context_blocks = []
        citations = []

        for i, match in enumerate(matches, start=1):
            content = match["content"]
            meta = match["metadata"]
            score = match["similarity_score"]

            context_blocks.append(f"--- Snippet {i} ---\n{content}")

            citations.append({
                "file_path": meta.get("file_path", ""),
                "symbol_name": meta.get("symbol_name") or None,
                "start_line": meta.get("start_line", 0),
                "end_line": meta.get("end_line", 0),
                "similarity_score": score
            })

        context_str = "\n\n".join(context_blocks)

        # 5. Construct Grounded Prompt
        prompt = f"""You are Archaeon, an expert AI software archaeologist and code intelligence system.
Your job is to answer questions about a codebase strictly and accurately using the provided code snippets below.

Rules:
1. Ground your answer ONLY in the provided code snippets.
2. For any claim, feature, or function you explain, explicitly cite the file path and line numbers (e.g. `[src/auth.py:12-25]`).
3. If the provided snippets do not contain enough information to answer the question with certainty, state clearly that the code snippets provided do not contain the answer. Do NOT hallucinate or assume facts not present in the snippets.
4. Format your answer using clean, concise GitHub Markdown.

--- CODE SNIPPETS ---
{context_str}

--- USER QUESTION ---
{question}
"""

        # 6. Call Gemini Flash
        response = self.client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt
        )

        return {
            "answer": response.text,
            "citations": citations
        }