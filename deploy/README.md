# Deploying the live demo

The public site is the same FastAPI app as on a laptop, run in a container with `PUBLIC_DEMO=1`. It needs
no GPU: Model Lab, Plato's Chair and What can I cut? replay results that were computed ahead of time. Live
scoring, transcription and picture generation call the Meta Model API, and `metalesionlab/web/guard.py`
caps what visitors can spend.

Nothing here deploys by itself. Going public is a deliberate step: the commands below create accounts,
upload files and start billing against the API key.

## What visitors can spend

| Route | Meta models | How it's limited on the live demo |
|---|---|---|
| `POST /api/sets` (Test Studio build) | Muse Image, SAM 3.1, Muse Spark | Up to 4 words, at most 2 pictures each (about $0.12 a build); 3 builds per visitor per day, 1 a minute |
| `POST /api/scenes` (description scene) | Muse Image, Muse Spark | 2 per visitor per day |
| `POST /api/assess/photo-test` (personal test from a photo) | Muse Spark, SAM 3.1, Muse Image | Off (`TIPPA_PUBLIC_PHOTO_TESTS=1` turns it on) |
| `POST /api/score/naming`, `/api/assess/naming` (spoken answer) | Muse Voice Transcribe, Muse Spark | 2.5 MB and 30 s per answer; 30 a minute and 150 a day per visitor |
| `POST /api/score/description`, `/api/score/fluency` | Muse Voice Transcribe, Muse Spark | 4 MB; 90 s (description) or 60 s (fluency); same counts |
| `POST /api/score/naming/text`, `/api/assess/rescore` (typed) | Muse Spark (meaning judge, second rater) | Same counts |
| `/api/ask...` (Ask the Lab agent) | Muse Spark | 4 a minute and 20 a day per visitor (`TIPPA_PUBLIC_ASK_PER_DAY`) |
| Any other POST, PUT, PATCH or DELETE under `/api/` | (unknown) | Treated as paid: 10 a minute and 100 a day per visitor |

Over all of these:
- **Daily cap.** All visitors together spend at most `TIPPA_PUBLIC_DAILY_USD` (default $2) per UTC day. The
  guard sums today's lines in the spend ledger and checks before every route and inside `MetaAPI` before
  every single call, so a background build or a multi-step agent stops at the cap too. Then the site shows
  "Today's live demo budget is used up" with links to the recorded Scorer demo, the challenge game and the
  Model Lab; everything that doesn't call the API keeps working.
- **Overall cap.** `MLL_BUDGET_USD` (default $10 in the container) caps this host's total spending.
- **Busy ceiling.** At most 60 paid requests a minute from everyone together.
- **Fails closed.** If the ledger can't be written, every API call is refused, so nothing is spent uncounted.

Free, with no API calls: every page, the replays (Model Lab, Plato's Chair, What can I cut?), the challenge
game with typed answers (cached meaning judgments), browsing sets, exports (cards PDF, norms CSV, ZIP), the
session report PDF and parallel forms.

**Kill switch:** set `TIPPA_PUBLIC_DAILY_USD=0` and restart. The site stays up with no API calls.

Visitors can edit only the sets they built (`TOT_PUBLIC=1`), so nobody can change the demo sets the
public test and the challenge use.

## 1. Build the bundle (every host)

`runs/` isn't in git. The bundle is the part of it the site reads (demo picture sets with only their
chosen pictures, lesion conditions, scenes, cached judgments, the layer-removal and bilingual results):

```bash
python scripts/build_site_bundle.py --stage dist/space
```

It writes `dist/site_data/` (about 100 MB with all 16 demo languages; `--sets 'demo_en' --sets 'demo_es'`
keeps fewer) and `dist/space/`, a folder ready to upload as a Hugging Face Space. It must end with
`passed: data-guard extensions and private patterns, no audio, no API key, ...`; if a check fails it
exits with an error and says which file. Don't deploy a bundle that failed.

Optional local check, with no API spending (the cap is 0):

```bash
docker build -t tippa-lingua dist/space
docker run --rm -p 7860:7860 -e TIPPA_PUBLIC_DAILY_USD=0 tippa-lingua   # open http://localhost:7860
```

## 2a. Hugging Face Spaces (recommended)

Free CPU hardware (2 vCPU, 16 GB) runs the app comfortably.

1. Log in to Hugging Face and create a Space at https://huggingface.co/new-space: a name such as
   `tippa-lingua`, license Apache-2.0, **SDK: Docker** (Blank template), hardware **CPU basic**, public.
2. In the Space, open **Settings → Variables and secrets** and add two **secrets** (never variables, and never
   in the Dockerfile or the repository):
   - `MODEL_API_KEY`: the Meta Model API key. A separate key for the demo is best, if dev.meta.ai offers one,
     so it can be revoked without touching the laptop's work.
   - `TOT_RECEIPT_KEY`: any long random string (`python -c "import secrets; print(secrets.token_hex(32))"`),
     so public-test results stay verifiable across restarts.

   Optional **variables**: `TIPPA_PUBLIC_DAILY_USD` (default 2), `MLL_BUDGET_USD` (default 10),
   `TIPPA_PUBLIC_BUILD_WORDS` (default 4; 0 turns Test Studio builds off).
3. Upload the staged folder (the CLI comes with `pip install -U huggingface_hub`; the login needs a token with
   write access):

   ```bash
   hf auth login
   hf upload <user>/tippa-lingua dist/space . --repo-type=space --commit-message "Tippa Lingua live demo"
   ```

   (Older versions of the CLI: `huggingface-cli upload ...` with the same arguments.)
4. The Space builds the image (about 5 minutes; watch **Logs**). When it says Running, the site is at
   `https://<user>-tippa-lingua.hf.space`.
