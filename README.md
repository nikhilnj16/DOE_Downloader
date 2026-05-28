# Education Data Pipeline

A fully replicable Python pipeline for automatically downloading, cleaning,
and organising publicly available K-12 education data from the **Nevada** and
**Massachusetts** Departments of Education.

---

## Project Overview

| Feature | Details |
|---|---|
| **States** | Nevada, Massachusetts |
| **Categories** | Test Scores, Financials, Teacher Records, Enrollment, Suspensions |
| **Input formats** | `.xlsx`, `.xls`, `.csv`, `.pdf` |
| **Output format** | UTF-8 CSV |
| **Retry logic** | Exponential back-off, up to 3 attempts per file |
| **Logging** | `logs/pipeline.log` + `logs/download_manifest.csv` |

---

## Setup

### 1. Clone / download the project

```bash
git clone https://github.com/your-org/doe_downloaders.git
cd doe_downloaders
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the Pipeline

### Full pipeline — both states, all categories

```bash
python main.py --state both --category all
```

### Single state + category

```bash
python main.py --state nevada --category test_scores
python main.py --state massachusetts --category financials
```

### Download only (skip cleaning)

```bash
python main.py --state massachusetts --category financials --skip-clean
```

### Clean only (skip downloading, e.g. files already downloaded)

```bash
python main.py --state nevada --category enrollment --skip-download
```

### Run a single downloader script standalone

```bash
python scripts/downloaders/nevada/nv_test_scores.py
python scripts/downloaders/massachusetts/ma_enrollment.py
```

### Run a single cleaner script standalone

```bash
python scripts/cleaners/clean_test_scores.py --state nevada
python scripts/cleaners/clean_financials.py --state massachusetts
```

---

## Folder Structure

```
doe_downloaders/
├── data/
│   ├── nevada/
│   │   ├── raw/          ← downloaded files land here
│   │   └── cleaned/      ← cleaned CSVs go here
│   └── massachusetts/
│       ├── raw/
│       └── cleaned/
├── scripts/
│   ├── downloaders/
│   │   ├── base_downloader.py   ← shared base class
│   │   ├── nevada/              ← NV-specific downloaders
│   │   └── massachusetts/       ← MA-specific downloaders
│   ├── cleaners/                ← one cleaner per category (both states)
│   └── utils/
│       ├── file_utils.py        ← directory creation, extension detection
│       └── logger.py            ← logging setup, manifest CSV writer
├── logs/
│   ├── pipeline.log             ← timestamped run log
│   └── download_manifest.csv   ← one row per attempted download
├── docs/
│   ├── source_urls.md           ← reference table of all source URLs
│   └── data_dictionary.md      ← expected cleaned column schemas
├── notebooks/
│   └── walkthrough.ipynb        ← interactive guided walkthrough
├── main.py                      ← pipeline entry point (argparse CLI)
├── config.py                    ← all URLs, paths, and request settings
├── requirements.txt
└── README.md
```

---

## How to Add a New State

1. **Add URLs** to `config.py` under a new state key in the `URLS` dict.
2. **Create downloader scripts** in `scripts/downloaders/{new_state}/`:
   - One `.py` file per category following the same pattern as the Nevada scripts.
   - Each file defines `STATE`, `CATEGORY`, `URLS`, and `download_all()`.
3. **Register** the new downloaders in the `_DOWNLOADER_REGISTRY` dict in `main.py`.
4. **Add raw/cleaned directories** by running `python -c "from scripts.utils.file_utils import create_dir_structure; create_dir_structure()"`.
   - Or add the state to `STATES` in `config.py` and the structure will be created automatically on the next run.

The cleaner scripts (`scripts/cleaners/clean_*.py`) already handle both states
generically — no changes needed unless the new state has a fundamentally
different file format.

---

## How to Add a New Data Category

1. **Add the category** to `CATEGORIES` in `config.py`.
2. **Add URLs** for each state in `config.py` under `URLS[state][new_category]`.
3. **Create downloader scripts** (one per state) inheriting from `BaseDownloader`.
4. **Create a cleaner** `scripts/cleaners/clean_{new_category}.py` with a `clean(state)` function.
5. **Register** the new downloaders and cleaner in `main.py`.

---

## Logging & the Download Manifest

Every run appends to two log outputs:

| File | Format | Contents |
|---|---|---|
| `logs/pipeline.log` | Plain text | Timestamped DEBUG/INFO/ERROR messages for the whole run |
| `logs/download_manifest.csv` | CSV | One row per file attempted: `timestamp, state, category, url, filename, status, filesize_kb` |

The manifest makes it easy to audit what was downloaded, detect failures,
and avoid re-downloading unchanged files in future runs.

---

## Key Design Decisions

- **`pathlib.Path` everywhere** — no `os.path` string manipulation.
- **No hardcoded paths** — all paths derived from `config.ROOT_DIR`.
- **`requests.Session` with `urllib3.util.retry.Retry`** — automatic retry with exponential back-off on 429/5xx errors.
- **`pdfplumber`** — extracts tabular data from PDFs without external tools.
- **Dynamic import in `main.py`** — new downloaders/cleaners plug in without modifying core orchestration logic.
