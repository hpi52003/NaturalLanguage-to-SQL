"""
seed_memory.py
--------------
Pre-seeds the Vanna 2.0 DemoAgentMemory with 15+ verified question→SQL pairs
so the agent starts with domain knowledge and doesn't have to learn from zero.

Run ONCE after setup_database.py:
    python seed_memory.py

Covers all required categories:
  - Patient queries (count, list, filter by city / gender)
  - Doctor queries (appointments per doctor, busiest doctor)
  - Appointment queries (by status, by month, by doctor)
  - Financial queries (revenue, unpaid invoices, average cost)
  - Time-based queries (last 3 months, monthly trends)
"""

import asyncio
from vanna_setup import build_agent
from vanna.core.tool import ToolContext # type: ignore
from vanna.core.user import User # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
# Verified Q → SQL pairs (all tested against clinic.db schema)
# ─────────────────────────────────────────────────────────────────────────────

QA_PAIRS = [
    # ── Patient queries ───────────────────────────────────────────────────────
    (
        "How many patients do we have?",
        "SELECT COUNT(*) AS total_patients FROM patients;",
    ),
    (
        "List all patients with their city",
        """SELECT first_name, last_name, city
           FROM patients
           ORDER BY last_name, first_name;""",
    ),
    (
        "Show all female patients",
        """SELECT first_name, last_name, city, date_of_birth
           FROM patients
           WHERE gender = 'F'
           ORDER BY last_name;""",
    ),
    (
        "Which city has the most patients?",
        """SELECT city, COUNT(*) AS patient_count
           FROM patients
           GROUP BY city
           ORDER BY patient_count DESC
           LIMIT 1;""",
    ),
    (
        "Show patients registered in the last 6 months",
        """SELECT first_name, last_name, registered_date, city
           FROM patients
           WHERE registered_date >= DATE('now', '-6 months')
           ORDER BY registered_date DESC;""",
    ),
    # ── Doctor queries ────────────────────────────────────────────────────────
    (
        "List all doctors and their specializations",
        """SELECT name, specialization, department
           FROM doctors
           ORDER BY specialization, name;""",
    ),
    (
        "Which doctor has the most appointments?",
        """SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count
           FROM doctors d
           JOIN appointments a ON a.doctor_id = d.id
           GROUP BY d.id, d.name, d.specialization
           ORDER BY appointment_count DESC
           LIMIT 1;""",
    ),
    (
        "Show number of appointments per doctor",
        """SELECT d.name, d.specialization, COUNT(a.id) AS total_appointments
           FROM doctors d
           LEFT JOIN appointments a ON a.doctor_id = d.id
           GROUP BY d.id, d.name, d.specialization
           ORDER BY total_appointments DESC;""",
    ),
    # ── Appointment queries ───────────────────────────────────────────────────
    (
        "Show appointments for last month",
        """SELECT a.id, p.first_name, p.last_name, d.name AS doctor,
                  a.appointment_date, a.status
           FROM appointments a
           JOIN patients p ON p.id = a.patient_id
           JOIN doctors  d ON d.id = a.doctor_id
           WHERE strftime('%Y-%m', a.appointment_date)
                 = strftime('%Y-%m', DATE('now', '-1 month'))
           ORDER BY a.appointment_date;""",
    ),
    (
        "How many cancelled appointments last quarter?",
        """SELECT COUNT(*) AS cancelled_count
           FROM appointments
           WHERE status = 'Cancelled'
             AND appointment_date >= DATE('now', '-3 months');""",
    ),
    (
        "Show monthly appointment count for the past 6 months",
        """SELECT strftime('%Y-%m', appointment_date) AS month,
                  COUNT(*) AS appointment_count
           FROM appointments
           WHERE appointment_date >= DATE('now', '-6 months')
           GROUP BY month
           ORDER BY month;""",
    ),
    # ── Financial queries ─────────────────────────────────────────────────────
    (
        "What is the total revenue?",
        "SELECT SUM(total_amount) AS total_revenue FROM invoices;",
    ),
    (
        "Show revenue by doctor",
        """SELECT d.name AS doctor, SUM(i.total_amount) AS total_revenue
           FROM invoices i
           JOIN appointments a ON a.patient_id = i.patient_id
           JOIN doctors d      ON d.id = a.doctor_id
           GROUP BY d.id, d.name
           ORDER BY total_revenue DESC;""",
    ),
    (
        "Show unpaid invoices",
        """SELECT p.first_name, p.last_name, i.total_amount,
                  i.paid_amount,
                  ROUND(i.total_amount - i.paid_amount, 2) AS balance_due,
                  i.status, i.invoice_date
           FROM invoices i
           JOIN patients p ON p.id = i.patient_id
           WHERE i.status IN ('Pending', 'Overdue')
           ORDER BY i.status, balance_due DESC;""",
    ),
    (
        "Top 5 patients by total spending",
        """SELECT p.first_name, p.last_name,
                  ROUND(SUM(i.total_amount), 2) AS total_spending
           FROM invoices i
           JOIN patients p ON p.id = i.patient_id
           GROUP BY p.id, p.first_name, p.last_name
           ORDER BY total_spending DESC
           LIMIT 5;""",
    ),
    (
        "Average treatment cost by specialization",
        """SELECT d.specialization,
                  ROUND(AVG(t.cost), 2) AS avg_cost,
                  COUNT(t.id)           AS treatment_count
           FROM treatments t
           JOIN appointments a ON a.id = t.appointment_id
           JOIN doctors d      ON d.id = a.doctor_id
           GROUP BY d.specialization
           ORDER BY avg_cost DESC;""",
    ),
    (
        "Revenue trend by month",
        """SELECT strftime('%Y-%m', invoice_date) AS month,
                  ROUND(SUM(total_amount), 2)      AS monthly_revenue
           FROM invoices
           GROUP BY month
           ORDER BY month;""",
    ),
    (
        "List patients who visited more than 3 times",
        """SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
           FROM patients p
           JOIN appointments a ON a.patient_id = p.id
           GROUP BY p.id, p.first_name, p.last_name
           HAVING visit_count > 3
           ORDER BY visit_count DESC;""",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Seeding logic — fixed for Vanna 2.0.2
# ─────────────────────────────────────────────────────────────────────────────

async def seed(agent):
    """
    Insert Q→SQL pairs into DemoAgentMemory using the correct
    Vanna 2.0.2 API: save_tool_usage(question, tool_name, args, context).
    """
    memory = agent.agent_memory

    # Build a ToolContext — required by Vanna 2.0.2
    user = User(
        id="seed-user",
        email="seed@clinic.local",
        group_memberships=["user"],
    )
    ctx = ToolContext(
        user=user,
        conversation_id="seed-session",
        request_id="seed-session",
        agent_memory=memory,
    )

    for i, (question, sql) in enumerate(QA_PAIRS, start=1):
        await memory.save_tool_usage(
            question=question,
            tool_name="run_sql",
            args={"sql": sql.strip()},
            context=ctx,
            success=True,
        )
        print(f"  [{i:02d}/{len(QA_PAIRS)}] ✓  {question}")

    print(f"\n✅  Seeded {len(QA_PAIRS)} Q→SQL pairs into agent memory.")
    print(f"   Agent is ready — start the server with:")
    print(f"   uvicorn main:app --port 8000 --reload")


def main():
    print("🌱  Seeding Vanna 2.0 agent memory ...\n")
    agent = build_agent()
    asyncio.run(seed(agent))


if __name__ == "__main__":
    main()