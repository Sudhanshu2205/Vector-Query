import numpy as np
from typing import List, Dict, Tuple
import time


class RetrievalService:
    """
    Service for retrieving relevant chunks using similarity search.
    
    Retrieval Strategy:
    - Top-K: 3 to 5 chunks (configurable)
    - Similarity Metric: Cosine similarity (via FAISS inner product with normalized vectors)
    - Returns chunks with similarity scores for context relevance
    """
    
    def __init__(self, top_k: int = 5):
        """
        Initialize the retrieval service.
        
        Args:
            top_k: Number of top chunks to retrieve (default: 5)
        """
        self.top_k = top_k
    
    def retrieve(
        self,
        vector_store,
        doc_id: str,
        query_embedding: np.ndarray,
        top_k: int = None
    ) -> Tuple[List[Dict], float]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            vector_store: VectorStore instance
            doc_id: Document identifier
            query_embedding: Query embedding vector
            top_k: Override default top_k if provided
            
        Returns:
            Tuple of (list of retrieved chunks with metadata, retrieval time in ms)
        """
        start_time = time.time()
        
        k = top_k if top_k is not None else self.top_k
        results, scores = vector_store.search(doc_id, query_embedding, top_k=k)
        
        retrieval_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return results, retrieval_time
    
    def format_context(self, retrieved_chunks: List[Dict]) -> str:
        """
        Format retrieved chunks into context string for LLM.
        
        Args:
            retrieved_chunks: List of retrieved chunk metadata
            
        Returns:
            Formatted context string
        """
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            context_parts.append(
                f"[Source {i}] (Relevance: {chunk['score']:.3f}):\n{chunk['text']}"
            )
        return "\n\n".join(context_parts)
