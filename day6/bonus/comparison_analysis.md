# NL2SQL vs Cortex Analyst — Sigma DataTech Evaluation
Team: Anirban
Date: 2026-05-25

## 5-Question Head-to-Head Results

| # | Question | Module 2 SQL Correct? | Cortex SQL Correct? | Module 2 Time | Cortex Time |
|---|----------|------------------------|----------------------|---------------|-------------|
| 1 | Total transaction count | YES | YES | ~8s (est.) | ~15.0s |
| 2 | Failed transaction count | YES | YES | ~7.7s | ~14.3s |
| 3 | Highest revenue merchant | YES | YES | ~6.7s | ~20.8s |
| 4 | Failure rate by payment method | YES | YES | ~5.8s | ~26.0s |
| 5 | Total revenue (with COMPLETED filter) | YES | YES | ~6.5s | ~16.0s |

Note: Module 2 audit logging recorded completion timestamps but not elapsed seconds. Times above are estimated from timestamp gaps in `day6/lab/nl2sql_audit.json`; Cortex times come from `elapsed_seconds` in `day6/bonus/cortex_results.json`.

## Observations

### Where Module 2 NL2SQL was better:
Module 2 was faster in this run and produced more presentation-ready SQL for question 4, including total transactions, failed transactions, and a rounded failure-rate percentage. It also demonstrated a useful safety guard by rejecting the malicious `DROP TABLE fact_transactions` prompt before execution.

### Where Cortex Analyst was better:
Cortex required less custom application logic once the semantic model existed: the lab only needed the YAML model and an API call, instead of maintaining the full Python prompt, validation, execution, and answer-generation pipeline. It also keeps the governed semantic layer close to Snowflake, which is a better long-term fit for controlled self-serve analytics.

### Business Rule Accuracy
Question 5 is the critical test — revenue must only count COMPLETED transactions. Both systems applied this rule correctly.

- Module 2: Yes. It used `WHERE STATUS = 'COMPLETED'` for total revenue, and used `CASE WHEN T.STATUS='COMPLETED' THEN T.AMOUNT ELSE 0 END` for highest-revenue merchant.
- Cortex: Yes. It generated SQL with `WHERE STATUS = 'COMPLETED'`, consistent with the revenue metric/business rule in the semantic model.

## Your Recommendation

Your recommendation: Hybrid approach

Reason: I would deploy Cortex Analyst as the production self-serve analytics foundation because the semantic model is easier to govern, maintain, and scale, and it keeps data residency inside Snowflake. I would keep the Module 2 NL2SQL pattern as a complementary control layer for safety validation, audit logging, custom fallback behavior, and user-friendly result summaries where the product experience needs more orchestration.
