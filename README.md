# Clinic NL2SQL Chatbot

A Natural Language to SQL system built using Vanna 2.0 and FastAPI. You type a question in plain English, it generates SQL, runs it against a clinic database and gives back the results. No SQL needed.

---

## Tech Stack

| Layer         | Technology              |
|---------------|-------------------------|
| LLM Provider  | Google Gemini 2.5 Flash |
| NL2SQL Engine | Vanna 2.0               |
| API Framework | FastAPI + Uvicorn       |
| Database      | SQLite (`clinic.db`)    |
| Charts        | Plotly                  |

I went with **Google Gemini** (`gemini-2.5-flash`) since it has a free tier and works well with Vanna 2.0. Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

---

## Project Structure

```
project/
├── setup_database.py   # creates the database and inserts dummy data
├── vanna_setup.py      # sets up the Vanna 2.0 agent
├── seed_memory.py      # pre-loads 15 Q→SQL pairs into agent memory
├── main.py             # FastAPI app
├── sql_validator.py    # blocks unsafe SQL before execution
├── requirements.txt
├── README.md
└── RESULTS.md          # test results for all 20 questions
```

---

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd project
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your API key

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your-key-here
```

This file is already in `.gitignore` so it won't get committed.

### 5. Create the database

```bash
python setup_database.py
```

You should see something like:

```
Building clinic.db ...
  inserting doctors...
  inserting patients...
  inserting appointments...
  inserting treatments...
  inserting invoices...

Done!
  200 patients, 15 doctors, 500 appointments, ~350 treatments, 300 invoices
```

### 6. Seed agent memory

```bash
python seed_memory.py
```

This loads 15+ verified question-SQL pairs so the agent has some context before you start asking questions.

### 7. Start the server

```bash
uvicorn main:app --port 8000 --reload
```

API is live at `http://localhost:8000`.

---

## One-liner

```bash
pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000
```

---

## API

### `POST /chat`

Send a plain English question, get back SQL + results.

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
  "message": "Found 5 rows.",
  "sql_query": "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM invoices i JOIN patients p ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5;",
  "columns": ["first_name", "last_name", "total_spending"],
  "rows": [
    ["Priya", "Sharma", 7800.50],
    ["Rahul", "Gupta", 6500.00]
  ],
  "row_count": 5,
  "chart": { "data": [...], "layout": {...} },
  "chart_type": "bar"
}
```

If the generated SQL fails validation, you get back a message explaining why — not a 500 error.

---

### `GET /health`

```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 15
}
```

---

## How it works

```
User question
     ↓
FastAPI — validates input, checks cache, applies rate limit
     ↓
Vanna 2.0 Agent — generates SQL using Gemini + seeded memory
     ↓
sql_validator.py — SELECT only, blocks DROP/EXEC/system tables
     ↓
SQLite — runs the query on clinic.db
     ↓
Plotly — generates chart if relevant
     ↓
JSON response
```

---

## Bonus features

| Feature          | Notes                                         |
|------------------|-----------------------------------------------|
| Charts           | Plotly, auto picks bar/line/scatter           |
| Input validation | Pydantic v2 on the request body               |
| Caching          | In-memory cache keyed on the question         |
| Rate limiting    | 20 requests per minute per IP                 |
| Logging          | Python logging with timestamps on every step  |

---

## Notes

- Uses Vanna 2.0 — not the old 0.x API. No `vn.train()`, no ChromaDB.
- API key is loaded from `.env` only, never hardcoded.
- SQLite is intentional for this assignment. The pipeline itself is database-agnostic.





 




 
