# More Money More Love – Scraper

Scrapes all products from [moremoneymorelove.de](https://moremoneymorelove.de), generates 768‑dim image and text embeddings (SigLIP), and upserts into a Supabase `products` table.

## Setup

1. **Clone:**
   ```bash
   git clone https://github.com/adrianpawlas/scraper-moremoneymorelove.git
   cd scraper-moremoneymorelove
   ```

2. **Create virtualenv and install dependencies:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   - Copy `.env.example` to `.env`
   - Set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (or `SUPABASE_KEY`) in `.env`

## Run

- **Full run (scrape all pages, embed, upsert):**
  ```bash
  python run_scraper.py
  ```
  or
  ```bash
  python main.py
  ```

- **Dry run (no DB writes):**
  ```bash
  python run_scraper.py --dry-run
  ```

- **Limit number of products (e.g. test with 5):**
  ```bash
  python run_scraper.py --limit 5
  ```

## Automation

### Manual

Run whenever you want:
```bash
python run_scraper.py
```

### Daily at midnight (Windows Task Scheduler)

1. Open Task Scheduler → Create Basic Task.
2. Trigger: Daily, repeat at midnight.
3. Action: Start a program → Program: `run_daily.bat`, Start in: project folder.

Or run `run_daily.bat` from a scheduled task that uses the project directory as working directory.

### Daily via GitHub Actions

1. Push the repo to GitHub.
2. In repo **Settings → Secrets and variables → Actions**, add:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
3. The workflow `.github/workflows/daily-scrape.yml` runs at **00:00 UTC** every day.
4. You can also run it manually: **Actions → Daily scrape → Run workflow**.

## Data

- **Source:** Shopify collection `https://moremoneymorelove.de/en/collections/shop-all` (paginated JSON until empty).
- **Embeddings:** `google/siglip-base-patch16-384` (768‑dim) for both image and text (product info).
- **Table:** Supabase `public.products`; upsert key `(source, product_url)` with `source = 'scraper'`, `brand = 'Moremoney Morelove'`.
