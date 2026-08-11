# 🕷️ Daily AI News Swarm Crawler

A collaborative, multi-agent CrewAI workflow that discovers, scrapes, validates, and deduplicates news from leading AI newsletters (TLDR AI, The Rundown AI, and The Neuron) into a unified daily digest dashboard.

---

## 🚀 Key Features

* **Decoupled Architecture**: Decoupled UI layer (`app.py`) from business operations (`services/crawler_service.py`).
* **Resilient Scraping Framework**: Implements connection pooling (`httpx.Client`), rate limiting (`TokenBucketRateLimiter`), exponential backoff, and circuit breakers.
* **Hardened Security**: Features a DNS Rebinding Shield protecting against local SSRF network intrusions, strict credential log/traceback masking, and input validation.
* **Deterministic Deduplication**: Compiles stories using semantic embedding similarities (Gemini `text-embedding-004`) to cluster duplicate reports.
* **Beautiful Dashboard**: Serving a glassmorphic Streamlit interface displaying real-time agent console logs, key metrics cards, and a human markdown digest viewer.

---

## 🛠️ Getting Started

### Prerequisites

* Python 3.10+
* Google Gemini API Key

### Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/shuangmulin-io/newsletter-crawler.git
   cd newsletter-crawler
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Launch the Streamlit application:
   ```bash
   python -m streamlit run app.py
   ```

Access the dashboard at `http://localhost:8501`.

---

## 🐳 Docker Deployment

The application can also be deployed containerized:

```bash
docker-compose up --build
```

---

## 🧪 Testing

Run the pytest unit testing suite to verify security limits, rate limiters, backoff behaviors, and circuit breakers:

```bash
python -m pytest tests/
```
