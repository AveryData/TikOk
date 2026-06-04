# A Record of Our Day

A single-page daily PDF rendered on demand by a tiny cloud service. Tap an
NFC tag at home → iOS Shortcut fetches the PDF → phone AirPrints it to the
home laser printer. **Zero always-on hardware at home.**

```
[NFC tag at home] → [iOS Shortcut]
                       ├─ GET <cloud-run>/briefing?secret=…  → returns PDF
                       └─ Print action                       → AirPrint to M201dw
```

## What's on the page

Nine personas, one per day of the week (overridable via `?style=…`):

| Day | Persona | Vibe |
|---|---|---|
| Mon | `terminal` | $ ./record-of-our-day, ASCII bars, [OVERDUE] tags |
| Tue | `spider-man` | The Daily Bugle, halftone, POW! badges |
| Wed | `darwin` | Field Notes & Observations, Roman numerals, sepia |
| Thu | `pokemon` | Trainer Card, Pokédex IDs, KO tags |
| Fri | `stranger-things` | Hawkins Daily Bulletin, FROM THE UPSIDE DOWN |
| Sat | `newspaper` | A Record of Our Day classic |
| Sun | `scripture` | "And it came to pass…", verse markers |

Three older designs (`dashboard`, `minimalist`, `newspaper`) are still available.

Each persona renders the same data:
- Today's date + greeting + weather (Lindon, UT)
- SPY price + 7d / 30d / YTD % change
- Countdown(s) to upcoming events (e.g. Bear Lake Half Ironman)
- Year-progress bar with month markers
- Today's Google Calendar events (sample data until wired)
- Top 10 Notion tasks (sample data until wired)
- Upcoming 7 days
- Come Follow Me reference (placeholder — see scraper script)
- Prayer-writing box
- Quote of the day + joke of the day (curated rotating lists)

## Local dev

```bash
cd briefing
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Regenerate all 9 sample PDFs into samples/
python scripts/generate_samples.py

# Run the live service
uvicorn app.main:app --reload --port 8080
# preview (sample data only):
#   open http://localhost:8080/preview/scripture
# full briefing (tries real weather + ticker):
#   open http://localhost:8080/briefing
#   open "http://localhost:8080/briefing?style=spider-man"
```

WeasyPrint needs Pango/Cairo system libs. macOS: `brew install pango`.
Linux: see the Dockerfile.

## Deploy to Google Cloud Run

### One-time setup
You'll need:
- A Google account (free tier covers this forever — Cloud Run gives 2M
  requests/month and you'll make ~30)
- The `gcloud` CLI: https://cloud.google.com/sdk/docs/install
- ~10 minutes

```bash
# Sign in and pick a project (create one if you don't have one).
gcloud auth login
gcloud projects create record-of-our-day --name="A Record of Our Day" || true
gcloud config set project record-of-our-day

# Enable the APIs we need.
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

### Pick a secret
Generate a random string that gates the endpoint so randos can't trigger
prints. Anything ~24 chars is fine:

```bash
SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(18))")
echo "Your secret: $SECRET"   # save this — you'll paste it into the iOS Shortcut
```

### Deploy
From the `briefing/` directory:

```bash
gcloud run deploy daily-briefing \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 1 \
  --max-instances 2 \
  --set-env-vars "^|^TIMEZONE=America/Denver|WEATHER_LAT=40.3417|WEATHER_LON=-111.7186|WEATHER_LOCATION_LABEL=Lindon, UT|TICKER_SYMBOL=SPY|COUNTDOWNS=Bear Lake Brawl Half Ironman@2026-09-19|BRIEFING_SHARED_SECRET=$SECRET"
```

> The `^|^` prefix tells gcloud to split env vars on `|` instead of the
> default `,`. We need it because `WEATHER_LOCATION_LABEL` and `COUNTDOWNS`
> can contain commas of their own.

First deploy takes ~3-5 minutes (Cloud Build builds the container from the
Dockerfile). Subsequent deploys are faster.

When it's done, you'll see a URL like:
```
https://daily-briefing-xxxxxxxxxx-uc.a.run.app
```

### Verify
```bash
URL=$(gcloud run services describe daily-briefing --region us-central1 --format='value(status.url)')
curl -sI "$URL/healthz"                                    # → HTTP/2 200
curl -s -o /tmp/today.pdf "$URL/briefing?secret=$SECRET"   # PDF file
open /tmp/today.pdf                                        # see real weather + SPY
```

## iOS Shortcut

1. Phone → **Shortcuts** app → **+** → name it "Print Today".
2. **Get Contents of URL**
   - URL: `<your-cloud-run-url>/briefing?secret=<your-secret>`
   - Method: GET
3. **Print**
   - Input: "Contents of URL" from step 2
   - Tap "Show Compose Sheet" → **OFF** (so it prints silently)
4. Run once to test — iOS will ask which printer the first time; pick the
   M201dw. From then on it prints with no taps.

Bind to the NFC tag:
1. Shortcuts → **Automation** tab → **+** → **NFC**
2. Scan the tag
3. Action: **Run Shortcut** → "Print Today"
4. **Ask Before Running** → OFF

Now: tap phone to tag → PDF prints. Phone must be on home Wi-Fi at tap
time (same network as the printer); since the tag's at home, this is
always true.

## Health Auto Export (Apple Health → briefing)

HAE pushes a JSON blob to `/health?secret=…` each morning; the service
parses it into a snapshot, writes it to a GCS bucket, and the next
`/briefing` request reads the latest snapshot.

### 1. Make the bucket
```bash
PROJECT=$(gcloud config get-value project)
gcloud storage buckets create gs://record-of-our-day-health \
  --location=us-central1 --uniform-bucket-level-access

