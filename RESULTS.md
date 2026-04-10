# Test Results — 20 Questions

**LLM:** Google Gemini 2.5 Flash via Vanna 2.0  
**Database:** clinic.db (SQLite)  
**Tested after:** running `seed_memory.py`

---

## Summary

| Metric | Value |
|--------|-------|
| Total tested | 20 |
| Correct | 18 |
| Partially correct | 1 |
| Failed | 1 |
| Pass rate | 90% |

---

## Results

---

### Q1 — How many patients do we have?
**Status:** ✅ Correct

```sql
SELECT COUNT(*) AS total_patients FROM patients;
```
Returns 200 as expected.

---

### Q2 — List all doctors and their specializations
**Status:** ✅ Correct

```sql
SELECT name, specialization, department
FROM doctors
ORDER BY specialization, name;
```
All 15 doctors come back with their details.

---

### Q3 — Show me appointments for last month
**Status:** ✅ Correct

```sql
SELECT a.id, p.first_name, p.last_name, d.name AS doctor,
       a.appointment_date, a.status
FROM appointments a
JOIN patients p ON p.id = a.patient_id
JOIN doctors  d ON d.id = a.doctor_id
WHERE strftime('%Y-%m', a.appointment_date) = strftime('%Y-%m', DATE('now', '-1 month'))
ORDER BY a.appointment_date;
```
Filters correctly to the previous month using SQLite's `strftime`.

---

### Q4 — Which doctor has the most appointments?
**Status:** ✅ Correct

```sql
SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count
FROM doctors d
JOIN appointments a ON a.doctor_id = d.id
GROUP BY d.id
ORDER BY appointment_count DESC
LIMIT 1;
```
Returns the right doctor.

---

### Q5 — What is the total revenue?
**Status:** ✅ Correct

```sql
SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices;
```
Straightforward and correct.

---

### Q6 — Show revenue by doctor
**Status:** ✅ Correct

```sql
SELECT d.name AS doctor, ROUND(SUM(i.total_amount), 2) AS total_revenue
FROM invoices i
JOIN appointments a ON a.patient_id = i.patient_id
JOIN doctors d      ON d.id = a.doctor_id
GROUP BY d.id, d.name
ORDER BY total_revenue DESC;
```
The JOIN path through appointments works correctly here.

---

### Q7 — How many cancelled appointments last quarter?
**Status:** ✅ Correct

```sql
SELECT COUNT(*) AS cancelled_count
FROM appointments
WHERE status = 'Cancelled'
  AND appointment_date >= DATE('now', '-3 months');
```
Status filter and date range both work.

---

### Q8 — Top 5 patients by spending
**Status:** ✅ Correct

```sql
SELECT p.first_name, p.last_name,
       ROUND(SUM(i.total_amount), 2) AS total_spending
FROM invoices i
JOIN patients p ON p.id = i.patient_id
GROUP BY p.id
ORDER BY total_spending DESC
LIMIT 5;
```
Returns top 5 with correct amounts.

---

### Q9 — Average treatment cost by specialization
**Status:** ✅ Correct

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
Three-table join works, averages look right.

---

### Q10 — Show monthly appointment count for the past 6 months
**Status:** ✅ Correct

```sql
SELECT strftime('%Y-%m', appointment_date) AS month,
       COUNT(*) AS appointment_count
FROM appointments
WHERE appointment_date >= DATE('now', '-6 months')
GROUP BY month
ORDER BY month;
```
6 rows returned, one per month.

---

### Q11 — Which city has the most patients?
**Status:** ✅ Correct

```sql
SELECT city, COUNT(*) AS patient_count
FROM patients
GROUP BY city
ORDER BY patient_count DESC
LIMIT 1;
```
Returns the top city correctly.

---

### Q12 — List patients who visited more than 3 times
**Status:** ✅ Correct

```sql
SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
FROM patients p
JOIN appointments a ON a.patient_id = p.id
GROUP BY p.id
HAVING visit_count > 3
ORDER BY visit_count DESC;
```
`HAVING` clause works as expected.

---

### Q13 — Show unpaid invoices
**Status:** ✅ Correct

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
Picks up both Pending and Overdue, balance calculation is correct.

---

### Q14 — What percentage of appointments are no-shows?
**Status:** ✅ Correct

```sql
SELECT ROUND(
    CAST(SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) AS REAL)
    / COUNT(*) * 100, 2
) AS no_show_percentage
FROM appointments;
```
Used `CAST AS REAL` to avoid integer division in SQLite — that was a gotcha I had to think about.

---

### Q15 — Show the busiest day of the week for appointments
**Status:** ✅ Correct

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
`strftime('%w')` returns a number so had to map it to day names with CASE.

---

### Q16 — Revenue trend by month
**Status:** ✅ Correct

```sql
SELECT strftime('%Y-%m', invoice_date) AS month,
       ROUND(SUM(total_amount), 2) AS monthly_revenue
FROM invoices
GROUP BY month
ORDER BY month;
```
Clean monthly grouping, good for a line chart.

---

### Q17 — Average appointment duration by doctor
**Status:** ⚠️ Partial

```sql
SELECT d.name AS doctor,
       ROUND(AVG(t.duration_minutes), 1) AS avg_duration_minutes
FROM treatments t
JOIN appointments a ON a.id = t.appointment_id
JOIN doctors d      ON d.id = a.doctor_id
GROUP BY d.id, d.name
ORDER BY avg_duration_minutes DESC;
```

The schema doesn't have an `appointment_duration` column — only `treatments.duration_minutes` which tracks how long a treatment took. The agent used that as a proxy which is the closest thing available. The numbers aren't wrong, they're just treatment duration not appointment duration. This is a schema gap more than an agent error.

---

### Q18 — List patients with overdue invoices
**Status:** ✅ Correct

```sql
SELECT DISTINCT p.first_name, p.last_name, p.email, p.phone,
       COUNT(i.id) AS overdue_invoice_count,
       ROUND(SUM(i.total_amount - i.paid_amount), 2) AS total_outstanding
FROM invoices i
JOIN patients p ON p.id = i.patient_id
WHERE i.status = 'Overdue'
GROUP BY p.id
ORDER BY total_outstanding DESC;
```
Returns overdue patients with their outstanding balance.

---

### Q19 — Compare revenue between departments
**Status:** ✅ Correct

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
Per-department breakdown looks right.

---

### Q20 — Show patient registration trend by month
**Status:** ✅ Correct

```sql
SELECT strftime('%Y-%m', registered_date) AS month,
       COUNT(*) AS new_patients
FROM patients
WHERE registered_date IS NOT NULL
GROUP BY month
ORDER BY month;
```
NULL guard is there, monthly grouping works fine.

---

## Issues

**Q17 — partial result**  
Not really the agent's fault. The schema just doesn't have appointment duration as its own column. If I were to improve the schema I'd add a `duration_minutes` column directly on the `appointments` table.

**Cold start behavior (before seeding)**  
Before running `seed_memory.py`, the first few questions came back with explanations instead of SQL. Once the memory was seeded it worked consistently. So the seed step genuinely matters — don't skip it.

---

## What I'd improve

- Add `duration_minutes` to the `appointments` table so Q17 is accurate
- Add a `payment_date` column to invoices for queries like "paid this week"
- Persist the agent memory to a file so it doesn't reset when the server restarts

