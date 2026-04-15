import tiktoken
from typing import List


class ChunkingService:
    """
    Service for chunking text into smaller segments with overlap.
    
    Chunking Strategy:
    - Chunk Size: 400 tokens (within the 300-500 range for optimal semantic precision)
    - Overlap: 80 tokens (within the 50-100 range to prevent context loss)
    
    This configuration provides:
    - Better semantic precision in retrieval (smaller chunks)
    - Context preservation across boundaries (overlap)
    """
    
    def __init__(self, chunk_size: int = 400, overlap: int = 80):
        """
        Initialize the chunking service.
        
        Args:
            chunk_size: Target chunk size in tokens (default: 400)
            overlap: Overlap between chunks in tokens (default: 80)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.
        
        Args:
            text: Input text
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks with overlap based on token count.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        # Split into paragraphs first to maintain semantic coherence
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for paragraph in paragraphs:
            paragraph_tokens = self.count_tokens(paragraph)
            
            # If single paragraph is larger than chunk size, split it
            if paragraph_tokens > self.chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    current_tokens = 0
                
                # Split large paragraph by sentences
                sentences = self._split_into_sentences(paragraph)
                for sentence in sentences:
                    sentence_tokens = self.count_tokens(sentence)
                    
                    if current_tokens + sentence_tokens <= self.chunk_size:
                        current_chunk += " " + sentence
                        current_tokens += sentence_tokens
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence
                        current_tokens = sentence_tokens
                        
                        # Add overlap from previous chunk
                        if chunks and self.overlap > 0:
                            overlap_text = self._get_overlap_text(chunks[-1], self.overlap)
                            if overlap_text:
                                current_chunk = overlap_text + " " + current_chunk
                                current_tokens += self.count_tokens(overlap_text)
            else:
                # Add paragraph to current chunk
                if current_tokens + paragraph_tokens <= self.chunk_size:
                    current_chunk += "\n\n" + paragraph if current_chunk else paragraph
                    current_tokens += paragraph_tokens
                else:
                    # Save current chunk and start new one
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    
                    # Add overlap from previous chunk
                    if chunks and self.overlap > 0:
                        overlap_text = self._get_overlap_text(chunks[-1], self.overlap)
                        current_chunk = overlap_text + "\n\n" + paragraph if overlap_text else paragraph
                        current_tokens = self.count_tokens(overlap_text) + paragraph_tokens if overlap_text else paragraph_tokens
                    else:
                        current_chunk = paragraph
                        current_tokens = paragraph_tokens
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _get_overlap_text(self, text: str, overlap_tokens: int) -> str:
        """
        Get the last N tokens from text for overlap.
        
        Args:
            text: Source text
            overlap_tokens: Number of tokens to extract
            
        Returns:
            Overlap text
        """
        tokens = self.encoding.encode(text)
        if len(tokens) <= overlap_tokens:
            return text
        
        overlap_tokens_list = tokens[-overlap_tokens:]
        return self.encoding.decode(overlap_tokens_list)
