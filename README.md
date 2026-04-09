# Clinic NL2SQL Chatbot

An AI-powered Natural Language to SQL system built with **Vanna 2.0** and **FastAPI**.  
Users ask questions in plain English and receive SQL results from a clinic database — no SQL required.

---

## Tech Stack

| Layer         | Technology               |
|---------------|--------------------------|
| LLM Provider  | Google Gemini 2.5 Flash  |
| NL2SQL Engine | Vanna 2.0 (Agent-based)  |
| API Framework | FastAPI + Uvicorn        |
| Database      | SQLite (`clinic.db`)     |
| Charts        | Plotly                   |

**LLM Provider chosen: Google Gemini** (`gemini-2.5-flash`)  
Free API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

---

## Project Structure

```
project/
├── setup_database.py   # Creates clinic.db schema + dummy data
├── vanna_setup.py      # Vanna 2.0 Agent initialization
├── seed_memory.py      # Pre-seeds agent with 15+ Q→SQL pairs
├── main.py             # FastAPI application
├── sql_validator.py    # SQL security validation layer
├── requirements.txt    # All pip dependencies
├── README.md           # This file
├── RESULTS.md          # Test results for all 20 questions
└── clinic.db           # Generated SQLite database (after setup)
```

---

## Setup Instructions

### 1. Clone and enter the project

```bash
git clone <your-repo-url>
cd project
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your Google Gemini API key

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your-key-here
```

Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).  
**Do not commit this file** — it is in `.gitignore`.

### 5. Create the database

```bash
python setup_database.py
```

Expected output:
```
🏥  Building clinic.db ...
  → Inserting 15 doctors ...
  → Inserting 200 patients ...
  → Inserting 500 appointments ...
  → Inserting ~350 treatments (Completed only) ...
  → Inserting 300 invoices ...

✅  Done!
   Created 200 patients
   Created 15 doctors
   Created 500 appointments  (Completed: ~280)
   Created ~350 treatments
   Created 300 invoices  (Overdue: ~60)
```

### 6. Seed the agent memory

```bash
python seed_memory.py
```

This pre-loads 15+ verified Q→SQL pairs so the agent starts with domain knowledge.

### 7. Start the API server

```bash
uvicorn main:app --port 8000 --reload
```

The API is now live at `http://localhost:8000`.

---

## One-liner (full startup)

```bash
pip install -r requirements.txt && \
python setup_database.py && \
python seed_memory.py && \
uvicorn main:app --port 8000
```

---

## API Documentation

### `POST /chat`

Accepts a plain-English question and returns SQL results.

**Request**

```http
POST /chat
Content-Type: application/json

{
  "question": "Show me the top 5 patients by total spending"
}
```

**Response**

```json
{
  "message": "Found 5 rows. Here is a bar chart of the results.",
  "sql_query": "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM invoices i JOIN patients p ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5;",
  "columns": ["first_name", "last_name", "total_spending"],
  "rows": [
    ["Priya", "Sharma", 7800.50],
    ["Rahul", "Gupta",  6500.00]
  ],
  "row_count": 5,
  "chart": { "data": [...], "layout": {...} },
  "chart_type": "bar"
}
```

**Validation errors** return a response with a `message` field explaining the issue — not an HTTP 500.

---

### `GET /health`

Liveness and readiness probe.

**Response**

```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 15
}
```

---

## Architecture Overview

```
User Question (plain English)
        │
        ▼
  FastAPI /chat endpoint
        │  Input validation (Pydantic, length limits)
        │  Rate limiter (20 req/min per IP)
        │  Cache check (avoid duplicate LLM calls)
        │
        ▼
  Vanna 2.0 Agent
        │  LLM: GeminiLlmService (gemini-2.5-flash)
        │  Memory: DemoAgentMemory (15+ seeded pairs)
        │  Tools: RunSqlTool, VisualizeDataTool, memory tools
        │
        ▼
  SQL Extraction + Validation
        │  SELECT-only enforcement
        │  Forbidden keyword check (DROP, EXEC, GRANT …)
        │  System table block (sqlite_master …)
        │  Semicolon injection detection
        │
        ▼
  SQLite Execution (clinic.db)
        │
        ▼
  Chart Generation (Plotly)
        │
        ▼
  JSON Response → User
```

---

## Bonus Features Implemented

| Feature           | Implementation |
|-------------------|----------------|
| Chart Generation  | Plotly — auto-selects bar / line / scatter |
| Input Validation  | Pydantic v2 validators on `ChatRequest`    |
| Query Caching     | In-memory dict keyed on normalised question |
| Rate Limiting     | 20 requests / 60 seconds per IP            |
| Structured Logging| Python `logging` with timestamps           |

---

## Notes

- **Vanna 2.0 only** — does not use `vn.train()`, `VannaBase`, or ChromaDB.
- **No API key hardcoded** — always loaded from `.env` via `python-dotenv`.
- **SQLite is intentional** — the pipeline is database-agnostic; swap `SqliteRunner` for any other runner.
