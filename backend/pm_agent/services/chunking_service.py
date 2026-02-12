"""
Chunking Service
Splits text into chunks with configurable size and overlap.
"""
import os
import re
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ChunkingService:
    """Service for splitting text into chunks"""
    
    def __init__(self):
        # Default: 300 words per chunk, ~30 words overlap
        self.chunk_size_words = int(os.getenv("CHUNK_SIZE_WORDS", "300"))
        self.chunk_overlap_words = int(os.getenv("CHUNK_OVERLAP_WORDS", "30"))
    
    def _split_into_words(self, text: str) -> List[str]:
        """Split text into words while preserving separators"""
        # Use regex to split on whitespace, keeping separators
        words = re.findall(r'\S+|\s+', text)
        return [w for w in words if w.strip()]  # Remove empty strings
    
    def _count_words(self, text: str) -> int:
        """Count words in text"""
        words = text.split()
        return len(words)
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks with overlap.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List of chunk dictionaries with 'text' and 'metadata' keys
        """
        if not text or not text.strip():
            return []
        
        # Split into words
        words = self._split_into_words(text)
        
        if len(words) == 0:
            return []
        
        chunks = []
        current_chunk_words = []
        current_chunk_size = 0
        chunk_index = 0
        
        for i, word in enumerate(words):
            # Add word to current chunk
            current_chunk_words.append(word)
            current_chunk_size = self._count_words(''.join(current_chunk_words))
            
            # If chunk size reached, save chunk and start new one with overlap
            if current_chunk_size >= self.chunk_size_words:
                chunk_text = ''.join(current_chunk_words).strip()
                
                # Create chunk metadata
                chunk_metadata = {
                    "chunk_index": chunk_index,
                    **(metadata or {})
                }
                
                chunks.append({
                    "text": chunk_text,
                    "metadata": chunk_metadata
                })
                
                chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap_words > 0:
                    # Keep last N words for overlap
                    overlap_start = max(0, len(current_chunk_words) - self.chunk_overlap_words)
                    current_chunk_words = current_chunk_words[overlap_start:]
                else:
                    current_chunk_words = []
        
        # Add remaining words as final chunk
        if current_chunk_words:
            chunk_text = ''.join(current_chunk_words).strip()
            if chunk_text:
                chunk_metadata = {
                    "chunk_index": chunk_index,
                    **(metadata or {})
                }
                chunks.append({
                    "text": chunk_text,
                    "metadata": chunk_metadata
                })
        
        logger.info(f"Split text into {len(chunks)} chunks (size: {self.chunk_size_words} words, overlap: {self.chunk_overlap_words} words)")
        return chunks
    
    def chunk_text_simple(self, text: str) -> List[str]:
        """
        Simple chunking that returns just the text chunks.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        chunks = self.chunk_text(text)
        return [chunk["text"] for chunk in chunks]
    
    def chunk_text_by_characters(
        self,
        text: str,
        chunk_size: int = 400,
        chunk_overlap: int = 100,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks by characters with overlap.
        Used for Pinecone indexing with specific character limits.
        
        Args:
            text: Text to chunk
            chunk_size: Number of characters per chunk (default: 400)
            chunk_overlap: Number of overlapping characters (default: 100)
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List of chunk dictionaries with 'text' and 'metadata' keys
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        chunk_index = 0
        start = 0
        
        while start < len(text):
            # Calculate end position
            end = start + chunk_size
            
            # Extract chunk
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                # Create chunk metadata
                chunk_metadata = {
                    "chunk_index": chunk_index,
                    "chunk_start": start,
                    "chunk_end": min(end, len(text)),
                    **(metadata or {})
                }
                
                chunks.append({
                    "text": chunk_text,
                    "metadata": chunk_metadata
                })
                
                chunk_index += 1
            
            # Move start position forward (with overlap)
            start = end - chunk_overlap
            
            # Prevent infinite loop if overlap >= chunk_size
            if chunk_overlap >= chunk_size:
                start += 1
        
        logger.info(f"Split text into {len(chunks)} chunks (size: {chunk_size} chars, overlap: {chunk_overlap} chars)")
        return chunks

# Create service instance
chunking_service = ChunkingService()

