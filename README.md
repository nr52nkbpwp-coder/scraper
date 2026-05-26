# GrowDB — Growtopia Item Database

A fast, clean web interface for searching Growtopia item data — powered by a Python scraper and deployed on Vercel.

![preview](https://img.shields.io/badge/stack-HTML%20%2B%20Python%20%2B%20Vercel-4ade80?style=flat-square)

## Features

- 🔍 Live search with autocomplete suggestions
- 📦 Full item data: rarity, hardness, sprites, grow time, recipes & more
- ⌨️ Keyboard-navigable (arrow keys + enter)
- 🔗 Shareable URLs via `?item=Dirt`
- 🐍 Python scraper as Vercel serverless functions

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Vanilla HTML/CSS/JS (no framework, zero deps) |
| API | Python serverless functions (Vercel) |
| Scraper | `requests` + `BeautifulSoup4` |
| Host | Vercel (free tier) |

## Project Structure

```
growtopia-wiki-web/
├── api/
│   ├── scraper.py      # Core scraping logic
│   ├── search.py       # GET /api/search?q=<query>
│   └── item.py         # GET /api/item?name=<name>
├── public/
│   └── index.html      # Full frontend (single file)
├── requirements.txt    # Python deps for Vercel
├── vercel.json         # Routing config
└── README.md
```

## Deploy to Vercel

### Option A — Vercel CLI (recommended)

```bash
# 1. Clone & enter project
git clone https://github.com/YOUR_USERNAME/growtopia-wiki-web.git
cd growtopia-wiki-web

# 2. Install Vercel CLI
npm i -g vercel

# 3. Deploy (follow prompts)
vercel

# 4. Deploy to production
vercel --prod
```

### Option B — GitHub + Vercel Dashboard

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) → **Add New Project**
3. Import your GitHub repo
4. Leave all settings default → click **Deploy**
5. Done ✅

## Local Development

The frontend (`public/index.html`) calls `/api/search` and `/api/item`.

For local testing with Vercel dev server:

```bash
npm i -g vercel
pip install -r requirements.txt
vercel dev
# → open http://localhost:3000
```

Or open `public/index.html` directly and set `API_BASE` at the top of the script to your deployed Vercel URL:

```js
const API_BASE = 'https://your-project.vercel.app';
```

## API Reference

### `GET /api/search?q=<query>`
Returns a list of matching item titles.

```json
{
  "results": [
    { "Title": "Dirt", "Url": "https://growtopia.fandom.com/wiki/Dirt" }
  ]
}
```

### `GET /api/item?name=<name>`
Returns full item data.

```json
{
  "Title": "Dirt",
  "Rarity": 1,
  "Description": "...",
  "Hardness": { "Fist": 3, "Pickaxe": 0, "Restore": 8 },
  "Sprite": { "Item": "...", "Tree": "...", "Seed": "..." },
  ...
}
```

## License

MIT
