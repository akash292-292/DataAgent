"""
Pinecone Service
Manages Pinecone operations for storing and retrieving document chunks.
Uses ONE shared index for all documents (free-tier safe).
File separation is handled via metadata filtering (file_id).
"""

import os
import logging
from typing import List, Dict, Any, Optional

from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 🔑 Single shared index (free-tier safe)
RAG_INDEX_NAME = "document-rag-index"


class PineconeService:
    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY", "")
        self.embedding_dimension = 384  # all-MiniLM-L6-v2
        self._client: Optional[Pinecone] = None

        if not self.api_key:
            logger.warning("[PINECONE] PINECONE_API_KEY not set.")

    # --------------------------------------------------
    # Client
    # --------------------------------------------------
    def _get_client(self) -> Pinecone:
        if self._client is None:
            if not self.api_key:
                raise ValueError("PINECONE_API_KEY missing.")
            self._client = Pinecone(api_key=self.api_key)
            logger.info("[PINECONE] Client initialized.")
        return self._client
    
    def _get_index_name(self, file_id: int, file_name: str) -> str:
        """
        Generate a unique index name for a file.
        Format: kb-file-{file_id}-{sanitized_filename}
        Pinecone requires: lowercase alphanumeric characters and hyphens ONLY (no underscores)
        """
        import re
        # Sanitize filename: remove extension, replace spaces and special chars with hyphens
        # Remove file extension
        name_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
        
        # Replace spaces, underscores, and special characters with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9]', '-', name_without_ext)
        
        # Replace multiple consecutive hyphens with single hyphen
        sanitized = re.sub(r'-+', '-', sanitized)
        
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        
        # Convert to lowercase
        sanitized = sanitized.lower()
        
        # Limit length to 40 characters (to leave room for prefix)
        sanitized = sanitized[:40]
        
        # Ensure it doesn't start with a number (add prefix if needed)
        if sanitized and sanitized[0].isdigit():
            sanitized = 'file-' + sanitized
        
        # Build index name: kb-file-{file_id}-{sanitized}
        index_name = f"kb-file-{file_id}-{sanitized}".lower()
        
        # Final validation: ensure only lowercase alphanumeric and hyphens (NO underscores)
        index_name = re.sub(r'[^a-z0-9-]', '', index_name)
        
        # Remove consecutive hyphens
        index_name = re.sub(r'-+', '-', index_name)
        index_name = index_name.strip('-')
        
        # Ensure it doesn't start or end with hyphen
        if index_name.startswith('-'):
            index_name = 'kb' + index_name
        if index_name.endswith('-'):
            index_name = index_name[:-1]
        
        return index_name
    
    def get_index_name_for_file(self, file_id: int, file_name: str) -> str:
        """Public helper to get the Pinecone index name for a file"""
        return self._get_index_name(file_id, file_name)
    
    def index_exists(self, index_name: str) -> bool:
        """Check if a Pinecone index exists using the new SDK"""
        try:
            client = self._get_client()
            try:
                existing_indexes = client.list_indexes().names()
            except AttributeError:
                # Fallback in case .names() is not available
                existing_indexes = [idx.name for idx in client.list_indexes()]
            return index_name in existing_indexes
        except Exception as e:
            logger.error(f"Failed to list Pinecone indexes: {str(e)}")
            return False

    
    def create_index_for_file(
        self,
        file_id: int,
        file_name: str,
        dimension: int = None
    ) -> Dict[str, Any]:
        """
        Create a Pinecone index for a specific file.
        
        Args:
            file_id: Database ID of the file
            file_name: Original filename
            dimension: Embedding dimension (defaults to 384 for all-MiniLM-L6-v2)
            
        Returns:
            Dict with success status and index name
        """
        try:
            client = self._get_client()
            index_name = self._get_index_name(file_id, file_name)
            dim = dimension or self.embedding_dimension
            
            # Check if index already exists
            try:
                existing_indexes = client.list_indexes().names()
            except AttributeError:
                existing_indexes = [idx.name for idx in client.list_indexes()]
            
            if index_name in existing_indexes:
                logger.info(f"Index {index_name} already exists, skipping creation")
                return {
                    "success": True,
                    "index_name": index_name,
                    "created": False,
                    "message": f"Index {index_name} already exists"
                }
            
            # Create index
            logger.info(f"Creating Pinecone index: {index_name} (dimension: {dim})")
            
            # Use ServerlessSpec from the new SDK
            try:
                client.create_index(
                    name=index_name,
                    dimension=dim,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    ),
                )
            except Exception as create_error:
                # If index creation fails, it might already exist or be a different type
                logger.warning(f"Index creation returned error (might already exist): {str(create_error)}")
                # Check if index exists
                try:
                    existing_indexes = client.list_indexes().names()
                except AttributeError:
                    existing_indexes = [idx.name for idx in client.list_indexes()]
                if index_name in existing_indexes:
                    logger.info(f"Index {index_name} exists, continuing...")
                else:
                    raise create_error
            
            logger.info(f"Successfully created index: {index_name}")
            return {
                "success": True,
                "index_name": index_name,
                "created": True,
                "message": f"Index {index_name} created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create Pinecone index: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


    # --------------------------------------------------
    # Index lifecycle
    # --------------------------------------------------
    def ensure_shared_index(self):
        client = self._get_client()
        try:
            res = client.list_indexes()
            try:
                existing = res.names()
            except AttributeError:
                existing = [idx.name for idx in res]

            if RAG_INDEX_NAME in existing:
                logger.info(f"[PINECONE] Index '{RAG_INDEX_NAME}' exists.")
                return

            logger.info(f"[PINECONE] Creating index '{RAG_INDEX_NAME}'...")
            client.create_index(
                name=RAG_INDEX_NAME,
                dimension=self.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            logger.info("[PINECONE] Index created.")

        except Exception as e:
            if "quota" in str(e).lower() or "max serverless indexes" in str(e).lower():
                logger.warning("[PINECONE] Quota reached. Using existing index.")
            else:
                raise

    # --------------------------------------------------
    # Ingestion (First-time upload)
    # --------------------------------------------------
    def index_file_chunks(
        self,
        file_id: int,
        file_name: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> Dict[str, Any]:
        try:
            index = self._get_client().Index(RAG_INDEX_NAME)

            vectors = []
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                vectors.append({
                    "id": f"chunk_{file_id}_{i}",
                    "values": emb,
                    "metadata": {
                        "file_id": str(file_id),  # MUST be string
                        "file_name": file_name,
                        "text": chunk.get("text", ""),
                        "chunk_index": i,
                    },
                })

            for i in range(0, len(vectors), 100):
                index.upsert(vectors=vectors[i:i + 100])

            logger.info(f"[PINECONE] Indexed {len(vectors)} chunks for file {file_id}")
            return {"success": True, "chunks_indexed": len(vectors)}

        except Exception as e:
            logger.error(f"[PINECONE] Indexing failed: {e}")
            return {"success": False, "error": str(e)}

    # --------------------------------------------------
    # Retrieval (Chat)
    # --------------------------------------------------
    def query_file_chunks(
        self,
        query_embedding: List[float],
        file_id: int,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            index = self._get_client().Index(RAG_INDEX_NAME)

            response = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter={"file_id": {"$eq": str(file_id)}}
            )

            return response.get("matches", [])

        except Exception as e:
            logger.error(f"[PINECONE] Query failed: {e}")
            return []

    def search_across_indexes(
        self,
        query_embedding: List[float],
        index_names: List[str],
        top_k: int = 10
    ) -> Dict[str, Any]:
        try:
            index = self._get_client().Index(RAG_INDEX_NAME)

            response = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )

            results = []
            for m in response.get("matches", []):
                results.append({
                    "id": m.get("id"),
                    "score": m.get("score"),
                    "metadata": m.get("metadata"),
                    "index_name": RAG_INDEX_NAME,
                })

            return {"success": True, "results": results}

        except Exception as e:
            logger.error(f"[PINECONE] Cross-search failed: {e}")
            return {"success": False, "error": str(e)}

    # --------------------------------------------------
    # Cleanup (20-day expiry)
    # --------------------------------------------------
    def delete_index(self, file_id: int, file_name: str = None) -> Dict[str, Any]:
        try:
            index = self._get_client().Index(RAG_INDEX_NAME)
            index.delete(filter={"file_id": {"$eq": str(file_id)}})
            logger.info(f"[PINECONE] Deleted vectors for file {file_id}")
            return {"success": True}
        except Exception as e:
            logger.error(f"[PINECONE] Cleanup failed: {e}")
            return {"success": False, "error": str(e)}

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def list_indexes(self) -> List[str]:
        try:
            res = self._get_client().list_indexes()
            try:
                return res.names()
            except AttributeError:
                return [idx.name for idx in res]
        except Exception:
            return []

    def index_exists(self, index_name: str) -> bool:
        return index_name in self.list_indexes()

    def get_index_name_for_file(self, file_id: int, file_name: str) -> str:
        return RAG_INDEX_NAME


# ✅ Singleton
pinecone_service = PineconeService()
