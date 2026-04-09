"""
setup_database.py
-----------------
Creates clinic.db with 5 tables and inserts all realistic dummy data.

Run:  python setup_database.py
Out:  clinic.db  +  printed summary
"""

import sqlite3
import random
from datetime import datetime, timedelta, date

# ── Reproducible seed so the data is the same every run ──────────────────────
random.seed(42)
DB_PATH = "clinic.db"


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def rand_date_past(months: int = 12) -> date:
    """Random calendar date within the last `months` months."""
    today = datetime.today()
    earliest = today - timedelta(days=months * 30)
    offset = random.randint(0, (today - earliest).days)
    return (earliest + timedelta(days=offset)).date()


def rand_datetime_past(months: int = 12) -> datetime:
    """Random datetime within the last `months` months, clamped to clinic hours."""
    today = datetime.today()
    earliest = today - timedelta(days=months * 30)
    offset_sec = random.randint(0, int((today - earliest).total_seconds()))
    dt = earliest + timedelta(seconds=offset_sec)
    # Clinic open 08:00 – 18:00
    return dt.replace(
        hour=random.randint(8, 17),
        minute=random.choice([0, 15, 30, 45]),
        second=0,
        microsecond=0,
    )


def nullable(value, null_prob: float = 0.15):
    """Return None with probability `null_prob`, else return the value."""
    return None if random.random() < null_prob else value


def rand_phone() -> str:
    return f"+91-{random.randint(7000000000, 9999999999)}"


# ─────────────────────────────────────────────────────────────────────────────
# Reference data pools
# ─────────────────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Aditya", "Akash", "Amara", "Amelia", "Ananya", "Arjun", "Aryan",
    "Asha", "Bhavya", "Carlos", "Deepa", "Dev", "Diana", "Elena", "Farhan",
    "Fatima", "Gaurav", "Ishaan", "James", "Jaya", "Kiran", "Lakshmi", "Lena",
    "Manish", "Maya", "Meera", "Mohammed", "Nadia", "Neha", "Nikhil", "Nina",
    "Omar", "Pooja", "Priya", "Rahul", "Raj", "Rakesh", "Rania", "Ravi",
    "Rohan", "Sahil", "Sakshi", "Samira", "Sara", "Shilpa", "Shivam", "Sneha",
    "Sofia", "Sunita", "Tanvi", "Tara", "Uma", "Usman", "Varsha", "Vikram",
    "Vijay", "Vivaan", "Yasmin", "Zara",
]

LAST_NAMES = [
    "Ahmed", "Ali", "Bhat", "Chandra", "Choudhary", "Das", "Desai", "Ghosh",
    "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Khan", "Kumar", "Malhotra",
    "Mehta", "Mishra", "Nair", "Patel", "Pillai", "Rao", "Reddy", "Saxena",
    "Shah", "Sharma", "Singh", "Sinha", "Srivastava", "Verma",
]

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
]

SPECIALIZATIONS = ["Dermatology", "Cardiology", "Orthopedics", "General", "Pediatrics"]

DEPT_MAP = {
    "Dermatology": "Skin & Hair",
    "Cardiology":  "Heart & Vascular",
    "Orthopedics": "Bone & Joint",
    "General":     "General Medicine",
    "Pediatrics":  "Child Health",
}

DOCTOR_NAMES = [
    "Dr. Arvind Mehta",  "Dr. Priya Sharma",  "Dr. Sunita Rao",
    "Dr. Ramesh Iyer",   "Dr. Kavita Pillai", "Dr. Sanjay Gupta",
    "Dr. Nisha Patel",   "Dr. Vikram Singh",  "Dr. Anita Desai",
    "Dr. Karthik Nair",  "Dr. Leela Verma",   "Dr. Rajan Bhat",
    "Dr. Meena Joshi",   "Dr. Dilip Reddy",   "Dr. Fatima Khan",
]

APPT_STATUSES   = ["Scheduled", "Completed", "Cancelled", "No-Show"]
APPT_WEIGHTS    = [0.15,         0.55,         0.20,         0.10]

INV_STATUSES    = ["Paid", "Pending", "Overdue"]
INV_WEIGHTS     = [0.55,   0.25,      0.20]

