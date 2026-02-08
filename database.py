"""
Supabase products table upsert.
Unique constraint: (source, product_url). Upsert on conflict.
"""
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List

from config import SUPABASE_URL, SUPABASE_KEY, SOURCE, BRAND, SECOND_HAND, COUNTRY

logger = logging.getLogger(__name__)


def generate_id(source: str, product_url: str) -> str:
    return hashlib.sha256(f"{source}:{product_url}".encode()).hexdigest()


def prepare_row(
    record: Dict[str, Any],
    image_embedding: Optional[List[float]] = None,
    info_embedding: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Build one row for public.products. All required and optional fields."""
    product_url = record.get("product_url") or ""
    product_id = generate_id(SOURCE, product_url)

    metadata_str = None
    if record.get("metadata"):
        metadata_str = json.dumps(record["metadata"]) if isinstance(record["metadata"], dict) else str(record["metadata"])

    row = {
        "id": product_id,
        "source": SOURCE,
        "product_url": product_url,
        "affiliate_url": None,
        "image_url": record.get("image_url") or "",
        "brand": BRAND,
        "title": record.get("title") or "",
        "description": record.get("description"),
        "category": record.get("category"),
        "gender": record.get("gender"),
        "metadata": metadata_str,
        "size": record.get("size"),
        "second_hand": SECOND_HAND,
        "country": COUNTRY,
        "compressed_image_url": None,
        "tags": record.get("tags"),
        "other": None,
        "price": record.get("price"),
        "sale": record.get("sale"),
        "additional_images": record.get("additional_images") or None,
    }

    if image_embedding is not None:
        row["image_embedding"] = image_embedding
    if info_embedding is not None:
        row["info_embedding"] = info_embedding

    return row


def get_supabase_client():
    """Create Supabase client."""
    from supabase import create_client
    if not SUPABASE_KEY:
        raise ValueError("SUPABASE_SERVICE_KEY or SUPABASE_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def upsert_product(row: Dict[str, Any], supabase_client) -> bool:
    """Insert or update one product. Uses upsert on (source, product_url)."""
    try:
        supabase_client.table("products").upsert(
            row,
            on_conflict="source,product_url",
        ).execute()
        return True
    except Exception as e:
        logger.error("Upsert failed for %s: %s", row.get("product_url"), e)
        return False
