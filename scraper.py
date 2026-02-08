"""
Fetch all products from More Money More Love (Shopify) via collection JSON API.
Pagination: page=1, 2, ... until products array is empty.
"""
import re
import time
import logging
from typing import Iterator, List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

from config import (
    COLLECTION_URL,
    BASE_URL,
    PRODUCTS_JSON_PATH,
    LIMIT_PER_PAGE,
    REQUEST_TIMEOUT,
    REQUEST_DELAY,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)

# English collection path for JSON (store uses /en/ for English)
COLLECTION_HANDLE = "shop-all"
JSON_BASE = "https://moremoneymorelove.de/en/collections"


def _strip_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _normalize_category(product_type: Optional[str]) -> Optional[str]:
    """Map product_type to category; if multiple (e.g. 'Sweaters & Hoodies'), comma-separate."""
    if not product_type:
        return None
    # e.g. "Sweaters & Hoodies" -> "Sweaters, Hoodies"
    out = product_type.replace(" & ", ", ").replace(" and ", ", ")
    return out.strip() if out else None


def _infer_gender(product: Dict[str, Any]) -> str:
    """Infer gender: 'woman' only for girls/women products, else 'man' (store is mostly men)."""
    tags = [t.upper() for t in (product.get("tags") or [])]
    ptype = (product.get("product_type") or "").upper()
    title = (product.get("title") or "").upper()
    if "GIRLS" in ptype or "GIRLS" in title or any("GIRL" in t for t in tags):
        return "woman"
    if "WOMEN" in ptype or "WOMEN" in title:
        return "woman"
    return "man"


def _price_string(product: Dict[str, Any]) -> Optional[str]:
    """Original price only, with currency. e.g. 159.99EUR. Uses compare_at_price when present."""
    variants = product.get("variants") or []
    if not variants:
        return None
    v = variants[0]
    compare = v.get("compare_at_price")  # original
    price = v.get("price")  # fallback if no compare
    value = compare or price
    if not value:
        return None
    try:
        return f"{float(value):.2f}EUR"
    except (TypeError, ValueError):
        return f"{value}EUR"


def _sale_value(product: Dict[str, Any]) -> Optional[str]:
    """Sale price with currency when product is on sale. e.g. 54.99EUR."""
    variants = product.get("variants") or []
    if not variants:
        return None
    v = variants[0]
    price = v.get("price")
    compare = v.get("compare_at_price")
    if not price:
        return None
    try:
        if compare and float(price) < float(compare):
            return f"{float(price):.2f}EUR"
        return None
    except (TypeError, ValueError):
        return f"{price}EUR"


def _product_url(handle: str) -> str:
    return f"{BASE_URL}/en/products/{handle}"


def _image_urls(product: Dict[str, Any]) -> tuple:
    """Return (first_image_url, additional_images_str). additional_images: 'url1 , url2'."""
    images = product.get("images") or []
    urls = [img.get("src") for img in images if img.get("src")]
    urls = [u for u in urls if u]
    if not urls:
        return "", ""
    main = urls[0]
    rest = urls[1:]
    additional = " , ".join(rest) if rest else ""
    return main, additional


def _sizes(product: Dict[str, Any]) -> Optional[str]:
    """Size option values as comma-separated."""
    options = product.get("options") or []
    for opt in options:
        name = (opt.get("name") or "").lower()
        if name in ("size", "größe", "grösse"):
            vals = opt.get("values") or []
            return ", ".join(str(v) for v in vals)
    return None


def fetch_collection_page(page: int) -> List[Dict[str, Any]]:
    """Fetch one page of products from collection JSON. Returns list of product dicts."""
    url = f"{JSON_BASE}/{COLLECTION_HANDLE}{PRODUCTS_JSON_PATH}"
    params = {"page": page, "limit": LIMIT_PER_PAGE}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            products = data.get("products") or []
            return products
        except Exception as e:
            logger.warning(f"Page {page} attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    return []


def stream_all_products() -> Iterator[Dict[str, Any]]:
    """Yield product dicts from all collection pages until a page returns no products."""
    page = 1
    while True:
        products = fetch_collection_page(page)
        if not products:
            logger.info(f"Page {page} returned 0 products, stopping.")
            break
        logger.info(f"Page {page}: got {len(products)} products")
        for p in products:
            yield p
        page += 1
        time.sleep(REQUEST_DELAY)


def product_to_record(product: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Shopify product JSON to our internal record (no embeddings)."""
    handle = product.get("handle") or ""
    product_url = _product_url(handle)
    image_url, additional_images = _image_urls(product)
    description = _strip_html(product.get("body_html") or "")
    category = _normalize_category(product.get("product_type"))
    gender = _infer_gender(product)
    price = _price_string(product)
    sale = _sale_value(product)
    size = _sizes(product)
    tags = product.get("tags") or []

    metadata = {
        "vendor": product.get("vendor"),
        "product_type": product.get("product_type"),
        "tags": tags,
        "variants_count": len(product.get("variants") or []),
        "options": product.get("options"),
    }

    return {
        "product_url": product_url,
        "image_url": image_url,
        "additional_images": additional_images,
        "title": (product.get("title") or "").strip(),
        "description": description or None,
        "category": category,
        "gender": gender,
        "price": price or None,
        "sale": sale,
        "size": size,
        "metadata": metadata,
        "tags": tags,
    }
