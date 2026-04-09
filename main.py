"""
main.py
FastAPI application for the Clinic NL2SQL chatbot.

Endpoints:
  POST /chat    
  GET  /health  
Start:
    uvicorn main:app --port 8000 --reload
"""

import os
import re
import json
import sqlite3
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import pandas as pd # type: ignore
import plotly.express as px # type: ignore
import plotly # type: ignore
from fastapi import FastAPI, HTTPException, Request # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from fastapi.responses import JSONResponse # type: ignore
from pydantic import BaseModel, Field, field_validator # type: ignore

from vanna_setup import build_agent, DB_PATH
from sql_validator import validate_sql, ValidationError

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("clinic.api")

# ─────────────────────────────────────────────────────────────────────────────
# App state — agent is built once at startup and reused across requests
# ─────────────────────────────────────────────────────────────────────────────

class AppState:
    agent = None
    query_cache: dict[str, dict] = {}   # simple in-memory cache


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the Vanna 2.0 agent when the server starts."""
    log.info("Starting up — building Vanna 2.0 agent ...")
    try:
        state.agent = build_agent()
        log.info("Agent ready ✓")
    except Exception as exc:
        log.error(f"Agent build failed: {exc}")
        raise
    yield
    log.info("Shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Clinic NL2SQL API",
    description="Ask questions in plain English, get SQL results from the clinic database.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Rate limiting — simple per-IP token bucket (bonus requirement)
# ─────────────────────────────────────────────────────────────────────────────

_rate_store: dict[str, list[float]] = {}
RATE_LIMIT   = 20    # requests
RATE_WINDOW  = 60.0  # seconds


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    timestamps = _rate_store.get(ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(timestamps) >= RATE_LIMIT:
        _rate_store[ip] = timestamps
        return True
    timestamps.append(now)
    _rate_store[ip] = timestamps
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def question_must_be_meaningful(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Question cannot be blank.")
        if len(stripped) < 3:
            raise ValueError("Question is too short — please be more specific.")
        return stripped


class ChatResponse(BaseModel):
    message:    str
    sql_query:  str | None     = None
    columns:    list[str]      = []
    rows:       list[list]     = []
    row_count:  int            = 0
    chart:      dict | None    = None
    chart_type: str | None     = None


class HealthResponse(BaseModel):
    status:              str
    database:            str
    agent_memory_items:  int


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_sql_from_response(agent_response: str) -> str | None:
    """
    Pull the SQL out of whatever text the agent returns.
    Tries four strategies in order of reliability.
    """
    # Strategy 1: markdown code fence  ```sql ... ```
    fence = re.search(r"```(?:sql)?\s*([\s\S]+?)```", agent_response, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()

    # Strategy 2: line starting with SELECT / WITH
    for line in agent_response.splitlines():
        if re.match(r"^\s*(SELECT|WITH)\b", line, re.IGNORECASE):
            # grab from this line to end-of-block (heuristic: stop at blank line)
            idx = agent_response.index(line)
            block = agent_response[idx:]
            end = re.search(r"\n\s*\n", block)
            return block[: end.start()].strip() if end else block.strip()

    # Strategy 3: anything between SELECT and semicolon
    sel = re.search(r"(SELECT[\s\S]+?;)", agent_response, re.IGNORECASE)
    if sel:
        return sel.group(1).strip()

    # Strategy 4: give up
    return None


def _run_sql_on_db(sql: str) -> pd.DataFrame:
    """Execute a validated SELECT query and return a DataFrame."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df


def _pick_chart_type(df: pd.DataFrame) -> str:
    """Heuristic to choose the most appropriate chart type."""
    cols = df.columns.tolist()
    n_numeric = sum(pd.api.types.is_numeric_dtype(df[c]) for c in cols)

    # Time-series patterns
    if any(c.lower() in ("month", "date", "week", "year") for c in cols):
        return "line"
    # Single numeric → bar
    if n_numeric == 1 and len(cols) == 2:
        return "bar"
    # Two numerics → scatter
    if n_numeric >= 2:
        return "scatter"
    return "bar"


def _build_chart(df: pd.DataFrame) -> tuple[dict | None, str | None]:
    """
    Return a (plotly-json-dict, chart_type) pair, or (None, None) if
    the data isn't suitable for charting.
    """
    if df.empty or len(df.columns) < 2:
        return None, None

    try:
        chart_type = _pick_chart_type(df)
        cols       = df.columns.tolist()
        x_col      = cols[0]
        # pick the first numeric column as y
        numeric_cols = [c for c in cols[1:] if pd.api.types.is_numeric_dtype(df[c])]
        if not numeric_cols:
            return None, None
        y_col = numeric_cols[0]

        if chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col, title=f"{y_col} over {x_col}")
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col)
        else:
            fig = px.bar(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}")

        fig.update_layout(margin=dict(l=40, r=40, t=60, b=40))
        chart_dict = json.loads(plotly.io.to_json(fig))
        return chart_dict, chart_type

    except Exception as exc:
        log.warning(f"Chart generation failed: {exc}")
        return None, None


