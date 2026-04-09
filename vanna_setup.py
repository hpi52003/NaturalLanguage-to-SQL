"""
vanna_setup.py
--------------
Initializes the Vanna 2.0 Agent for the clinic NL2SQL system.

Components wired here:
  - GeminiLlmService        → LLM brain (gemini-2.5-flash)
  - SqliteRunner            → executes SQL against clinic.db
  - ToolRegistry            → RunSqlTool, VisualizeDataTool, memory tools
  - DemoAgentMemory         → in-memory learning store (replaces ChromaDB)
  - ClinicUserResolver      → identifies every caller as a default 'user'
  - Agent                   → ties all components together

Usage (imported by main.py and seed_memory.py):
    from vanna_setup import build_agent
    agent = build_agent()
"""

import os
from dotenv import load_dotenv

# ── Vanna 2.0 imports ─────────────────────────────────────────────────────────
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
)
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.google import GeminiLlmService

load_dotenv()  # reads GOOGLE_API_KEY from .env

DB_PATH = "clinic.db"

# ─────────────────────────────────────────────────────────────────────────────
# Schema description injected into the system prompt so the LLM always knows
# the full table structure — this dramatically improves SQL accuracy.
# ─────────────────────────────────────────────────────────────────────────────

CLINIC_SCHEMA_CONTEXT = """
You are an expert SQL assistant for a clinic management system.
The SQLite database (clinic.db) has these tables:

TABLE patients (
    id              INTEGER PRIMARY KEY,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,           -- nullable
    phone           TEXT,           -- nullable
    date_of_birth   DATE,
    gender          TEXT,           -- 'M' or 'F'
    city            TEXT,
    registered_date DATE
);

TABLE doctors (
    id             INTEGER PRIMARY KEY,
    name           TEXT,
    specialization TEXT,            -- Dermatology | Cardiology | Orthopedics | General | Pediatrics
    department     TEXT,
    phone          TEXT             -- nullable
);

TABLE appointments (
    id               INTEGER PRIMARY KEY,
    patient_id       INTEGER,       -- FK → patients.id
    doctor_id        INTEGER,       -- FK → doctors.id
    appointment_date DATETIME,      -- format: YYYY-MM-DD HH:MM
    status           TEXT,          -- Scheduled | Completed | Cancelled | No-Show
    notes            TEXT           -- nullable
);

TABLE treatments (
    id               INTEGER PRIMARY KEY,
    appointment_id   INTEGER,       -- FK → appointments.id  (only Completed appointments)
    treatment_name   TEXT,
    cost             REAL,          -- between 50 and 5000
    duration_minutes INTEGER
);

TABLE invoices (
    id           INTEGER PRIMARY KEY,
    patient_id   INTEGER,           -- FK → patients.id
    invoice_date DATE,
    total_amount REAL,
    paid_amount  REAL,
    status       TEXT               -- Paid | Pending | Overdue
);

Important rules:
- Always use SELECT only. Never modify data.
- Use proper JOINs when combining tables.
- For date filtering use SQLite date functions: strftime('%Y-%m', appointment_date).
- For percentage calculations use CAST(... AS REAL) to avoid integer division.
- Alias all computed columns clearly (e.g., AS total_revenue).
"""


# ─────────────────────────────────────────────────────────────────────────────
# User resolver — all requests treated as a single default 'user'
# (In production you would extract identity from cookies / JWT)
# ─────────────────────────────────────────────────────────────────────────────

class ClinicUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(
            id="clinic-default-user",
            email="user@clinic.local",
            group_memberships=["user"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# Builder function — call once at startup
# ─────────────────────────────────────────────────────────────────────────────

def build_agent() -> Agent:
    """
    Construct and return a fully configured Vanna 2.0 Agent.
    Reads GOOGLE_API_KEY from the environment / .env file.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. "
            "Add it to your .env file: GOOGLE_API_KEY=your-key-here"
        )

    # 1. LLM Service — gemini-2.5-flash is stable with Vanna 2.0 tool-calling
    llm = GeminiLlmService(
        api_key=api_key,
        model="gemini-2.5-flash",
    )

    # 2. SQLite runner — points at the clinic database
    sql_runner = SqliteRunner(database_path=DB_PATH)

    # 3. In-memory agent memory (DemoAgentMemory)
    #    Stores successful Q→SQL pairs so the agent improves over the session
    agent_memory = DemoAgentMemory(max_items=1000)

    # 4. Tool registry — register all required tools with access control
    tools = ToolRegistry()

    # SQL execution tool — every user can run SELECT queries
    tools.register_local_tool(
        RunSqlTool(sql_runner=sql_runner),
        access_groups=["user"],
    )

    # Chart generation via Plotly
    tools.register_local_tool(
        VisualizeDataTool(),
        access_groups=["user"],
    )

    # Memory tools — let the agent save & retrieve correct Q→SQL pairs
    tools.register_local_tool(
        SaveQuestionToolArgsTool(),
        access_groups=["user"],
    )
    tools.register_local_tool(
        SearchSavedCorrectToolUsesTool(),
        access_groups=["user"],
    )

    # 5. Agent config — tune behaviour
    config = AgentConfig(
        system_prompt=CLINIC_SCHEMA_CONTEXT,
    )

    # 6. Assemble the Agent
    agent = Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=ClinicUserResolver(),
        agent_memory=agent_memory,
        config=config,
    )

    return agent
