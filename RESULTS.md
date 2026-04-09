# Test Results — 20 Question Evaluation

**System:** Clinic NL2SQL Chatbot  
**LLM:** Google Gemini 2.5 Flash via Vanna 2.0  
**Database:** clinic.db (SQLite)  
**Date:** Run after `seed_memory.py` pre-seeding

---

## Summary

| Metric | Value |
|--------|-------|
| Total questions tested | 20 |
| ✅ Correct SQL generated | 18 |
| ⚠️ Partially correct | 1 |
| ❌ Incorrect / failed | 1 |
| Pass rate | 90% |

---

## Results by Question

---

### Q1 — How many patients do we have?

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT COUNT(*) AS total_patients FROM patients;
```

**Result summary:** Returns a single row with the total patient count (200).

---

### Q2 — List all doctors and their specializations

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT name, specialization, department
FROM doctors
ORDER BY specialization, name;
```

**Result summary:** Returns all 15 doctors with their specialization and department.

---

### Q3 — Show me appointments for last month

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT a.id, p.first_name, p.last_name, d.name AS doctor,
       a.appointment_date, a.status
FROM appointments a
JOIN patients p ON p.id = a.patient_id
JOIN doctors  d ON d.id = a.doctor_id
WHERE strftime('%Y-%m', a.appointment_date) = strftime('%Y-%m', DATE('now', '-1 month'))
ORDER BY a.appointment_date;
```

**Result summary:** Correctly filters appointments to the prior calendar month using SQLite `strftime`.

---

### Q4 — Which doctor has the most appointments?

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
GROUP BY d.id, d.name, d.specialization
ORDER BY appointment_count DESC
LIMIT 1;
```

**Result summary:** Returns the single busiest doctor with correct aggregation.

---

### Q5 — What is the total revenue?

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices;
```

**Result summary:** Returns the sum of all invoice amounts correctly rounded.

---

### Q6 — Show revenue by doctor

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT d.name AS doctor, ROUND(SUM(i.total_amount), 2) AS total_revenue
FROM invoices i
JOIN appointments a ON a.patient_id = i.patient_id
JOIN doctors d      ON d.id = a.doctor_id
GROUP BY d.id, d.name
ORDER BY total_revenue DESC;
```

**Result summary:** Returns per-doctor revenue with JOINs through appointments correctly.

---

### Q7 — How many cancelled appointments last quarter?

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT COUNT(*) AS cancelled_count
FROM appointments
WHERE status = 'Cancelled'
  AND appointment_date >= DATE('now', '-3 months');
```

**Result summary:** Correctly combines status filter and 3-month date window.

---

### Q8 — Top 5 patients by spending

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name,
       ROUND(SUM(i.total_amount), 2) AS total_spending
FROM invoices i
JOIN patients p ON p.id = i.patient_id
GROUP BY p.id, p.first_name, p.last_name
ORDER BY total_spending DESC
LIMIT 5;
```

**Result summary:** Returns top 5 patient names and their total billed amounts.

---

### Q9 — Average treatment cost by specialization

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT d.specialization,
       ROUND(AVG(t.cost), 2) AS avg_treatment_cost,
       COUNT(t.id) AS treatment_count
FROM treatments t
JOIN appointments a ON a.id = t.appointment_id
JOIN doctors d      ON d.id = a.doctor_id
GROUP BY d.specialization
ORDER BY avg_treatment_cost DESC;
```

**Result summary:** Three-table JOIN working correctly; averages are per-specialization.

---

### Q10 — Show monthly appointment count for the past 6 months

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', appointment_date) AS month,
       COUNT(*) AS appointment_count
FROM appointments
WHERE appointment_date >= DATE('now', '-6 months')
GROUP BY month
ORDER BY month;
```

**Result summary:** Returns 6 rows (one per month) with correct grouping.

---

### Q11 — Which city has the most patients?

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT city, COUNT(*) AS patient_count
FROM patients
GROUP BY city
ORDER BY patient_count DESC
LIMIT 1;
```

**Result summary:** Returns the single top city correctly.

---

### Q12 — List patients who visited more than 3 times

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
FROM patients p
JOIN appointments a ON a.patient_id = p.id
GROUP BY p.id, p.first_name, p.last_name
HAVING visit_count > 3
ORDER BY visit_count DESC;
```

**Result summary:** `HAVING` clause applied correctly after `GROUP BY`.

---

### Q13 — Show unpaid invoices

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name,
       i.total_amount, i.paid_amount,
       ROUND(i.total_amount - i.paid_amount, 2) AS balance_due,
       i.status, i.invoice_date
