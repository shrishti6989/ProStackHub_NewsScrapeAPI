# ProStackHub_NewsScrapeAPI

A config-driven news scraper with SQLite deduplication and a REST API, built for the **ProStackHub Python Internship**.

## Features

- **Config-driven scraping**: add new sources by editing `sources.yaml` — no code changes
- **BeautifulSoup + requests** with rate-limiting, retries, and per-source error handling
- **SQLite persistence** with URL uniqueness enforcement (deduplication on re-scrape)
- **FastAPI REST API** with filtering, pagination, and sorting
- **APScheduler**: auto-scrapes every 6 hours; tracks run history
- **Graceful failure**: if one source breaks, the others keep going
- **Auto-generated docs** at `/docs` (Swagger UI)

## Sources Currently Configured

- Hacker News (HTML scraping)
- BBC News (RSS)
- The Verge (Atom feed)

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET  | `/` | API info |
| GET  | `/articles` | List articles with filters, pagination, sorting |
| POST | `/scrape` | Trigger a manual scrape |
| GET  | `/health` | Pipeline status, counts, scheduler info |
| GET  | `/docs` | Swagger UI |

### Query Parameters for `/articles`

- `source` — filter by source name (e.g. `bbc_news`)
- `search` — search in title, summary, or author
- `date_from` / `date_to` — ISO date range
- `limit` — 1–100 (default 20)
- `offset` — pagination offset
- `order_by` — `scraped_at` / `published_at` / `title` / `source`
- `order` — `asc` / `desc`

## Tech Stack

- Python 3.11+
- FastAPI + Uvicorn
- Requests + BeautifulSoup + lxml
- SQLite (built-in)
- APScheduler
- PyYAML

## Local Setup

    git clone https://github.com/shrishti6989/ProStackHub_NewsScrapeAPI.git
    cd ProStackHub_NewsScrapeAPI
    pip install -r requirements.txt

## Running Locally

    uvicorn newsscrape.api.main:app --reload --port 8000

Then visit:
- API root: http://localhost:8000/
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Articles: http://localhost:8000/articles

## Adding a New Source

Edit `newsscrape/config/sources.yaml`, append a new block:

    - name: my_source
      url: "https://example.com/news"
      item_selector: "div.article"
      title_selector: "h2"
      link_selector: "a"
      author_selector: "span.author"
      date_selector: "time"
      summary_selector: "p.summary"
      base_url: "https://example.com"

Restart the app. That's it — no Python changes needed.

## Deployment

Deployed on **Render** (free tier):

- Config: `render.yaml`
- Start command: `uvicorn newsscrape.api.main:app --host 0.0.0.0 --port $PORT`
- Live URL: *[add after deploying]*

## Project Structure

    newsscrape/
      config/
        loader.py         YAML config loader
        sources.yaml      source definitions
      core/
        models.py         Article dataclass
        database.py       SQLite wrapper with dedup
        scraper.py        BeautifulSoup scraping engine
      api/
        main.py           FastAPI app
        routes.py         endpoint handlers
      scheduler/
        jobs.py           APScheduler setup
    tests/
    render.yaml
    requirements.txt

## Author

Sudhir Pandey — ProStackHub Python Internship, 2026
