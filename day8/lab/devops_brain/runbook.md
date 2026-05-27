# Pipeline Overview

This pipeline processes transaction data, transforming it from bronze to silver and finally to gold tables. It runs to ensure that transaction data is cleaned, enriched, and aggregated for reporting purposes. If this pipeline stops, downstream reporting and analytics will be impacted.

## Pipeline Steps

1. **get_connection()** - Establishes a connection to the DuckDB database.
2. **setup_tables(con)** - Sets up the necessary tables in the database.
3. **load_merchants(con)** - Loads merchant data into the `merchants` table.
4. **load_bronze(con, transactions)** - Loads raw transaction data into the `bronze_transactions` table.
5. **transform_bronze_to_silver(transactions, merchants)** - Transforms bronze transactions into silver transactions.
6. **load_silver(con, silver_rows)** - Loads transformed transactions into the `silver_transactions` table.
7. **compute_merchant_performance(silver_rows)** - Computes merchant performance metrics.
8. **compute_daily_summary(silver_rows)** - Computes daily summary metrics.
9. **load_gold(con, merchant_perf, daily_summary)** - Loads merchant performance and daily summary into gold tables.

## Schedule / Trigger

This pipeline runs every night at 2 AM UTC via a cron job.

## Failure Modes

1. **Database Connection Failure** - Root cause: Network issue or database downtime. Symptom: Pipeline logs show "Connection refused".
2. **Table Creation Failure** - Root cause: SQL syntax error. Symptom: Pipeline logs show "Syntax error".
3. **Merchant Data Load Failure** - Root cause: Corrupted merchant data. Symptom: Pipeline logs show "Data load failed".
4. **Bronze Data Load Failure** - Root cause: Corrupted transaction data. Symptom: Pipeline logs show "Data load failed".
5. **Silver Transformation Failure** - Root cause: Missing merchant data for a transaction. Symptom: Pipeline logs show "Transformation failed".

## Recovery Actions

1. **Database Connection Failure**
   - Check network connectivity.
   - Restart the database service.
   - Retry the pipeline.
2. **Table Creation Failure**
   - Review and correct the SQL syntax.
   - Rerun the `setup_tables(con)` function.
3. **Merchant Data Load Failure**
   - Validate the merchant data for corruption.
   - Correct the data and rerun the `load_merchants(con)` function.
4. **Bronze Data Load Failure**
   - Validate the transaction data for corruption.
   - Correct the data and rerun the `load_bronze(con, transactions)` function.
5. **Silver Transformation Failure**
   - Ensure all merchants are present in the `merchants` table.
   - Rerun the `transform_bronze_to_silver(transactions, merchants)` function.

## Known Bugs

- Hardcoded AWS credentials in the code.
- Lack of null handling in `transform_bronze_to_silver` function.

## Escalation Contacts

1. **On-call DE:** Priya Nair (priya.nair@sigmadatatech.in, +91-98400-11111)
2. **Tech Lead:** Arjun Mehta (arjun.mehta@sigmadatatech.in)
3. **Platform Manager:** Kavya Reddy (kavya.reddy@sigmadatatech.in)

## Data Quality Checks

After a successful run, verify the following:

- `silver_transactions` table has the expected number of records.
- `gold_merchant_performance` table has today's date.
- `gold_daily_summary` table has today's date.
- Check for any "DIRTY" flags in the `quality_flag` column of `silver_transactions`.