# Let Cloud Run's default service account read/write the bucket.
PROJ_NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
gcloud storage buckets add-iam-policy-binding gs://record-of-our-day-health \
  --member="serviceAccount:${PROJ_NUM}-compute@developer.gserviceaccount.com" \
  --role=roles/storage.objectAdmin
```

### 2. Point the service at it
```bash
gcloud run services update daily-briefing --region us-central1 \
  --update-env-vars HEALTH_BUCKET=record-of-our-day-health
```

### 3. Configure the HAE remote
In **Health Auto Export → Automations → REST API**:

| Field | Value |
|---|---|
| URL | `https://daily-briefing-…run.app/health?secret=<BRIEFING_SHARED_SECRET>` |
| Method | POST |
| Format | JSON, **Aggregated** (not raw samples) |
| Aggregation | Daily |
| Range | Last 7 days |
| Schedule | Daily, ~5:00 am (before the print) |

Check these metrics:
- Steps · Active Energy · Resting Heart Rate · Heart Rate Variability
- Weight · VO2 Max · Sleep Analysis
- Workouts (toggle the "Include Workouts" switch)

### 4. Verify
After HAE runs once:
```bash
URL=$(gcloud run services describe daily-briefing --region us-central1 --format='value(status.url)')
curl -s "$URL/briefing?secret=$SECRET&fmt=html" | grep -i steps   # should reflect real data
gcloud storage ls gs://record-of-our-day-health/health/snapshots/  # one file per day
```

If a push fails the briefing keeps rendering — stale snapshots older
than `HEALTH_MAX_AGE_HOURS` (default 36) are dropped silently so the
page never shows numbers from a broken sync.

## Configure later

Set or update env vars without rebuilding:
```bash
gcloud run services update daily-briefing --region us-central1 \
  --update-env-vars "STYLE=newspaper"   # pin a single style instead of day rotation
```

All env vars (`briefing/app/config.py`):
| Var | Default | Purpose |
|---|---|---|
| `STYLE` | unset | Pin a single style; overrides day-of-week rotation |
| `STYLE_MONDAY` … `STYLE_SUNDAY` | terminal/spider-man/darwin/pokemon/stranger-things/newspaper/scripture | Per-day persona |
| `TIMEZONE` | `America/Denver` | Used for "today" and weather |
| `WEATHER_LAT` / `WEATHER_LON` | Lindon coords | Open-Meteo lookup |
| `WEATHER_LOCATION_LABEL` | `Lindon, UT` | Display name on the page |
| `TICKER_SYMBOL` | `SPY` | Yahoo Finance symbol (set empty to hide) |
| `COUNTDOWNS` | Bear Lake | Comma-separated `"Label@YYYY-MM-DD"` entries |
| `BRIEFING_SHARED_SECRET` | unset | Gate the endpoint; required if set |
| `HEALTH_BUCKET` | unset | GCS bucket name for Health Auto Export snapshots |
| `HEALTH_MAX_AGE_HOURS` | `36` | Drop the snapshot if HAE hasn't pushed within this window |
| `GOOGLE_OAUTH_*` / `NOTION_*` | unset | For wiring real calendar + tasks (next step) |

## Roadmap

- [x] Nine persona templates fitting one Letter page each
- [x] Real weather (Open-Meteo) + SPY (Yahoo Finance), no auth needed
- [x] Day-of-week persona rotation with `?style=` override
- [x] Day-of-rendering timezone-aware
- [x] Graceful fallback to sample data when a source fetch fails
- [ ] Wire Google Calendar (today's events + upcoming 7 days)
- [ ] Wire Notion DCJ Task Board (top 10 by urgency)
- [x] Health Auto Export receiver + GCS storage (template render pending)
- [ ] Populate `come_follow_me_2026.json` (run `scripts/scrape_come_follow_me.py` locally)
- [ ] Deploy to Cloud Run
- [ ] Build iOS Shortcut + program NFC tag
