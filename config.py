"""Configuration for More Money More Love scraper."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project directory so scheduled/midnight runs find it regardless of cwd
_project_dir = Path(__file__).resolve().parent
load_dotenv(_project_dir / ".env", override=False)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://yqawmzggcgpeyaaynrjk.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY", ""))

# Store
BASE_URL = "https://moremoneymorelove.de"
COLLECTION_URL = "https://moremoneymorelove.de/en/collections/shop-all"
PRODUCTS_JSON_PATH = "/products.json"
LIMIT_PER_PAGE = 50

# Fixed values for this source
SOURCE = "scraper"
BRAND = "Moremoney Morelove"
SECOND_HAND = False
COUNTRY = None  # Always null for this source
CURRENCY_DISPLAY = "EUR"  # Store shows EUR

# Embeddings
EMBEDDING_MODEL = "google/siglip-base-patch16-384"
EMBEDDING_DIM = 768

# Requests
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1.0
MAX_RETRIES = 3
