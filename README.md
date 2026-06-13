# Cargro Lead Generation MVP

This project is a Python and Streamlit MVP for finding and reviewing public-company logistics leads for Cargro Solutions / LuxeLine Detailing. It focuses on companies that sell bulky or heavy e-commerce products and may need last-mile delivery, return pickups, overflow transport, scheduled delivery, Sprinter routes, bakwagen routes, bakwagen with laadklep routes, or future e-fulfillment support.

The tool prepares leads for manual review. It does not send automated outreach emails.

## What it does

- Discovers candidate company URLs from a legal search API when configured.
- Provides a `Discover Websites` tab for creating `candidate_urls.csv` and `candidate_urls.xlsx`.
- Supports manual URL mode when no search API key is available.
- Crawls a small number of public pages per domain.
- Extracts company-level information, generic contact details, source URLs, and evidence snippets.
- Scores each lead from 0 to 100.
- Classifies opportunity types such as last-mile bulky delivery, overflow transport, return pickup service, scheduled delivery, two-man delivery, bakwagen with laadklep route, Sprinter route, e-fulfillment pilot, and storage + delivery.
- Exports CSV and XLSX files.
- Generates Dutch outreach drafts for manual review only.

## Install

Use Python 3.11 or newer.

```powershell
cd leadgen_cargro
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Run the Streamlit app

```powershell
cd leadgen_cargro
streamlit run app.py
```

The app opens in your browser. Upload CSV files or edit the starter files in `data/input`.

## Manual URL mode

Manual URL mode works without any API key.

1. Open `data/input/manual_urls.csv`.
2. Add rows with `url` and optional `category`.
3. Start the Streamlit app.
4. Click `Run crawling and scoring`.

Example:

```csv
url,category
https://example-webshop.nl,garden furniture
```

## Website Discovery

Use the `Discover Websites` tab when you want the app to find candidate company websites before running lead analysis.

The discovery workflow:

1. Upload `search_keywords.csv` with `keyword`, `category`, `country`, `language`, and `max_results`.
2. Select a provider: `brave`, `bing`, or `serpapi`.
3. Enter the provider API key if it is not already configured on the server.
4. Click `Find candidate websites`.
4. Review the discovered URLs, confidence scores, and discovery reasons.
5. Download `candidate_urls.csv` or `candidate_urls.xlsx`.
6. Use `Send candidates to analysis` or upload the candidate CSV in the normal lead analysis workflow.

The discovery feature only collects public company-level website URLs. It filters out social media, marketplace-only pages, documents, and obvious blog/news results. It does not scrape Google search pages directly and does not collect personal data.

If no API key is configured, the app shows:

```text
No search provider configured. You can still use manual URL mode or upload a candidate URL CSV.
```

### Where do these websites come from?

The system discovers potential company websites using search keywords related to bulky e-commerce categories such as garden furniture, fitness equipment, beds, furniture, and home/garden products. If a search API is configured, it collects public search results, filters out irrelevant pages, removes duplicates, and creates a clean candidate website list. These websites are then analyzed separately for logistics signals such as delivery, returns, webshop activity, heavy products, and contact details.

You can also build a candidate list manually from safe public sources, such as webshop directories, keurmerk member pages, or manually copied search results.

## Search API mode

The app does not scrape Google search result pages directly. It only uses supported search APIs.

1. Copy `.env.example` to `.env`.
2. Set `SEARCH_PROVIDER` to `brave`, `bing`, or `serpapi`.
3. Add the matching API key, or enter it in the website discovery tab at runtime.
4. Add keywords in `data/input/search_keywords.csv`.

Supported environment variables:

- `BRAVE_SEARCH_API_KEY`
- `BING_SEARCH_API_KEY`
- `SERPAPI_API_KEY`
- `SERPAPI_KEY`

## Input files

`data/input/search_keywords.csv`

```csv
keyword,category,country,language,max_results
tuinmeubelen webshop bezorgen Nederland,garden furniture,Netherlands,nl,20
```

`data/input/manual_urls.csv`

```csv
url,category
https://example-webshop.nl,garden furniture
```

`data/input/candidate_urls_example.csv`

```csv
url,category,source
https://example-webshop.nl,garden furniture,manual
```

## Exported files

After a run, exports are saved in `data/output`:

- `candidate_urls.csv`
- `candidate_urls.xlsx`
- `leads.csv`
- `leads.xlsx`
- `crawl_log.csv`

Candidate URL exports include URL, category, keyword, title, snippet, domain, source provider, rank, country, language, discovery reason, confidence score, status, and notes.

Export columns include company name, website, category, contact URLs, opportunity type, lead score, priority, signals, evidence snippets, source URLs, status, and notes.

## Legal and ethical rules

- Collect only public business/company information.
- Do not scrape private personal data.
- Do not scrape LinkedIn or social media personal profiles.
- Do not scrape Google search result pages directly.
- Do not bypass logins, captchas, paywalls, robots.txt, or anti-bot systems.
- Respect robots.txt where applicable.
- Use polite rate limits.
- Store source URLs and evidence snippets for every lead.
- Prefer generic company emails like `info@`, `sales@`, `klantenservice@`, `service@`, or `logistiek@`.
- Do not send automated outreach emails. Review every lead and draft manually.

## Review workflow

1. Run discovery and crawling.
2. Filter by category, score, and opportunity type.
3. Open source URLs and evidence snippets.
4. Edit `status` and `notes`.
5. Review the Dutch outreach draft manually.
6. Export CSV or XLSX for your working list.

For website discovery, first export or send `candidate_urls.csv`, then run the normal lead analysis on the candidate URLs.

## Tests

```powershell
cd leadgen_cargro
pytest
```

The included tests cover scoring and extraction basics.