async def _ask_agent(question: str, remote_addr: str = "127.0.0.1") -> dict:
    """
    Send the question to the Vanna 2.0 agent and collect structured response.
    Handles all UiComponent types returned by Vanna 2.0.2.
    """
    from vanna.core.user import RequestContext # type: ignore
    from vanna.components.rich import ( # type: ignore
        ArtifactComponent, DataFrameComponent, RichTextComponent,
        CardComponent, NotificationComponent, StatusCardComponent,
        TaskTrackerUpdateComponent
    )
    from vanna.components.simple import SimpleTextComponent # type: ignore

    agent = state.agent
    request_context = RequestContext(remote_addr=remote_addr)

    result = {
        "sql": None,
        "text": [],
        "rows": [],
        "columns": [],
    }

    async for component in agent.send_message(request_context, question):
        rich   = getattr(component, "rich_component", None)
        simple = getattr(component, "simple_component", None)

        # Log every component type to help with debugging
        rich_type = type(rich).__name__ if rich is not None else None
        log.info(f"[agent] component: rich={rich_type}, simple={type(simple).__name__ if simple else None}")
        if rich is not None:
            # Log all non-None fields for inspection
            for field in getattr(rich, "model_fields", {}):
                val = getattr(rich, field, None)
                if val and field not in ("id","type","lifecycle","data","children","timestamp","visible","interactive"):
                    log.info(f"  [{rich_type}] {field} = {str(val)[:120]}")

        # ── ArtifactComponent: SQL query or other code ────────────────────
        if isinstance(rich, ArtifactComponent):
            atype = getattr(rich, "artifact_type", "") or ""
            content = getattr(rich, "content", "") or ""
            if "sql" in atype.lower() or content.strip().upper().startswith("SELECT"):
                result["sql"] = content
                log.info(f"[agent] SQL captured from ArtifactComponent: {content[:80]}")
            else:
                if content:
                    result["text"].append(content)

        # ── DataFrameComponent: result rows ───────────────────────────────
        elif isinstance(rich, DataFrameComponent):
            result["columns"] = rich.columns or []
            result["rows"] = [
                [row.get(col) for col in (rich.columns or [])]
                for row in (rich.rows or [])
            ]
            log.info(f"[agent] DataFrame: {len(result['rows'])} rows, cols={result['columns']}")

        # ── RichTextComponent ─────────────────────────────────────────────
        elif isinstance(rich, RichTextComponent):
            content = getattr(rich, "content", "") or ""
            # Could contain SQL in a code block
            if not result["sql"] and "SELECT" in content.upper():
                sql_candidate = _extract_sql_from_response(content)
                if sql_candidate:
                    result["sql"] = sql_candidate
            if content:
                result["text"].append(content)

        # ── CardComponent ─────────────────────────────────────────────────
        elif isinstance(rich, CardComponent):
            for attr in ("content", "title", "subtitle"):
                val = getattr(rich, attr, None)
                if val:
                    result["text"].append(str(val))

        # ── NotificationComponent ─────────────────────────────────────────
        elif isinstance(rich, NotificationComponent):
            msg = getattr(rich, "message", None)
            if msg:
                result["text"].append(msg)

        # ── StatusCardComponent ───────────────────────────────────────────
        elif isinstance(rich, StatusCardComponent):
            for attr in ("title", "description"):
                val = getattr(rich, attr, None)
                if val:
                    result["text"].append(str(val))

        # ── TaskTrackerUpdate (progress messages like "Processing...") ────
        elif isinstance(rich, TaskTrackerUpdateComponent):
            detail = getattr(rich, "detail", None)
            if detail:
                result["text"].append(str(detail))

        # ── SimpleTextComponent fallback ──────────────────────────────────
        elif isinstance(simple, SimpleTextComponent):
            txt = getattr(simple, "text", "") or ""
            if not result["sql"] and "SELECT" in txt.upper():
                sql_candidate = _extract_sql_from_response(txt)
                if sql_candidate:
                    result["sql"] = sql_candidate
            if txt:
                result["text"].append(txt)

        # ── Generic fallback: scan all string fields ──────────────────────
        elif rich is not None:
            for attr in ("content", "text", "message", "description"):
                val = getattr(rich, attr, None)
                if val and isinstance(val, str):
                    if not result["sql"] and "SELECT" in val.upper():
                        sql_candidate = _extract_sql_from_response(val)
                        if sql_candidate:
                            result["sql"] = sql_candidate
                    result["text"].append(val)
                    break

    # ── If still no SQL, try to extract from all collected text ──────────
    if not result["sql"]:
        combined = " ".join(result["text"])
        result["sql"] = _extract_sql_from_response(combined)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req_body: ChatRequest, request: Request):
    """
    Accept a plain-English question and return:
      - The generated SQL
      - Result rows and column names
      - An optional Plotly chart
      - A human-readable summary message
    """
    client_ip = request.client.host if request.client else "unknown"

    # ── Rate limit check ──────────────────────────────────────────────────────
    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment and try again.",
        )

    question = req_body.question
    log.info(f"[/chat] question='{question}' ip={client_ip}")

    # ── Cache hit ─────────────────────────────────────────────────────────────
    cache_key = question.lower().strip()
    if cache_key in state.query_cache:
        log.info("[/chat] Cache hit — returning cached response.")
        return JSONResponse(content=state.query_cache[cache_key])

    # ── Ask the agent ─────────────────────────────────────────────────────────
    try:
        agent_result = await _ask_agent(question, remote_addr=client_ip)
        log.info(f"[/chat] Agent responded — sql={'yes' if agent_result['sql'] else 'no'}, rows={len(agent_result['rows'])}")
    except Exception as exc:
        log.error(f"[/chat] Agent error: {exc}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(exc)}")

    # ── Extract SQL (from agent components, or fall back to text parsing) ─────
    sql = agent_result["sql"]
    if not sql:
        combined_text = " ".join(agent_result["text"])
        sql = _extract_sql_from_response(combined_text)
    if sql:
        log.info(f"[/chat] SQL extracted: {sql[:80]}...")

    has_rows = bool(agent_result["rows"] and agent_result["columns"])

    # ── If no SQL AND no rows — agent couldn't answer ─────────────────────────
    if not sql and not has_rows:
        friendly = " ".join(agent_result["text"]).strip()
        return ChatResponse(
            message=friendly or "I could not generate a SQL query for that question. Please try rephrasing it."
        )

    # ── Validate SQL if we have one (security gate) ───────────────────────────
    if sql:
        try:
            validate_sql(sql)
        except ValidationError as ve:
            log.warning(f"[/chat] SQL validation failed: {ve}")
            # If we still have rows from the agent, use them anyway
            if not has_rows:
                return ChatResponse(
                    message=f"The generated query failed security validation: {ve}",
                    sql_query=sql,
                )

    # ── Build DataFrame: prefer agent rows, else run SQL ourselves ────────────
    if has_rows:
        columns = agent_result["columns"]
        rows    = agent_result["rows"]
        df      = pd.DataFrame(rows, columns=columns)
        log.info(f"[/chat] Using agent DataFrame: {len(df)} rows")
    else:
        try:
            df = _run_sql_on_db(sql)
            log.info(f"[/chat] Executed SQL directly: {len(df)} rows")
        except Exception as exc:
            log.error(f"[/chat] DB execution error: {exc}")
            return ChatResponse(
                message=f"The query ran into a database error: {exc}",
                sql_query=sql,
            )

    # ── Empty result ──────────────────────────────────────────────────────────
    if df.empty:
        return ChatResponse(
            message="No data found for your question.",
            sql_query=sql,
            columns=list(df.columns),
            rows=[],
            row_count=0,
        )

    # ── Build chart ───────────────────────────────────────────────────────────
    chart, chart_type = _build_chart(df)

    # ── Compose summary message ───────────────────────────────────────────────
    row_word  = "row" if len(df) == 1 else "rows"
    agent_text = " ".join(agent_result["text"]).strip()
    # Filter out internal status messages from the agent
    skip_phrases = ("processing your request", "no similar patterns", "saved to memory", "response complete", "tool completed successfully", "tool completed", "searching memory", "similar patterns found")
    clean_texts = [
        t for t in agent_result["text"]
        if not any(p in t.lower() for p in skip_phrases)
    ]
    clean_message = " ".join(clean_texts).strip()
    message = clean_message or (
        f"Found {len(df)} {row_word}."
        + (f" Here is a {chart_type} chart of the results." if chart else "")
    )

    # ── Serialise DataFrame ───────────────────────────────────────────────────
    columns = list(df.columns)
    rows    = df.where(pd.notnull(df), None).values.tolist()

    response = ChatResponse(
        message=message,
        sql_query=sql,
        columns=columns,
        rows=rows,
        row_count=len(df),
        chart=chart,
        chart_type=chart_type,
    )

    # ── Store in cache ────────────────────────────────────────────────────────
    state.query_cache[cache_key] = response.model_dump()

    return response


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Liveness + readiness probe.

    Returns:
      - status: 'ok' or 'degraded'
      - database: 'connected' or error description
      - agent_memory_items: number of seeded Q→SQL pairs in memory
    """
    # Check database
    db_status = "connected"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as exc:
        db_status = f"error: {exc}"

    # Count memory items
    memory_count = 0
    try:
        if state.agent:
            items = await state.agent.agent_memory.search_saved_correct_tool_uses(
                "SELECT", limit=10000
            )
            memory_count = len(items)
    except Exception:
        pass  # memory count failure is non-fatal

    overall = "ok" if db_status == "connected" and state.agent else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        agent_memory_items=memory_count,
    )
