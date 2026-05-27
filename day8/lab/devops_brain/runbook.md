# Pipeline Overview

This pipeline processes transaction data, transforming it into a cleaned and enriched format for further analysis. It runs to ensure that the data warehouse is up-to-date with the latest transaction information. If this pipeline stops, downstream analytics and reporting will be impacted, leading to outdated insights.

## Pipeline Steps

1. Connect to the DuckDB database using `get_connection()`.
2. Set up necessary tables in the database using `setup_tables(con)`.
3. Load merchant data into the `merchants` table using `load_merchants(con)`.
4. Load raw transaction data into the `bronze_transactions` table using `load_bronze(con, transactions)`.
5. Transform raw transactions into enriched transactions and load them into the `silver_transactions` table using `transform_bronze_to_silver(transactions, merchants)` and `load_silver(con, silver_rows)`.
6. Compute merchant performance metrics and load them into the `gold_merchant_performance` table using `compute_merchant_performance(silver_rows)` and `load_gold(con, merchant_perf, daily_summary)`.
7. Compute daily summary metrics and load them into the `gold_daily_summary` table using `compute_daily_summary(silver_rows)` and `load_gold(con, merchant_perf, daily_summary)`.

## Schedule / Trigger

This pipeline runs every night at 2 AM using a cron job.

## Failure Modes

1. **Database Connection Failure**
   - **Root Cause:** Incorrect database path or permissions.
   - **Symptom:** Pipeline fails to start.
2. **Table Creation Failure**
   - **Root Cause:** Syntax error in SQL statements.
   - **Symptom:** Pipeline fails during table setup.
3. **Merchant Data Load Failure**
   - **Root Cause:** Corrupt or missing merchant data.
   - **Symptom:** Empty `merchants` table.
4. **Bronze Transaction Load Failure**
   - **Root Cause:** Corrupt or missing transaction data.
   - **Symptom:** Empty `bronze_transactions` table.
5. **Silver Transaction Transformation Failure**
   - **Root Cause:** Incompatible data types or missing fields.
   - **Symptom:** Empty `silver_transactions` table.

## Recovery Actions

1. **Database Connection Failure**
   - Verify the `DB_PATH` and ensure the database file exists.
   - Check file permissions.
   - Restart the pipeline.
2. **Table Creation Failure**
   - Review and correct the SQL statements in `setup_tables(con)`.
   - Restart the pipeline.
3. **Merchant Data Load Failure**
   - Verify the integrity of the `MERCHANTS` data.
   - Restart the pipeline.
4. **Bronze Transaction Load Failure**
   - Verify the integrity of the `TRANSACTIONS_CLEAN` and `TRANSACTIONS_DIRTY` data.
   - Restart the pipeline.
5. **Silver Transaction Transformation Failure**
   - Review the data types and ensure all required fields are present in the transaction data.
   - Restart the pipeline.

## Known Bugs

- Hardcoded AWS credentials in the source code.
- Lack of null handling in `transform_bronze_to_silver()` function.

## Escalation Contacts

1. **On-call DE:** Priya Nair (priya.nair@sigmadatatech.in, +91-98400-11111)
2. **Tech Lead:** Arjun Mehta (arjun.mehta@sigmadatatech.in)
3. **Platform Manager:** Kavya Reddy (kavya.reddy@sigmadatatech.in)

## Data Quality Checks

After a successful run, verify the following:

- The `bronze_transactions` table contains the expected number of records.
- The `silver_transactions` table contains enriched transaction data with no duplicates.
- The `gold_merchant_performance` table has up-to-date merchant performance metrics.
- The `gold_daily_summary` table has up-to-date daily summary metrics.