"""
More Money More Love scraper: fetch all products, generate embeddings, upsert to Supabase.
Smart sync: new products added, existing kept as-is, products no longer in catalog removed.
Run: python main.py [--dry-run] [--limit N]
"""
import argparse
import logging
import sys
from config import SUPABASE_KEY

from scraper import stream_all_products, product_to_record
from embeddings import EmbeddingGenerator
from database import prepare_row, upsert_products, remove_stale_products

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run(dry_run: bool = False, limit: int | None = None):
    if not SUPABASE_KEY and not dry_run:
        logger.error("Set SUPABASE_SERVICE_KEY or SUPABASE_KEY in .env for database upload.")
        sys.exit(1)

    logger.info("Starting scraper (dry_run=%s, limit=%s)", dry_run, limit)
    gen = EmbeddingGenerator()

    # 1) Collect all products and build rows (so we can batch upsert and know current set for sync)
    rows: list = []
    total = 0
    for raw in stream_all_products():
        if limit is not None and total >= limit:
            logger.info("Reached limit %s", limit)
            break
        total += 1
        record = product_to_record(raw)
        product_url = record["product_url"]
        title = record.get("title") or product_url

        if not record.get("image_url"):
            logger.warning("Skip (no image): %s", title[:60])
            continue

        logger.info("Processing %s", title[:60])
        image_emb = gen.image_embedding(record["image_url"])
        if image_emb is None:
            logger.warning("No image embedding for %s", title[:60])
        record["brand"] = "Moremoney Morelove"
        info_emb = gen.info_embedding_from_record(record)
        if info_emb is None:
            logger.warning("No info embedding for %s", title[:60])

        row = prepare_row(record, image_embedding=image_emb, info_embedding=info_emb)
        rows.append(row)

    if dry_run:
        logger.info("Dry run: would upsert %s products (no DB write, no stale removal)", len(rows))
        return

    if not rows:
        logger.info("No products to upsert.")
        removed = remove_stale_products(set())
        if removed:
            logger.info("Removed %s stale product(s) no longer in catalog.", removed)
        return

    # 2) Batch upsert (PostgREST HTTP, reliable for scheduled runs)
    if not upsert_products(rows):
        logger.error("Upsert failed; skipping stale-removal to avoid data loss.")
        sys.exit(1)
    logger.info("Upserted %s products.", len(rows))

    # 3) Smart sync: remove products for this source that are no longer in the catalog
    current_ids = {r["id"] for r in rows}
    removed = remove_stale_products(current_ids)
    if removed:
        logger.info("Removed %s stale product(s) no longer in catalog.", removed)

    logger.info("Done. Processed=%s, upserted=%s, stale_removed=%s", total, len(rows), removed)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="More Money More Love → Supabase")
    ap.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    ap.add_argument("--limit", type=int, default=None, help="Max products to process")
    args = ap.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)
