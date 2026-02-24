"""
Supabase products table via PostgREST REST API (no SDK).
- Unique constraint: (source, product_url). Upsert on conflict.
- Smart sync: after upsert, remove products for this source that are no longer in the catalog.
"""
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, Set

import requests

from config import SUPABASE_URL, SUPABASE_KEY, SOURCE, BRAND, SECOND_HAND, COUNTRY

logger = logging.getLogger(__name__)

# PostgREST base URL (no trailing slash)
REST_BASE = f"{SUPABASE_URL.rstrip('/')}/rest/v1"
PRODUCTS_ENDPOINT = f"{REST_BASE}/products"

# Chunk size for upsert and for delete batches
CHUNK_SIZE = 100


def _session():
    """HTTP session with Supabase PostgREST headers. Fails fast if key missing."""
    if not SUPABASE_KEY:
        raise ValueError("SUPABASE_SERVICE_KEY or SUPABASE_KEY must be set in .env")
    s = requests.Session()
    s.headers.update({
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    })
    return s


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


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure every row has the same set of keys (PostgREST requirement). Use None for missing."""
    if not rows:
        return []
    all_keys = set()
    for r in rows:
        all_keys.update(r.keys())
    return [{k: r.get(k) for k in all_keys} for r in rows]


def upsert_products(rows: List[Dict[str, Any]]) -> bool:
    """
    Upsert all products via PostgREST in chunks. On chunk failure, retry that chunk row-by-row.
    Returns True if all succeeded, False otherwise.
    """
    if not rows:
        return True
    normalized = _normalize_rows(rows)
    session = _session()
    prefer = "resolution=merge-duplicates,return=minimal"

    for i in range(0, len(normalized), CHUNK_SIZE):
        chunk = normalized[i : i + CHUNK_SIZE]
        r = session.post(
            PRODUCTS_ENDPOINT,
            headers={"Prefer": prefer},
            data=json.dumps(chunk),
            timeout=60,
        )
        if r.status_code in (200, 201, 204):
            continue
        logger.warning("Batch upsert failed %s: %s", r.status_code, r.text[:500])
        # Retry chunk one row at a time
        for row in chunk:
            rr = session.post(
                PRODUCTS_ENDPOINT,
                headers={"Prefer": prefer},
                data=json.dumps([row]),
                timeout=60,
            )
            if rr.status_code not in (200, 201, 204):
                logger.error("Upsert failed for id=%s: %s %s", row.get("id"), rr.status_code, rr.text[:300])
                return False
    return True


def get_existing_product_ids_for_source() -> Set[str]:
    """Return set of product ids currently in DB for this source."""
    session = _session()
    # PostgREST: select id where source=SOURCE; paginate if needed
    ids: Set[str] = set()
    offset = 0
    while True:
        r = session.get(
            PRODUCTS_ENDPOINT,
            params={"source": f"eq.{SOURCE}", "select": "id", "offset": offset, "limit": 1000},
            timeout=30,
        )
        if r.status_code != 200:
            logger.error("Failed to fetch existing ids: %s %s", r.status_code, r.text[:300])
            return ids
        data = r.json()
        if not data:
            break
        for row in data:
            if row.get("id"):
                ids.add(row["id"])
        if len(data) < 1000:
            break
        offset += len(data)
    return ids


def remove_stale_products(current_scraped_ids: Set[str]) -> int:
    """
    Delete products for this source that are not in current_scraped_ids (no longer in catalog).
    Returns number of rows deleted.
    """
    existing = get_existing_product_ids_for_source()
    to_remove = existing - current_scraped_ids
    if not to_remove:
        return 0
    session = _session()
    deleted = 0
    id_list = list(to_remove)
    for i in range(0, len(id_list), CHUNK_SIZE):
        batch = id_list[i : i + CHUNK_SIZE]
        # PostgREST: DELETE where id in (id1, id2, ...)
        r = session.delete(
            PRODUCTS_ENDPOINT,
            params={"id": f"in.({','.join(batch)})"},
            timeout=60,
        )
        if r.status_code in (200, 204):
            deleted += len(batch)
        else:
            logger.warning("Delete batch failed: %s %s", r.status_code, r.text[:300])
    return deleted