TREATMENT_NAMES = [
    "Consultation", "Blood Test", "X-Ray", "ECG", "Ultrasound",
    "Skin Biopsy", "Physiotherapy Session", "Vaccination",
    "Allergy Test", "MRI Scan", "Cardiac Stress Test",
    "Diabetes Screening", "Vision Test", "Wound Dressing",
    "Minor Surgery", "Nebulization", "IV Infusion",
    "Nutritional Counseling", "Sleep Study", "Bone Density Scan",
]

APPT_NOTES = [
    "Follow-up required", "Referred to specialist",
    "Patient reports improvement", "Routine check",
    "First visit", "Urgent consultation", "Lab results pending",
    "Prescription renewed", "Post-surgery review",
]


# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS treatments;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS doctors;
DROP TABLE IF EXISTS patients;

CREATE TABLE patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT    NOT NULL,
    last_name       TEXT    NOT NULL,
    email           TEXT,
    phone           TEXT,
    date_of_birth   DATE,
    gender          TEXT    CHECK(gender IN ('M', 'F')),
    city            TEXT,
    registered_date DATE
);

CREATE TABLE doctors (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    specialization TEXT,
    department     TEXT,
    phone          TEXT
);

CREATE TABLE appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER NOT NULL REFERENCES patients(id),
    doctor_id        INTEGER NOT NULL REFERENCES doctors(id),
    appointment_date DATETIME,
    status           TEXT CHECK(status IN ('Scheduled','Completed','Cancelled','No-Show')),
    notes            TEXT
);

CREATE TABLE treatments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id   INTEGER NOT NULL REFERENCES appointments(id),
    treatment_name   TEXT,
    cost             REAL,
    duration_minutes INTEGER
);