5. Check the guard:

   ```bash
   curl -s "https://<user>-tippa-lingua.hf.space/api/guard?debug=1"
   curl -s https://ifconfig.me
   ```

   `public_demo` and `ledger_ok` must be `true`, and `you.ip_seen` should be the address `ifconfig.me`
   prints. If it shows a proxy address instead, add the variable `TOT_PROXY_HOPS=2`, restart the Space and
   check again (otherwise per-visitor limits apply to everyone together: safe, but tight).
6. Take the public test (`/take`) with one or two answers and see `spent_today_usd` go up in `/api/guard`.

To update the site, build the bundle again and repeat step 3; `hf upload` replaces changed files.

**Restarts and storage.** Without persistent storage, the container's `/data` (spend ledger, volunteers'
summaries) is lost on every restart: a rebuild, a settings change, or waking up after 48 hours idle. Each
restart starts the day's count again, so the worst case is $2 per restart. With **Settings → Persistent
storage** (the smallest tier is a few dollars a month), `/data` survives and the caps hold across restarts.

## 2b. Fly.io (fallback)

Fly builds from the local folder (`.dockerignore` lets in `dist/site_data`), and a volume keeps `/data`.

```bash
brew install flyctl && fly auth login
python scripts/build_site_bundle.py
cp deploy/fly.toml.example fly.toml            # set a unique app name in it
fly apps create <app-name>
fly volumes create tippa_data --size 1 --region iad -a <app-name>
fly secrets set -a <app-name> MODEL_API_KEY=... TOT_RECEIPT_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
fly deploy --ha=false
curl -s "https://<app-name>.fly.dev/api/guard?debug=1"
```

`fly.toml` sets `TOT_CLIENT_IP_HEADER=fly-client-ip`, so per-visitor limits use Fly's own header. The volume
is mounted as root; the container's start script hands it to the app user before starting the app.
A shared CPU with 1 GB costs a few dollars a month and stops when idle.

## 2c. Render (fallback)

Render builds from the Git repository, which doesn't have the bundle, so deploy a prebuilt image:

```bash
python scripts/build_site_bundle.py
docker build --platform linux/amd64 -t ghcr.io/<user>/tippa-lingua:demo .
docker login ghcr.io && docker push ghcr.io/<user>/tippa-lingua:demo
```

Then create a Web Service from **Existing image** with that URL, add `MODEL_API_KEY` and `TOT_RECEIPT_KEY`
as secret environment variables, and check `/api/guard?debug=1` as above (set `TOT_PROXY_HOPS` if needed).
Render sets `PORT` itself. Free instances sleep after 15 minutes and have no disk, so the day's count restarts
on every wake-up; a paid instance with a disk mounted at `/data` keeps it.

## Volunteers' reference-range summaries

The public test (`/take`) lets adults who report no neurological or language condition add their result to the
reference range. Only a summary is stored, one JSON line per volunteer in `TIPPA_NORMS_DIR/<set>.jsonl`
(`/data/norms` in the container): set, set version, language, number of items, number correct, percent
correct, median latency, optional age band and the date. No audio, transcripts, names or IP addresses (the
per-visitor limit of 3 a day keys on a salted hash held in memory). The server rebuilds each summary from
signed per-answer receipts, so it can't be typed in by hand.

On the host these lines need persistent storage (`/data` above) or they vanish on restart. A small database
isn't needed at this volume. To publish a reference range, copy the `.jsonl` files to a laptop (Fly:
`fly ssh sftp get /data/norms/demo_en.jsonl`; a Space has no shell, so add a token-protected export route
first if the reference range matters) and run `python scripts/aggregate_norms.py --norms-dir <folder>`,
which writes `public_data/naming_norms_<set>.json` only for sets with at least 10 contributors.

## Settings

| Variable | Default (container) | Meaning |
|---|---|---|
| `MODEL_API_KEY` | none | Meta Model API key: a secret in the host's secret store |
| `PUBLIC_DEMO` | 1 | Turns on the guard; unset on a laptop |
| `TIPPA_PUBLIC_DAILY_USD` | 2 | Daily cap for all visitors together, per UTC day; 0 refuses every call |
| `MLL_BUDGET_USD` | 10 | Total cap for this host's ledger |
| `TIPPA_PUBLIC_BUILD_WORDS` / `_CANDIDATES` | 4 / 2 | Test Studio build size; 0 words turns builds off |
| `TIPPA_PUBLIC_PHOTO_TESTS` | 0 | 1 allows personal tests from a photo |
| `TIPPA_PUBLIC_ASK_PER_DAY` | 20 | Ask the Lab questions per visitor per day |
| `TIPPA_PUBLIC_GLOBAL_PER_MIN` | 60 | Paid requests per minute from everyone together |
| `TIPPA_PUBLIC_AUDIO_MB` | 2.5 | Largest naming recording |
| `TOT_LIMIT_BUILD` / `_SCENE` / `_SCORE` | 3 / 2 / 150 | Per visitor per day |
| `TIPPA_DATA_DIR` | /app/site_data | The bundle (`TOT_DATA_DIR` also works) |
| `TIPPA_NORMS_DIR`, `MLL_LEDGER` | /data/norms, /data/costs.jsonl | Volunteers' summaries and the spend ledger |
| `TOT_TRUST_PROXY`, `TOT_PROXY_HOPS`, `TOT_CLIENT_IP_HEADER` | 1, 1, none | How the visitor's address is found behind the host's proxy |
| `TOT_RECEIPT_KEY` | random per start | Signs public-test receipts: a secret |

The host's ledger is separate from the laptop's `runs/costs.jsonl`: the laptop's $120 cap doesn't see what
the site spends. Total spending is the two ledgers together (and the dev.meta.ai usage page).
