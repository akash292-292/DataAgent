"""
Embedding Service - LITE VERSION (Optimized for 512MB RAM)
Provides text embeddings using local sentence-transformers or hosted providers.
"""
import os
import gc  # Crucial for clearing memory on Render
from typing import List
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self):
        self.provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
        self.model_name = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
        self._model = None
        self._embedding_dimension = None
        
    def _load_local_model(self):
        """LITE MODE: Load model in CPU-safe FP32"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                import torch

                # FORCE CPU
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
                os.environ["TORCH_NUM_THREADS"] = "1"
                os.environ["TOKENIZERS_PARALLELISM"] = "false"

                device = "cuda" if torch.cuda.is_available() else "cpu"

                logger.info(f"Loading local model: {self.model_name} on {device}...")

                # ⚡ FIXED: Always use FP32
                self._model = SentenceTransformer(
                    self.model_name,
                    device=device
                )

                # Force float32 on CPU (prevents Half precision errors)
                if device == "cpu":
                    self._model = self._model.float()

                self._embedding_dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded successfully. Dimension: {self._embedding_dimension}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {str(e)}")
                raise

    def _embed_with_openai(self, texts: List[str]) -> List[List[float]]:
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            response = client.embeddings.create(model=model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {str(e)}")
            raise

    def _embed_with_vertex(self, texts: List[str]) -> List[List[float]]:
        try:
            from google.cloud import aiplatform
            from vertexai.language_models import TextEmbeddingModel
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT not set")
            aiplatform.init(project=project_id, location=location)
            model = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")
            return [model.get_embeddings([t])[0].values for t in texts]
        except Exception as e:
            logger.error(f"Vertex AI embedding failed: {str(e)}")
            raise

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            if self.provider == "local":
                self._load_local_model()
                embeddings = self._model.encode(
                    texts,
                    convert_to_numpy=True,
                    batch_size=4,
                    show_progress_bar=False
                )
                return embeddings.tolist()
            elif self.provider == "openai":
                return self._embed_with_openai(texts)
            elif self.provider == "vertex":
                return self._embed_with_vertex(texts)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        finally:
            gc.collect()

    def embed_query(self, query: str) -> List[float]:
        embeddings = self.embed([query])
        return embeddings[0] if embeddings else []
    
    def get_embedding_dimension(self) -> int:
        if self.provider == "local":
            self._load_local_model()
            return self._embedding_dimension
        elif self.provider == "openai":
            return 1536
        elif self.provider == "vertex":
            return 768
        return 384

# Create service instance
embedding_service = EmbeddingService()
