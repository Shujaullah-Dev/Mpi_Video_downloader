#  MPI Video Downloader Pro

> **High-Performance Parallel Video Downloading powered by MPI4Py & yt-dlp**

A Parallel & Distributed Computing (PDC) project that leverages **MPI (Message Passing Interface)** to download multiple videos simultaneously across parallel processes. Features a sleek **Streamlit web UI** for real-time monitoring and control.

---

##  Features

-  **True Parallel Downloads** — distributes URLs across multiple MPI ranks using round-robin scheduling
-  **Streamlit Web Dashboard** — live progress monitoring per rank with a modern UI
-  **Pause / Resume / Stop** — full runtime control over the download session
-  **Auto-Retry with Exponential Backoff** — configurable retries for failed downloads
-  **Quality Selection** — choose from `best`, `worst`, `480p`, `720p`, or `1080p`
-  **Bulk URL Import** — paste URLs manually or upload a `.txt` / `.csv` file
-  **Statistics Dashboard** — success rate, per-rank completion metrics, and download times
-  **Auto Download Logs** — JSON log saved after each session
-  **Wide Platform Support** — YouTube, Vimeo, YouTube Shorts, and [1000+ sites via yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

##  Architecture

```
┌─────────────────────────────────────────┐
│           Streamlit Web UI (app.py)      │
│  - URL input & config                    │
│  - Launches mpiexec subprocess           │
│  - Reads status_rank_*.json per rank     │
└────────────────┬────────────────────────┘
                 │ mpiexec -n <N>
                 ▼
┌─────────────────────────────────────────┐
│   MPI Worker Pool (mpi_video_downloader.py)       │
│                                         │
│  Rank 0  │  Rank 1  │  Rank 2  │  ...   │
│  URL 0   │  URL 1   │  URL 2   │        │
│  URL N   │  URL N+1 │  URL N+2 │        │
│                                         │
│  Each rank writes status_rank_<r>.json  │
│  MPI Barrier synchronizes at finish     │
└─────────────────────────────────────────┘
```

**URL Distribution:** Round-robin — URL `i` goes to rank `i % size`.

---

##  Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.13 |
| MPI Runtime | Microsoft MPI (Windows) / OpenMPI (Linux/macOS) |
| `mpi4py` | ≥ 4.1.1 |
| `yt-dlp` | ≥ 2023.0.0 |
| `streamlit` | ≥ 1.51.0 |
| `pandas` | ≥ 2.0.0 |
| `numpy` | ≥ 1.24.0 |

### Installing an MPI Runtime

**Windows** — Install [Microsoft MPI](https://learn.microsoft.com/en-us/message-passing-interface/microsoft-mpi):
```powershell
# Download and install msmpisetup.exe from the Microsoft MPI release page
# Verify installation
mpiexec --version
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt-get install libopenmpi-dev openmpi-bin
```

**macOS (Homebrew)**:
```bash
brew install open-mpi
```

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/mpi-video-downloader.git
cd mpi-video-downloader
```

### 2. Create and activate a virtual environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -e .
```
Or install directly:
```bash
pip install mpi4py streamlit yt-dlp pandas numpy
```

### 4. Verify MPI is working
```bash
mpiexec -n 4 python test_mpi.py
```
Expected output (order may vary):
```
Hello from rank 0 of 4
Hello from rank 1 of 4
Hello from rank 2 of 4
Hello from rank 3 of 4
```

---

##  Usage

### Option A — Web UI (Recommended)

Launch the Streamlit dashboard:
```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501` and:

1. **Configure** the number of MPI ranks (1–8) and output directory in the sidebar
2. **Paste** video URLs (one per line) or upload a `.txt` / `.csv` file
3. **Click** ▶️ Start Download
4. **Monitor** live progress in the **Progress** tab
5. **View** completed downloads and playback in the **Completed** tab
6. **Analyze** success rates and timing in the **Statistics** tab

### Option B — Command Line

Edit `config.json` manually, then run:

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=...",
    "https://vimeo.com/..."
  ],
  "output_dir": "downloads",
  "retry_failed": true,
  "max_retries": 2,
  "video_quality": "best"
}
```

```bash
mpiexec -n 4 python mpi_video_downloader.py
```

---

## 🎛️ Configuration Reference

| Key | Type | Default | Description |
|---|---|---|---|
| `urls` | `list[str]` | `[]` | List of video URLs to download |
| `output_dir` | `str` | `"downloads"` | Directory where videos are saved |
| `retry_failed` | `bool` | `true` | Enable auto-retry on failure |
| `max_retries` | `int` | `2` | Maximum retry attempts per URL |
| `video_quality` | `str` | `"best"` | Quality preset: `best`, `worst`, `480p`, `720p`, `1080p` |
| `num_ranks` | `int` | `4` | Number of MPI ranks (set via UI or `mpiexec -n`) |

---

## 📁 Project Structure

```
mpi-video-downloader/
├── app.py                   # Streamlit web dashboard
├── mpi_video_downloader.py  # MPI parallel download worker
├── config.json              # Runtime configuration (auto-generated by UI)
├── style.css                # Custom CSS for the Streamlit UI
├── test_mpi.py              # Quick MPI sanity check script
├── pyproject.toml           # Project metadata & dependencies
├── .gitignore
└── README.md
```

---

##  How Parallel Downloading Works

1. **Master (Rank 0)** reads `config.json` and logs the distribution plan.
2. **All ranks** independently compute their URL subset via round-robin (`url_index % size == rank`).
3. **Each rank** downloads its assigned videos sequentially, writing progress to `status_rank_<r>.json`.
4. The **Streamlit UI** polls these JSON files every 0.5 s to render live per-rank status.
5. **Pause/Resume** is implemented via a `pause.flag` file — workers poll for this file before each download.
6. After all downloads finish, a **MPI Barrier** synchronizes all ranks before the master prints the final summary.

---

##  Development

### Running without the UI (debugging)
```bash
mpiexec -n 2 python mpi_video_downloader.py
```

### Adding more supported sites
`yt-dlp` supports 1000+ sites out of the box. No code changes needed — just paste any supported URL into the UI.

### Extending quality options
Edit the `format_str` logic inside `download_video()` in `mpi_video_downloader.py`.

---

##  Known Limitations

- **Windows**: Requires [Microsoft MPI](https://learn.microsoft.com/en-us/message-passing-interface/microsoft-mpi) to be installed separately.
- **Progress granularity**: The per-rank progress bar shows 50% while downloading (yt-dlp does not expose fine-grained progress via its quiet mode).
- **Rank count vs. URL count**: If you launch more ranks than URLs, some ranks will be idle.
- **Streamlit session state**: Refreshing the browser tab mid-download may reset the UI session (the MPI process continues in the background).

---

##  Dependencies

| Package | Purpose |
|---|---|
| [`mpi4py`](https://mpi4py.readthedocs.io/) | MPI bindings for Python |
| [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) | Video downloading engine |
| [`streamlit`](https://streamlit.io/) | Web dashboard UI |
| [`pandas`](https://pandas.pydata.org/) | Tabular results display |
| [`numpy`](https://numpy.org/) | Numerical support |

---

##  License

This project was developed as a **Parallel & Distributed Computing (PDC) Lab Project** for academic purposes.

---

## 🙏 Acknowledgements

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — the powerful video download engine
- [mpi4py](https://mpi4py.readthedocs.io/) — MPI for Python
- [Streamlit](https://streamlit.io/) — rapid Python web app framework

