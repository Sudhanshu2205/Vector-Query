import os
import pickle
import numpy as np
import faiss
from typing import List, Dict, Tuple, Optional
from pathlib import Path


class VectorStore:
    """
    FAISS-based vector store for efficient similarity search.
    
    Uses IndexFlatIP (inner product) for cosine similarity when vectors are normalized.
    Fast, local, and requires no infrastructure overhead.
    """
    
    def __init__(self, vector_store_dir: str = "vector_store"):
        """
        Initialize the vector store.
        
        Args:
            vector_store_dir: Directory to store vector indexes
        """
        self.vector_store_dir = Path(vector_store_dir)
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)
        
        self.indexes: Dict[str, faiss.Index] = {}
        self.metadata: Dict[str, List[Dict]] = {}
    
    def create_index(self, doc_id: str, embedding_dim: int) -> faiss.Index:
        """
        Create a new FAISS index for a document.
        
        Args:
            doc_id: Document identifier
            embedding_dim: Dimension of embedding vectors
            
        Returns:
            FAISS index
        """
        # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
        index = faiss.IndexFlatIP(embedding_dim)
        self.indexes[doc_id] = index
        self.metadata[doc_id] = []
        
        return index
    
    def add_embeddings(self, doc_id: str, embeddings: np.ndarray, chunks: List[str]):
        """
        Add embeddings to the document's index.
        
        Args:
            doc_id: Document identifier
            embeddings: Embedding vectors (n x d)
            chunks: Corresponding text chunks
        """
        if doc_id not in self.indexes:
            raise ValueError(f"No index found for document {doc_id}")
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self.indexes[doc_id].add(embeddings.astype('float32'))
        
        # Store metadata
        for i, chunk in enumerate(chunks):
            self.metadata[doc_id].append({
                'chunk_id': i,
                'text': chunk,
                'doc_id': doc_id
            })
    
    def search(self, doc_id: str, query_embedding: np.ndarray, top_k: int = 5) -> Tuple[List[Dict], np.ndarray]:
        """
        Search for similar chunks.
        
        Args:
            doc_id: Document identifier
            query_embedding: Query embedding vector
            top_k: Number of top results to return
            
        Returns:
            Tuple of (list of chunk metadata with scores, similarity scores)
        """
        if doc_id not in self.indexes:
            raise ValueError(f"No index found for document {doc_id}")
        
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.indexes[doc_id].search(query_embedding, top_k)
        
        # Get metadata for results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata[doc_id]):
                result = self.metadata[doc_id][idx].copy()
                result['score'] = float(scores[0][i])
                results.append(result)
        
        return results, scores[0]
    
    def save_index(self, doc_id: str):
        """
        Save index and metadata to disk.
        
        Args:
            doc_id: Document identifier
        """
        if doc_id not in self.indexes:
            raise ValueError(f"No index found for document {doc_id}")
        
        # Save FAISS index
        index_path = self.vector_store_dir / f"{doc_id}.index"
        faiss.write_index(self.indexes[doc_id], str(index_path))
        
        # Save metadata
        metadata_path = self.vector_store_dir / f"{doc_id}.metadata"
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.metadata[doc_id], f)
    
    def load_index(self, doc_id: str):
        """
        Load index and metadata from disk.
        
        Args:
            doc_id: Document identifier
        """
        index_path = self.vector_store_dir / f"{doc_id}.index"
        metadata_path = self.vector_store_dir / f"{doc_id}.metadata"
        
        if not index_path.exists() or not metadata_path.exists():
            raise ValueError(f"No saved index found for document {doc_id}")
        
        # Load FAISS index
        self.indexes[doc_id] = faiss.read_index(str(index_path))
        
        # Load metadata
        with open(metadata_path, 'rb') as f:
            self.metadata[doc_id] = pickle.load(f)
    
    def index_exists(self, doc_id: str) -> bool:
        """
        Check if an index exists for a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            True if index exists, False otherwise
        """
        index_path = self.vector_store_dir / f"{doc_id}.index"
        metadata_path = self.vector_store_dir / f"{doc_id}.metadata"
        return index_path.exists() and metadata_path.exists()
    
    def delete_index(self, doc_id: str):
        """
        Delete index and metadata for a document.
        
        Args:
            doc_id: Document identifier
        """
        if doc_id in self.indexes:
            del self.indexes[doc_id]
        if doc_id in self.metadata:
            del self.metadata[doc_id]
        
        index_path = self.vector_store_dir / f"{doc_id}.index"
        metadata_path = self.vector_store_dir / f"{doc_id}.metadata"
        
        if index_path.exists():
            index_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