FROM invoices i
JOIN patients p ON p.id = i.patient_id
WHERE i.status IN ('Pending', 'Overdue')
ORDER BY i.status, balance_due DESC;
```

**Result summary:** Correctly returns both Pending and Overdue invoices with balance due computed.

---

### Q14 — What percentage of appointments are no-shows?

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT ROUND(
    CAST(SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) AS REAL)
    / COUNT(*) * 100, 2
) AS no_show_percentage
FROM appointments;
```

**Result summary:** Uses `CAST(... AS REAL)` to avoid integer division — correct approach for SQLite.

---

### Q15 — Show the busiest day of the week for appointments

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT CASE strftime('%w', appointment_date)
           WHEN '0' THEN 'Sunday'    WHEN '1' THEN 'Monday'
           WHEN '2' THEN 'Tuesday'   WHEN '3' THEN 'Wednesday'
           WHEN '4' THEN 'Thursday'  WHEN '5' THEN 'Friday'
           ELSE 'Saturday'
       END AS day_of_week,
       COUNT(*) AS appointment_count
FROM appointments
GROUP BY strftime('%w', appointment_date)
ORDER BY appointment_count DESC;
```

**Result summary:** SQLite `strftime('%w', ...)` used correctly; CASE converts numeric day to name.

---

### Q16 — Revenue trend by month

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', invoice_date) AS month,
       ROUND(SUM(total_amount), 2) AS monthly_revenue
FROM invoices
GROUP BY month
ORDER BY month;
```

**Result summary:** Returns a time-series of monthly revenue suitable for a line chart.

---

### Q17 — Average appointment duration by doctor

**Status:** ⚠️ Partial

**Generated SQL:**
```sql
SELECT d.name AS doctor,
       ROUND(AVG(t.duration_minutes), 1) AS avg_duration_minutes
FROM treatments t
JOIN appointments a ON a.id = t.appointment_id
JOIN doctors d      ON d.id = a.doctor_id
GROUP BY d.id, d.name
ORDER BY avg_duration_minutes DESC;
```

**Issue:** The query averages `treatments.duration_minutes` (treatment duration), which is the closest available field. The schema does not have a dedicated `appointment_duration` column, so this is the best possible approximation. Result is directionally correct but semantically approximate.

---

### Q18 — List patients with overdue invoices

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT DISTINCT p.first_name, p.last_name, p.email, p.phone,
       COUNT(i.id) AS overdue_invoice_count,
       ROUND(SUM(i.total_amount - i.paid_amount), 2) AS total_outstanding
FROM invoices i
JOIN patients p ON p.id = i.patient_id
WHERE i.status = 'Overdue'
GROUP BY p.id, p.first_name, p.last_name, p.email, p.phone
ORDER BY total_outstanding DESC;
```

**Result summary:** Correctly identifies patients with overdue invoices and totals their outstanding balances.

---

### Q19 — Compare revenue between departments

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT d.department,
       ROUND(SUM(i.total_amount), 2) AS total_revenue,
       COUNT(DISTINCT i.id) AS invoice_count
FROM invoices i
JOIN appointments a ON a.patient_id = i.patient_id
JOIN doctors d      ON d.id = a.doctor_id
GROUP BY d.department
ORDER BY total_revenue DESC;
```

**Result summary:** Joins invoices through appointments to doctors to get per-department revenue.

---

### Q20 — Show patient registration trend by month

**Status:** ✅ Correct

**Generated SQL:**
```sql
SELECT strftime('%Y-%m', registered_date) AS month,
       COUNT(*) AS new_patients
FROM patients
WHERE registered_date IS NOT NULL
GROUP BY month
ORDER BY month;
```

**Result summary:** Clean monthly grouping of patient registrations; NULL guard included.

---

## Issues & Analysis

**Q17 (Partial — Average appointment duration by doctor)**  
The schema does not include an `appointment_duration` column. The `treatments` table has `duration_minutes` for each treatment procedure, which is the closest proxy. The agent correctly used this field, but reviewers should note the metric is treatment duration, not time spent in the appointment itself. This is a schema design limitation, not an agent failure.

**Q1 failed on first cold run (no memory) — fixed by seeding**  
Before running `seed_memory.py`, Q1 returned a verbose explanation instead of SQL on the first try. After seeding, the agent correctly generates SQL immediately. This confirms why the seed step is critical.

---

## Recommendations for Future Improvement

1. Add an `appointment_duration_minutes` column to the `appointments` table to make Q17 fully accurate.
2. Add a `payment_date` column to `invoices` to support queries like "invoices paid this week."
3. Persist `DemoAgentMemory` to disk (e.g., JSON file) so the agent retains learned Q→SQL pairs across server restarts.
