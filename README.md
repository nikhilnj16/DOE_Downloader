# Education Data Downloader

A fully replicable Python pipeline for automatically downloading and organizing publicly available K-12 education data from the **Alaska** and **Ohio** Departments of Education.

---

## Setup

### 1. Clone/download the project
```bash
git clone https://github.com/nikhilnj16/DOE_Downloader.git
cd DOE_Downloader
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Pipeline

The pipeline supports downloading data by **State** and **Category**. All downloads are automatically saved to `data/{state}/{category}/` using the original filenames. Existing files on disk are automatically skipped during reruns.

### 🟢 Alaska (AK) Downloads

#### 1. Download all categories for Alaska:
```bash
python main.py --state alaska --category all
```

#### 2. Download specific categories for Alaska:
```bash
# Assessments (Overall & subgroups results flat)
python main.py --state alaska --category assessments

# School & District Financial reports
python main.py --state alaska --category financials

# Educator counts and staff profiles
python main.py --state alaska --category teacher_staff

# Student enrollment registers & chronic absenteeism
python main.py --state alaska --category enrollment_attendance
```

#### 3. Run standalone Alaska script:
```bash
python scripts/downloaders/alaska/ak_downloader.py
```

---

### 🟢 Ohio (OH) Downloads

The Ohio downloader uses a high-speed direct extraction pattern, querying the Azure Blob Storage REST API directly to fetch bulk data zip folders without loading heavy single-page application wrappers.

#### 1. Download all categories for Ohio:
```bash
python main.py --state ohio --category all
```

#### 2. Download specific categories for Ohio:
```bash
# Assessments bulk data
python main.py --state ohio --category assessments

# Per-pupil expenditures and finance manuals
python main.py --state ohio --category financials

# Educator credentials & certification databases
python main.py --state ohio --category teacher_staff

# Chronic absenteeism, enrollment detail spreadsheets
python main.py --state ohio --category enrollment_attendance
```

#### 3. Run standalone Ohio script:
```bash
python scripts/downloaders/ohio/oh_downloader.py
```

---

## Folder Structure

All data directories are set up in a clean, flat directory tree:

```text
DOE_Downloader/
├── config.py                 # Core configurations, state URLs lists, and path overrides
├── main.py                   # Orchestrator CLI entry point
├── requirements.txt          # Python dependencies
├── README.md                 # Project instructions
├── scripts/
│   ├── downloaders/
│   │   ├── base_downloader.py    # Common downloader helper base class
│   │   ├── alaska/               # Alaska specific downloader files
│   │   └── ohio/                 # Ohio specific downloader files
│   └── utils/
│       ├── file_utils.py         # Directory structure initializers & filename helpers
│       ├── logger.py             # Custom logging & download_manifest.csv appender
│       └── drive_upload.py       # Google Drive upload integration
└── data/                     # Output directories (ignored by Git)
    ├── alaska/
    │   ├── assessments/          # All ELA, Math, Science assessment score sheets (flat)
    │   ├── financials/
    │   ├── teacher_staff/
    │   └── enrollment_attendance/
    └── ohio/
        ├── assessments/
        ├── financials/
        ├── teacher_staff/
        └── enrollment_attendance/
```

---

## Logging & Auditing

Every run logs details and appends trace metadata into `logs/` (automatically created at runtime):
- **`logs/pipeline.log`**: A text log detailing timestamps, warnings, errors, and informational status of downloads.
- **`logs/download_manifest.csv`**: A CSV manifest recording download attempts with headers: `timestamp, state, category, url, filename, status, filesize_kb`.
