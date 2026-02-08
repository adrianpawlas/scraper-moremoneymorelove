"""
Image and text embeddings using google/siglip-base-patch16-384 (768-dim).
- image_embedding: from product main image
- info_embedding: from product text (title, price, description, category, etc.) via SigLIP text encoder
"""
import logging
from typing import Optional, List
import requests
from io import BytesIO
import torch
import numpy as np
from PIL import Image
from transformers import AutoProcessor, AutoModel

from config import EMBEDDING_MODEL, EMBEDDING_DIM, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """SigLIP for image and text embeddings (768-dim)."""

    def __init__(self):
        logger.info("Loading SigLIP model: %s", EMBEDDING_MODEL)
        self.processor = AutoProcessor.from_pretrained(EMBEDDING_MODEL)
        self.model = AutoModel.from_pretrained(EMBEDDING_MODEL)
        self.model.eval()
        self._embedding_dim = EMBEDDING_DIM
        logger.info("SigLIP loaded.")

    def _download_image(self, image_url: str) -> Optional[Image.Image]:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = requests.get(image_url, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content))
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img
        except Exception as e:
            logger.warning("Download image failed %s: %s", image_url[:80], e)
            return None

    def _ensure_dim(self, vec: np.ndarray) -> Optional[List[float]]:
        """Normalize and ensure length EMBEDDING_DIM."""
        vec = np.asarray(vec, dtype=np.float64).flatten()
        norm = np.linalg.norm(vec)
        if norm <= 0:
            return None
        vec = vec / norm
        if len(vec) == self._embedding_dim:
            return vec.tolist()
        if len(vec) > self._embedding_dim:
            vec = vec[: self._embedding_dim]
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.tolist()
        # Pad with zeros and renormalize
        pad = np.zeros(self._embedding_dim - len(vec))
        vec = np.concatenate([vec, pad])
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def image_embedding(self, image_url: str) -> Optional[List[float]]:
        """Return 768-dim embedding for the image at image_url."""
        img = self._download_image(image_url)
        if img is None:
            return None
        try:
            inputs = self.processor(images=img, return_tensors="pt")
            with torch.no_grad():
                out = self.model.get_image_features(**inputs)
                vec = out[0].cpu().numpy()
            return self._ensure_dim(vec)
        except Exception as e:
            logger.warning("Image embedding failed: %s", e)
            try:
                with torch.no_grad():
                    vision_out = self.model.vision_model(**inputs)
                    if hasattr(vision_out, "pooler_output") and vision_out.pooler_output is not None:
                        vec = vision_out.pooler_output[0].cpu().numpy()
                    elif hasattr(vision_out, "last_hidden_state"):
                        vec = vision_out.last_hidden_state[0].mean(dim=0).cpu().numpy()
                    else:
                        return None
                return self._ensure_dim(vec)
            except Exception as e2:
                logger.warning("Vision fallback failed: %s", e2)
                return None

    def text_embedding(self, text: str) -> Optional[List[float]]:
        """Return 768-dim embedding for text using SigLIP text encoder."""
        if not (text and text.strip()):
            return None
        try:
            # Text-only: use tokenizer (get_text_features expects input_ids, attention_mask only)
            inputs = self.processor.tokenizer(
                text.strip(),
                padding="max_length",
                max_length=64,
                truncation=True,
                return_tensors="pt",
            )
            text_inputs = {k: v for k, v in inputs.items() if k in ("input_ids", "attention_mask")}
            with torch.no_grad():
                out = self.model.get_text_features(**text_inputs)
                if hasattr(out, "pooler_output") and out.pooler_output is not None:
                    vec = out.pooler_output[0].cpu().numpy()
                elif hasattr(out, "last_hidden_state"):
                    vec = out.last_hidden_state[0, 0, :].cpu().numpy()
                else:
                    vec = out[0].cpu().numpy()
            return self._ensure_dim(vec)
        except Exception as e:
            logger.warning("Text embedding failed: %s", e)
            return None

    def info_embedding_from_record(self, record: dict) -> Optional[List[float]]:
        """Build one text string from product record and return its embedding."""
        parts = []
        if record.get("title"):
            parts.append(str(record["title"]))
        if record.get("brand"):
            parts.append(str(record["brand"]))
        if record.get("price"):
            parts.append(f"Price: {record['price']}")
        if record.get("sale"):
            parts.append(f"Sale: {record['sale']}")
        if record.get("category"):
            parts.append(f"Category: {record['category']}")
        if record.get("gender"):
            parts.append(f"Gender: {record['gender']}")
        if record.get("description"):
            parts.append(record["description"][:2000])
        if record.get("metadata"):
            import json
            try:
                m = record["metadata"] if isinstance(record["metadata"], dict) else json.loads(record["metadata"])
                parts.append(json.dumps(m)[:1000])
            except Exception:
                pass
        text = " ".join(parts)
        return self.text_embedding(text)
