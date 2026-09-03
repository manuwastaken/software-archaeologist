import os
import time
import random
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence
from google import genai
from google.genai import types

MODEL_NAME = "models/gemini-embedding-001"
DEFAULT_BATCH_SIZE = 50
MAX_WORKERS = 4
MAX_CHARS_PER_TEXT = 8000  # Safety boundary against model token overflow


class GeminiEmbeddingService:
    """
    Hyper-optimized Gemini Embedding client using the modern google-genai SDK.
    Features:
    - Multi-threaded concurrent batching
    - Exponential backoff with jitter on 429/503
    - In-memory LRU query cache
    - text-embedding-004 model
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please add it to your environment or .env file."
            )
        self.client = genai.Client(api_key=self.api_key)

    def _retry_with_backoff(self, func, *args, max_retries: int = 4, **kwargs):
        """Executes a function with exponential backoff and jitter upon rate-limits."""
        delay = 1.0
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "429" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg
                is_transient = "503" in err_msg or "unavailable" in err_msg

                if (is_rate_limit or is_transient) and attempt < max_retries - 1:
                    jitter = random.uniform(0.1, 0.5)
                    sleep_time = delay + jitter
                    print(f"[Embeddings] Rate limit or transient error. Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                    delay *= 2.0
                else:
                    raise e

    def _embed_single_batch(self, batch_texts: list[str], task_type: str) -> list[list[float]]:
        """Sends one batch of texts to the Gemini API."""
        sanitized = [t[:MAX_CHARS_PER_TEXT].strip() for t in batch_texts]

        def _call_api():
            response = self.client.models.embed_content(
                model=MODEL_NAME,
                contents=sanitized,
                config=types.EmbedContentConfig(task_type=task_type)
            )
            return [emb.values for emb in response.embeddings]

        return self._retry_with_backoff(_call_api)

    @functools.lru_cache(maxsize=512)
    def embed_query(self, query: str) -> list[float]:
        """
        Embeds a single search query with LRU in-memory cache.
        Uses task_type="RETRIEVAL_QUERY" for optimal search relevance.
        """
        query_text = query[:MAX_CHARS_PER_TEXT].strip()
        task_type = "RETRIEVAL_QUERY"

        def _call():
            response = self.client.models.embed_content(
                model=MODEL_NAME,
                contents=query_text,
                config=types.EmbedContentConfig(task_type=task_type)
            )
            return response.embeddings[0].values

        return self._retry_with_backoff(_call)

    def embed_documents(
        self, 
        texts: Sequence[str], 
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> list[list[float]]:
        """
        Embeds multiple code chunks concurrently across threads.
        Maintains the exact original ordering of the input texts.
        Uses task_type="RETRIEVAL_DOCUMENT".
        """
        if not texts:
            return []

        # Split texts into batches
        batches = [
            (i, list(texts[i:i + batch_size]))
            for i in range(0, len(texts), batch_size)
        ]

        results: list[list[float] | None] = [None] * len(texts)

        # If only 1 batch, avoid threadpool overhead
        if len(batches) == 1:
            start_idx, batch_texts = batches[0]
            return self._embed_single_batch(batch_texts, task_type="RETRIEVAL_DOCUMENT")

        # Fire multiple batches concurrently
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_idx = {
                executor.submit(self._embed_single_batch, batch_texts, "RETRIEVAL_DOCUMENT"): (start_idx, len(batch_texts))
                for start_idx, batch_texts in batches
            }

            for future in as_completed(future_to_idx):
                start_idx, count = future_to_idx[future]
                batch_embeddings = future.result()
                results[start_idx : start_idx + count] = batch_embeddings

        return results