# Automated SEO Content Website (Jekyll + GitHub Actions)

This project is a fully automated, production-ready SEO site that publishes one new article per day using free tools and APIs. It is optimized for GitHub Pages or Netlify hosting (free tiers), and uses a daily GitHub Actions cron job to discover keywords, generate content, fetch an image, and publish a new post.

## Features
- Daily automated post generation (GitHub Actions cron)
- Keyword discovery via Google Trends (pytrends) with fallbacks
- Content generation via:
  - Template-based SEO copy (default, reliable, free)
  - Optional OpenAI API (set `OPENAI_API_KEY`)
  - Optional Hugging Face Inference API (set `HUGGINGFACE_API_TOKEN`)
- Images from Unsplash API (set `UNSPLASH_ACCESS_KEY`), with fallback to Source Unsplash (no key)
- Jekyll site with:
  - Clean, responsive, fast theme
  - Schema.org JSON-LD, OpenGraph, Twitter cards
  - `jekyll-feed` and `jekyll-sitemap`
  - Sitemap and RSS auto-generated
  - 90+ Lighthouse targets for Performance/SEO/Best Practices
- Configurable niche and site metadata in `_config.yml`
- Google Analytics and Search Console verification support

## Quick Start

1. Fork/clone this repo, then set your niche and site details in `_config.yml` under `automation:` and top-level metadata.
2. Push to GitHub.
3. In your GitHub repo settings:
   - Pages: set the source to `main` branch (root). GitHub Pages will build the Jekyll site automatically.
   - Secrets and variables → Actions → New repository secrets:
     - Optional: `OPENAI_API_KEY`
     - Optional: `HUGGINGFACE_API_TOKEN`
     - Optional: `UNSPLASH_ACCESS_KEY` (or `PEXELS_API_KEY` if you adapt the script)
4. Enable Actions. The workflow `.github/workflows/daily.yml` will run daily and on manual trigger.
5. First post: A sample post is included in `_posts/`. On next cron tick, a new post will be generated.

## Configuration

Edit `_config.yml`:
- `title`, `description`, `url`, `baseurl`, `language`, `author`
- `google_analytics_id` for GA4 (optional)
- `google_site_verification` for Search Console (optional)
- `permalink: /:title/` for clean URLs
- `automation:` block controls:
  - `niche`: primary niche, e.g., "AI tools"
  - `country`: Google Trends region (e.g., `united_states`)
  - `language`: ISO code used in meta (e.g., `en`)
  - `min_word_count`, `max_word_count`: content length target
  - `generation_backend`: `template` (default), `openai`, or `hf_api`
  - `internal_links_max`: number of internal links to inject
  - `backup_keywords_file`: path to fallback keyword list

## How Automation Works

- GitHub Actions runs `scripts/generate_daily_post.py` daily.
- The script:
  1. Reads `_config.yml` settings.
  2. Finds candidate keywords via `pytrends` (suggestions and related queries). Falls back to `backup_keywords.txt`.
  3. Selects an unused keyword (tracked in `.automation/used_keywords.json`).
  4. Generates SEO-structured content using either template logic (default), OpenAI, or Hugging Face Inference API.
  5. Fetches an image from Unsplash (API key) or falls back to `source.unsplash.com` hotlink.
  6. Writes a new Markdown post under `_posts/YYYY-MM-DD-slug.md` with front matter.
  7. Workflow commits and pushes changes.

## Local Development

- Ruby/Jekyll (optional for local preview):
  - Install Ruby and Bundler
  - `bundle install`
  - `bundle exec jekyll serve` → http://localhost:4000

- Python (for manual runs):
  - `pip install -r scripts/requirements.txt`
  - `python scripts/generate_daily_post.py`

## Deployment

- GitHub Pages: Push to `main`. Pages builds Jekyll automatically.
- Netlify: Point Netlify to this repo and set build command `jekyll build` and publish directory `_site`. Add environment variable `JEKYLL_ENV=production`.

## Secrets

Set in GitHub → Settings → Secrets and variables → Actions → New repository secret:
- `OPENAI_API_KEY` (optional)
- `HUGGINGFACE_API_TOKEN` (optional)
- `UNSPLASH_ACCESS_KEY` (optional)

The workflow uses `GITHUB_TOKEN` automatically to commit changes.

## Notes on Free Tiers
- `pytrends` uses publicly accessible Google Trends endpoints
- Unsplash Source fallback uses hotlinked images; prefer API + local download with attribution for production consistency
- Hugging Face Inference API has free-rate limits and cold starts; default template mode avoids external calls

## License
MIT
