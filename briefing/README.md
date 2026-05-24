# Daily Briefing Printer

On-demand single-page briefing for an iPhone NFC tag. You tap the tag, your
phone fetches a freshly-rendered PDF from a tiny cloud service, and the
iOS Print action AirPrints it to the home printer. Nothing always-on at home.

```
[NFC tag] → [iOS Shortcut]
              ├─ GET /briefing  → service renders PDF
              └─ Print action   → iPhone AirPrints to LaserJet M201dw
```

## What's on the page

- Today's date (long format)
- Weather for Lindon, UT (current temp, high/low, precip chance, sunrise/sunset, conditions)
- Today's Google Calendar events (primary calendar)
- Top 10 most urgent tasks from the DCJ Notion task board:
  1. Past-due first (oldest first)
  2. Then due today
  3. Then sorted by priority (Ultra High → High → Medium → Low) and due date

Three style options ship in this repo. Pick one by setting `STYLE=<name>` or
hitting `/briefing?style=<name>`:

- `newspaper` — editorial serif, masthead, two-column layout
- `dashboard` — data-dense sans, timeline visualization, colored priority dots
- `minimalist` — light sans, generous whitespace, single-column flow

## Repo layout

```
briefing/
  app/
    main.py              FastAPI app (endpoints: /briefing, /preview/{style}, /healthz)
    config.py            Settings via env vars / .env
    models.py            Briefing, CalendarEvent, Task, Weather
    sources/
      calendar.py        Google Calendar fetcher (stub — needs OAuth wiring)
      tasks.py           Notion task board fetcher (stub — needs token wiring)
      weather.py         Open-Meteo fetcher (no auth needed)
    render/
      pdf.py             Jinja2 + WeasyPrint → PDF bytes
      sample.py          Fake briefing data for previews
    templates/
      newspaper.html
      dashboard.html
      minimalist.html
  scripts/
    generate_samples.py  Render the three styles to samples/*.pdf
  samples/               Committed sample PDFs for review
  Dockerfile
  requirements.txt
```

## Local dev

```bash
cd briefing
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Render sample PDFs for all three styles
python scripts/generate_samples.py
open samples/

# Or run the service
uvicorn app.main:app --reload --port 8080
# then open http://localhost:8080/preview/newspaper
```

WeasyPrint needs Pango/Cairo system libs. On macOS: `brew install pango`.
On Debian/Ubuntu: see the Dockerfile's `apt-get` line.

## Deploying to Google Cloud Run

```bash
# One-time
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# Deploy from source (Cloud Build handles container build)
cd briefing
gcloud run deploy daily-briefing \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --concurrency 1 \
  --max-instances 2 \
  --set-env-vars STYLE=newspaper,WEATHER_LAT=40.3417,WEATHER_LON=-111.7186,WEATHER_LOCATION_LABEL="Lindon, UT",TIMEZONE="America/Denver"
```

After it deploys you'll get a URL like
`https://daily-briefing-xxxxx-uc.a.run.app`. The endpoint to hit from the
Shortcut is `<url>/briefing` (with `?secret=...` once you set
`BRIEFING_SHARED_SECRET`).

Cost: Cloud Run free tier (2M requests/month, 360k GB-seconds) covers ~30
invocations/month forever. Cold start ~2-3 seconds with WeasyPrint loaded.

## iOS Shortcut setup

1. iPhone → **Shortcuts** app → **+** to create a new shortcut.
2. Add **Get Contents of URL**.
   - URL: `https://<your-cloud-run-url>/briefing?secret=<your-secret>`
   - Method: GET
   - (Toggle "Use Headers" off unless you want to set custom ones.)
3. Add **Print**.
   - Input: the previous step's "Contents of URL".
   - Tap "Show Compose Sheet" → **OFF** (so it prints without confirmation).
4. Tap **Done**. Run once to test — iOS will ask you to pick the printer
   the first time; choose the LaserJet M201dw. Subsequent runs print silently.

To bind it to the NFC tag:
1. iPhone → **Shortcuts** → **Automation** tab → **+** → **NFC**.
2. Scan your NFC tag.
3. Action: **Run Shortcut** → pick the briefing shortcut.
4. Toggle **Ask Before Running** to **OFF**.

Now: tap phone to tag → PDF prints. Phone must be on your home Wi-Fi
(same network as the M201dw) at tap-time, which it will be if the tag is
at home.

## Required credentials (post-style-selection)

Set these as Cloud Run env vars or in a local `.env`:

- `BRIEFING_SHARED_SECRET` — any random string; included as `?secret=` in
  the Shortcut URL so randos can't print to your printer by guessing the URL.
- `GOOGLE_OAUTH_CLIENT_SECRETS_PATH` + `GOOGLE_OAUTH_TOKEN_PATH` — for
  Google Calendar. Use an OAuth installed-app flow: create a Desktop client
  in Google Cloud Console, run a local one-time auth script to get a refresh
  token, mount the resulting token file into the container.
- `NOTION_TOKEN` — internal integration token from Notion. Create at
  https://www.notion.so/my-integrations, then share the DCJ Task Board with
  it from the database's "•••" → "Connections".
- `NOTION_TASK_DATABASE_ID` — the 32-char ID from the database URL.
- `NOTION_ASSIGNEE_USER_ID` — your Notion user ID, so the query filters to
  your tasks only.

## Roadmap

- [x] Three style templates with sample data
- [x] Sample PDF generation for style selection
- [ ] Pick a style (the only thing waiting on you)
- [ ] Wire Google Calendar source
- [ ] Wire Notion task source
- [ ] Wire Open-Meteo into `/briefing` (currently uses sample weather)
- [ ] Deploy to Cloud Run
- [ ] Build iOS Shortcut and bind to NFC tag