CREATE TABLE invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL REFERENCES patients(id),
    invoice_date DATE,
    total_amount REAL,
    paid_amount  REAL,
    status       TEXT CHECK(status IN ('Paid','Pending','Overdue'))
);
"""


# ─────────────────────────────────────────────────────────────────────────────
# Insertion helpers
# ─────────────────────────────────────────────────────────────────────────────

def insert_doctors(cur) -> list[int]:
    # 3 doctors per specialization → exactly 15
    specs = [s for s in SPECIALIZATIONS for _ in range(3)]
    rows = []
    for name, spec in zip(DOCTOR_NAMES, specs):
        rows.append((name, spec, DEPT_MAP[spec], nullable(rand_phone(), 0.10)))
    cur.executemany(
        "INSERT INTO doctors (name, specialization, department, phone) VALUES (?,?,?,?)",
        rows,
    )
    return [r[0] for r in cur.execute("SELECT id FROM doctors").fetchall()]


def insert_patients(cur) -> list[int]:
    seen_emails: set[str] = set()
    rows = []
    for _ in range(200):
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)

        # unique email or NULL
        email = None
        if random.random() > 0.12:
            base = f"{fn.lower()}.{ln.lower()}"
            candidate = f"{base}{random.randint(1, 999)}@clinic.example.com"
            while candidate in seen_emails:
                candidate = f"{base}{random.randint(1, 9999)}@clinic.example.com"
            seen_emails.add(candidate)
            email = candidate

        phone   = nullable(rand_phone(), 0.12)
        age_d   = random.randint(5 * 365, 80 * 365)
        dob     = (datetime.today() - timedelta(days=age_d)).date().isoformat()
        gender  = random.choice(["M", "F"])
        city    = random.choice(CITIES)
        reg     = rand_date_past(14).isoformat()   # up to 14 months back so some predate appts

        rows.append((fn, ln, email, phone, dob, gender, city, reg))

    cur.executemany(
        """INSERT INTO patients
           (first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
           VALUES (?,?,?,?,?,?,?,?)""",
        rows,
    )
    return [r[0] for r in cur.execute("SELECT id FROM patients").fetchall()]


def insert_appointments(cur, patient_ids, doctor_ids) -> tuple[list[int], list[int]]:
    # Skew: 20 % of patients get ~60 % of appointments (frequent visitors)
    frequent_pts = random.sample(patient_ids, k=max(1, len(patient_ids) // 5))
    patient_pool = frequent_pts * 4 + list(patient_ids)

    # Skew: first 5 doctors are "busier"
    busy_docs  = doctor_ids[:5]
    doctor_pool = busy_docs * 3 + list(doctor_ids)

    rows = []
    for _ in range(500):
        pid    = random.choice(patient_pool)
        did    = random.choice(doctor_pool)
        dt     = rand_datetime_past(12).strftime("%Y-%m-%d %H:%M")
        status = random.choices(APPT_STATUSES, weights=APPT_WEIGHTS, k=1)[0]
        notes  = nullable(random.choice(APPT_NOTES), 0.30)
        rows.append((pid, did, dt, status, notes))

    cur.executemany(
        "INSERT INTO appointments (patient_id, doctor_id, appointment_date, status, notes) VALUES (?,?,?,?,?)",
        rows,
    )

    all_rows       = cur.execute("SELECT id, status FROM appointments").fetchall()
    all_ids        = [r[0] for r in all_rows]
    completed_ids  = [r[0] for r in all_rows if r[1] == "Completed"]
    return all_ids, completed_ids


def insert_treatments(cur, completed_ids: list[int]):
    """350 treatments, every one linked to a Completed appointment only."""
    if not completed_ids:
        return

    # ~300 unique completed appointments + ~50 extras for multi-treatment visits
    base   = random.sample(completed_ids, k=min(300, len(completed_ids)))
    extras = random.choices(completed_ids, k=50)

    rows = []
    for appt_id in base + extras:
        rows.append((
            appt_id,
            random.choice(TREATMENT_NAMES),
            round(random.uniform(50, 5000), 2),
            random.randint(10, 120),
        ))

    cur.executemany(
        "INSERT INTO treatments (appointment_id, treatment_name, cost, duration_minutes) VALUES (?,?,?,?)",
        rows,
    )


def insert_invoices(cur, patient_ids: list[int]):
    rows = []
    for _ in range(300):
        pid    = random.choice(patient_ids)
        idate  = rand_date_past(12).isoformat()
        total  = round(random.uniform(100, 8000), 2)
        status = random.choices(INV_STATUSES, weights=INV_WEIGHTS, k=1)[0]

        if status == "Paid":
            paid = total
        elif status == "Pending":
            paid = round(random.uniform(0, total * 0.5), 2)
        else:  # Overdue
            paid = round(random.uniform(0, total * 0.3), 2)

        rows.append((pid, idate, total, paid, status))

    cur.executemany(
        "INSERT INTO invoices (patient_id, invoice_date, total_amount, paid_amount, status) VALUES (?,?,?,?,?)",
        rows,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("🏥  Building clinic.db ...")

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    cur = conn.cursor()

    print("  → Inserting 15 doctors ...")
    doctor_ids = insert_doctors(cur)

    print("  → Inserting 200 patients ...")
    patient_ids = insert_patients(cur)

    print("  → Inserting 500 appointments ...")
    _, completed_ids = insert_appointments(cur, patient_ids, doctor_ids)

    print("  → Inserting ~350 treatments (Completed only) ...")
    insert_treatments(cur, completed_ids)

    print("  → Inserting 300 invoices ...")
    insert_invoices(cur, patient_ids)

    conn.commit()

    # ── Summary ──────────────────────────────────────────────────────────────
    def count(table):
        return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    completed_n = cur.execute(
        "SELECT COUNT(*) FROM appointments WHERE status='Completed'"
    ).fetchone()[0]
    overdue_n = cur.execute(
        "SELECT COUNT(*) FROM invoices WHERE status='Overdue'"
    ).fetchone()[0]

    print(f"\n✅  Done!")
    print(f"   Created {count('patients')} patients")
    print(f"   Created {count('doctors')} doctors")
    print(f"   Created {count('appointments')} appointments  (Completed: {completed_n})")
    print(f"   Created {count('treatments')} treatments")
    print(f"   Created {count('invoices')} invoices  (Overdue: {overdue_n})")
    print(f"\n   📁  Database saved → {DB_PATH}")

    conn.close()


if __name__ == "__main__":
    main()
