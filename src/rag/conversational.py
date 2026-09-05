import os
from typing import Sequence
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI

from src.rag.embeddings import GeminiEmbeddingService
from src.rag.vector_store import ChromaVectorStore

CHAT_MODEL = "gemini-3.6-flash"


class ChromaLangChainRetriever:
    """
    Adapter that connects our Phase 3 ChromaVectorStore and GeminiEmbeddingService
    to LangChain's expected Retriever interface.
    """
    def __init__(
        self, 
        vector_store: ChromaVectorStore, 
        embedding_service: GeminiEmbeddingService, 
        repository_id: str, 
        top_k: int = 4
    ):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.repository_id = repository_id
        self.top_k = top_k

    def invoke(self, query: str) -> list[Document]:
        # 1. Embed query
        query_vector = self.embedding_service.embed_query(query)

        # 2. Search ChromaDB using Phase 3 vector store
        matches = self.vector_store.search(
            query_embedding=query_vector,
            repository_id=self.repository_id,
            top_k=self.top_k
        )

        # 3. Convert matches to LangChain Document objects
        docs: list[Document] = []
        for item in matches:
            meta = dict(item["metadata"])
            meta["similarity_score"] = item["similarity_score"]
            meta["chunk_id"] = item["chunk_id"]

            docs.append(
                Document(
                    page_content=item["content"],
                    metadata=meta
                )
            )

        return docs


class ConversationalRAGService:
    """
    Modern LCEL Conversational RAG Engine (Zero Deprecated Chains).
    Features:
    - Pure LCEL pipe syntax (|)
    - Query Condensation for follow-up questions
    - Grounded Code Answering with line citations
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        self.llm = ChatGoogleGenerativeAI(
            model=CHAT_MODEL,
            google_api_key=self.api_key,
            temperature=0.2
        )
        self.embedding_service = GeminiEmbeddingService(api_key=self.api_key)
        self.vector_store = ChromaVectorStore()

        # Build reusable LCEL chains
        self.rephrase_chain = self._build_rephrase_chain()
        self.qa_chain = self._build_qa_chain()

    def _build_rephrase_chain(self):
        """
        LCEL Chain: Rephrases follow-up questions into standalone queries.
        """
        rephrase_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Given a chat history and the latest user question which might reference "
                "context in the chat history, formulate a standalone question which can be "
                "understood without the chat history. Do NOT answer the question, just "
                "reformulate it if needed and otherwise return it as is."
            )),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])
        return rephrase_prompt | self.llm | StrOutputParser()

    def _build_qa_chain(self):
        """
        LCEL Chain: Generates a grounded answer from code context and chat history.
        """
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are Archaeon, an expert AI software archaeologist.\n"
                "Answer the user's question strictly using the provided code context below.\n"
                "Rules:\n"
                "1. Ground your answer ONLY in the provided code snippets.\n"
                "2. Always cite exact file paths and line ranges (e.g. `[src/auth.py:12-25]`).\n"
                "3. If the code context does not contain the answer, state that you don't know based on the code provided.\n"
                "4. Format your answer in clean GitHub Markdown.\n\n"
                "--- CODE CONTEXT ---\n"
                "{context}"
            )),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])
        return qa_prompt | self.llm | StrOutputParser()

    def chat(
        self, 
        repository_id: str, 
        message: str, 
        chat_history: Sequence[BaseMessage], 
        top_k: int = 4
    ) -> dict:
        """
        Executes the modern LCEL conversational pipeline:
        1. Condenses query if history exists
        2. Retrieves relevant code chunks from ChromaDB
        3. Generates grounded answer with citations
        """
        # Step 1: Condense follow-up query if chat history exists
        history_list = list(chat_history)
        if history_list:
            search_query = self.rephrase_chain.invoke({
                "chat_history": history_list,
                "question": message
            })
        else:
            search_query = message

        # Step 2: Retrieve relevant code documents from ChromaDB
        retriever = ChromaLangChainRetriever(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            repository_id=repository_id,
            top_k=top_k
        )
        docs = retriever.invoke(search_query)

        # Step 3: Format code context
        if docs:
            context_str = "\n\n".join(
                f"--- Snippet {i} ---\n{d.page_content}"
                for i, d in enumerate(docs, start=1)
            )
        else:
            context_str = "No relevant code snippets were found in this repository."

        # Step 4: Generate grounded answer via LCEL QA chain
        answer = self.qa_chain.invoke({
            "context": context_str,
            "chat_history": history_list,
            "question": message
        })

        # Step 5: Extract citations from retrieved documents
        citations = []
        for doc in docs:
            meta = doc.metadata
            citations.append({
                "file_path": meta.get("file_path", ""),
                "symbol_name": meta.get("symbol_name") or None,
                "start_line": meta.get("start_line", 0),
                "end_line": meta.get("end_line", 0),
                "similarity_score": meta.get("similarity_score", 0.0)
            })

        return {
            "answer": answer,
            "citations": citations,
            "standalone_query": search_query
        }