# ReliefWeb Document Fetcher & PDF Text Processor

A complete web application for downloading disaster reports and PDFs from the [ReliefWeb API](https://reliefweb.int/), with built-in full-text extraction from downloaded PDFs.

---

## 📁 Project Structure

```
reliefweb-fetcher/
├── reliefweb_server.py        # Flask backend server (API + serves frontend)
├── pdf_processor.py           # PDF text extraction module
├── demo_standalone.html       # Complete frontend (auto-served by Flask)
├── reliefweb_component.html   # Embeddable HTML component
├── requirements.txt           # Python dependencies
├── render.yaml                # Render deployment blueprint
├── INTEGRATION_GUIDE.md       # Integration instructions
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

---

## 🚀 Quick Start (Local)

```bash
git clone https://github.com/YOUR_USERNAME/reliefweb-fetcher.git
cd reliefweb-fetcher
pip install -r requirements.txt
python reliefweb_server.py
```

Open **http://localhost:5000** in your browser. That's it!

---

## ☁️ Deploy to Render (Free — Public URL)

This is the recommended way to make the app accessible to anyone.

### Step-by-Step

1. **Push your code to GitHub** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/reliefweb-fetcher.git
   git push -u origin main
   ```

2. **Go to [Render Dashboard](https://dashboard.render.com/)**

3. Click **"New +"** → **"Web Service"**

4. **Connect your GitHub repository** (`reliefweb-fetcher`)

5. Render will auto-detect the `render.yaml` and configure everything. If not, use these settings:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn reliefweb_server:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 300`
   - **Plan**: Free

6. Click **"Create Web Service"**

7. Wait ~2 minutes for the build. Your app will be live at:
   ```
   https://reliefweb-fetcher.onrender.com
   ```

### ⚠️ Render Free Tier Notes
- The service **spins down after 15 minutes of inactivity** (first request after sleep takes ~30 seconds)
- Files stored in `/tmp` are **ephemeral** — they are lost when the service restarts
- For persistent storage, upgrade to a paid plan or use an external storage service

---

## 🔧 Configuration

### Auto-Detection

The frontend **automatically detects** where it's being served from:
- If served by Flask (locally or on Render) → uses the same server
- If opened as a local file or from GitHub Pages → defaults to `http://localhost:5000`

You can always override this via the **⚙️ Server Settings** panel at the top of the page.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RELIEFWEB_OUTPUT_DIR` | `./reliefweb_data` | Where PDFs and JSON files are stored |
| `PORT` | `5000` | Server port (Render sets this automatically) |

---

## 📖 Features

### 📋 Document Fetcher
- Search ReliefWeb by disaster name and country
- Download all related PDFs automatically
- Real-time progress tracking with animated progress bar
- Batch download as ZIP file
- Metadata saved as JSON

### 📄 PDF Text Processor
- Browse previously downloaded data folders
- Extract full text from all PDFs using `pdfplumber`
- Matches extracted text back to the original report metadata
- Generates a structured full-text JSON file
- Real-time progress bar during extraction
- Download the resulting JSON directly from the browser

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the frontend HTML |
| `GET` | `/api/countries` | List all countries (cached) |
| `POST` | `/api/fetch` | Start a document download job |
| `GET` | `/api/status/<job_id>` | Get download job status |
| `GET` | `/api/download/zip/<job_id>` | Download ZIP of fetched PDFs |
| `GET` | `/api/download/json/<job_id>` | Download metadata JSON |
| `GET` | `/api/folders` | List available data folders |
| `POST` | `/api/process` | Start PDF text extraction job |
| `GET` | `/api/process/status/<job_id>` | Get processing job status |
| `GET` | `/api/process/download/<job_id>` | Download full-text JSON |
| `GET` | `/api/health` | Health check |

---

## 📂 Output Structure

```
reliefweb_data/
└── Hurricane_Melissa_HTI_20250213_143022/
    ├── pdfs/
    │   ├── 12345_report.pdf
    │   └── ...
    ├── Hurricane_Melissa_HTI_reports.json           # Metadata
    ├── Hurricane_Melissa_HTI_pdfs.zip               # All PDFs + metadata
    └── Hurricane_Melissa_HTI_reports_fulltext.json   # After text extraction
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Server status shows "Offline" | Make sure the Flask server is running |
| CORS errors | Ensure `flask-cors` is installed |
| No PDFs downloaded | Try different disaster/country combinations |
| Render deploy fails | Check build logs in the Render dashboard |
| Slow first load on Render | Free tier spins down after inactivity — wait ~30s |
| Folders not showing | Fetch some documents first, then click "Refresh Folders" |

---

## 🎯 Example Queries

- **Hurricane Melissa** + Haiti
- **Typhoon Haiyan** + Philippines
- **Nepal Earthquake** + Nepal
- **Pakistan Floods** + Pakistan
- **Syrian Crisis** + Syria

---

## 📊 Tech Stack

- **Backend**: Python 3.8+, Flask, pdfplumber, gunicorn
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks, no build step)
- **Deployment**: Render (free tier)
- **API**: [ReliefWeb API v1](https://apidoc.rwlabs.org/)

---

## 📄 License

Open source — available for use in humanitarian and research contexts.

---

**Built with ❤️ for humanitarian data collection**
