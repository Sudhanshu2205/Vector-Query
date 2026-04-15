import hashlib
import json
import re
import shutil
from typing import List
import numpy as np
import os
from pathlib import Path


class EmbeddingService:
    """
    Service for generating text embeddings using sentence-transformers.
    
    Model: all-MiniLM-L6-v2
    - Fast inference
    - Local execution (no API costs)
    - Good semantic similarity for retrieval
    - 384-dimensional embeddings
    """
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the sentence-transformers model
        """
        self.model_name = os.getenv("EMBEDDING_MODEL", model_name)
        self.model = None
        self.backend = None
        self.model_error = None
        self.fallback_dimension = 384
    
    def _configure_cache_dir(self) -> Path:
        """Keep all model caches inside the project workspace by default."""
        cache_root = Path(
            os.getenv("VECTORQUERY_CACHE_DIR")
            or Path(__file__).resolve().parents[2] / ".cache"
        )

        cache_root.mkdir(parents=True, exist_ok=True)

        sentence_transformers_cache = cache_root / "sentence_transformers"
        huggingface_home = cache_root / "huggingface"
        huggingface_hub_cache = huggingface_home / "hub"
        transformers_cache = cache_root / "transformers"

        for path in (
            sentence_transformers_cache,
            huggingface_home,
            huggingface_hub_cache,
            transformers_cache,
        ):
            path.mkdir(parents=True, exist_ok=True)

        os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(sentence_transformers_cache)
        os.environ["HF_HOME"] = str(huggingface_home)
        os.environ["HF_HUB_CACHE"] = str(huggingface_hub_cache)
        os.environ["HUGGINGFACE_HUB_CACHE"] = str(huggingface_hub_cache)
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ.pop("TRANSFORMERS_CACHE", None)

        return sentence_transformers_cache

    def _get_local_model_dir(self, cache_dir: Path) -> Path:
        """Map a model repo id to a normal local directory."""
        return cache_dir / self.model_name.replace("/", "__")

    def _ensure_special_tokens_map(self, model_dir: Path) -> None:
        """Backfill special_tokens_map.json when older model repos omit it."""
        tokenizer_config_path = model_dir / "tokenizer_config.json"
        special_tokens_map_path = model_dir / "special_tokens_map.json"

        if special_tokens_map_path.exists() or not tokenizer_config_path.exists():
            return

        tokenizer_config = json.loads(tokenizer_config_path.read_text(encoding="utf-8"))
        special_tokens_map = {
            key: tokenizer_config[key]
            for key in (
                "unk_token",
                "sep_token",
                "pad_token",
                "cls_token",
                "mask_token",
            )
            if tokenizer_config.get(key)
        }

        if special_tokens_map:
            special_tokens_map_path.write_text(
                json.dumps(special_tokens_map, indent=2),
                encoding="utf-8",
            )

    def _download_model(self, cache_dir: Path) -> Path:
        """Download the embedding model into a regular local directory."""
        from huggingface_hub import snapshot_download

        model_dir = self._get_local_model_dir(cache_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        required_files = (
            model_dir / "modules.json",
            model_dir / "config.json",
            model_dir / "tokenizer.json",
            model_dir / "tokenizer_config.json",
            model_dir / "1_Pooling" / "config.json",
        )

        if not all(path.exists() for path in required_files):
            if model_dir.exists():
                shutil.rmtree(model_dir, ignore_errors=True)
            model_dir.mkdir(parents=True, exist_ok=True)

            snapshot_download(
                repo_id=self.model_name,
                local_dir=str(model_dir),
                max_workers=1,
            )

        self._ensure_special_tokens_map(model_dir)

        if not all(path.exists() for path in required_files):
            missing_files = [str(path) for path in required_files if not path.exists()]
            raise RuntimeError(
                "Embedding model download is incomplete. Missing files: "
                + ", ".join(missing_files)
            )

        return model_dir
    
    def _load_model(self):
        """Load the embedding model."""
        cache_dir = self._configure_cache_dir()
        model_dir = self._download_model(cache_dir)
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(str(model_dir), cache_folder=str(cache_dir))
        self.backend = "sentence-transformers"

    def _ensure_backend(self) -> None:
        """Prefer sentence-transformers, but degrade gracefully offline."""
        if self.backend is not None:
            return

        try:
            self._load_model()
        except Exception as e:
            self.backend = "hashing"
            self.model_error = str(e)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into unigrams and bigrams for lexical similarity."""
        words = re.findall(r"\b\w+\b", text.lower())
        bigrams = [f"{left}_{right}" for left, right in zip(words, words[1:])]
        return words + bigrams

    def _hash_embedding(self, text: str) -> np.ndarray:
        """Generate a deterministic local embedding without external downloads."""
        vector = np.zeros(self.fallback_dimension, dtype="float32")

        for token in self._tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.fallback_dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        return vector
    
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as numpy array
        """
        self._ensure_backend()

        if self.model is not None:
            return self.model.encode(text, convert_to_numpy=True)

        return self._hash_embedding(text)
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            Matrix of embeddings as numpy array
        """
        self._ensure_backend()

        if self.model is not None:
            return self.model.encode(texts, convert_to_numpy=True)

        if not texts:
            return np.empty((0, self.fallback_dimension), dtype="float32")

        return np.vstack([self._hash_embedding(text) for text in texts])
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors.
        
        Returns:
            Embedding dimension
        """
        self._ensure_backend()

        if self.model is not None:
            return self.model.get_sentence_embedding_dimension()

        return self.fallback_dimension
