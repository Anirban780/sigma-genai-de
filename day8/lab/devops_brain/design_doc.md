# Pipeline Design Document

## What This Pipeline Does
This pipeline ingests transaction data, enriches it with merchant information, and processes it into clean, enriched, and aggregated layers for analytical purposes.

## Data Flow Diagram
```
+---------------------+     +---------------------+     +---------------------+     +-----------------------+
|     Source          |     |     Bronze Layer    |     |     Silver Layer    |     |       Gold Layer      |
| (TRANSACTIONS_CLEAN |     | (bronze_transactions|     | (silver_transactions|     | (gold_merchant_perf.  |
|  & TRANSACTIONS_DIRTY)|     |                     |     |                     |     |  & gold_daily_summary)|
+---------------------+     +---------------------+     +---------------------+     +-----------------------+
    | Load                |     | Load                 |     | Load                 |     | Load                  |
    |                     |     |                      |     |                      |     |                       |
    v                     v                     v                      v                       v
+---------------------+     +---------------------+     +---------------------+     +-----------------------+
|     MERCHANTS       |     | Transform & Enrich  |     | Compute Aggregations|     | Compute Aggregations |
| (MERCHANTS)         |     | (transform_bronze_to|     | (compute_merchant_   |     | (compute_daily_summar |
+---------------------+     |_silver)              |     |  performance)        |     | y)                    |
    |                     |     |                      |     |                      |     |                       |
    v                     v                     v                      v                       v
+---------------------+     +---------------------+     +---------------------+     +-----------------------+
```

## Key Design Decisions
- **Layered Approach**: The pipeline uses a three-layer approach (Bronze, Silver, Gold) to ensure data is progressively cleaned and enriched.
- **Enrichment with Merchant Data**: Merchant information is joined with transaction data to provide context and enrich the dataset.
- **Aggregations for Analysis**: The Gold layer computes key metrics and summaries to facilitate business analysis.
- **Quality Flags**: Transactions are flagged for quality to distinguish between clean and potentially problematic data.

## Known Limitations
- **Single Source of Transactions**: The pipeline currently only processes transactions from `TRANSACTIONS_CLEAN` and `TRANSACTIONS_DIRTY`. Adding more sources would require modifications.
- **Static Merchant Data**: Merchant data is loaded once and not updated unless the pipeline is rerun. This could lead to stale merchant information.
- **Limited Error Handling**: The pipeline has minimal error handling, which could lead to data loss if exceptions occur.
- **No Data Versioning**: The pipeline does not maintain historical versions of data, which could be useful for auditing and analysis.

## Dependencies
- **DuckDB**: The pipeline relies on DuckDB for data storage and processing.
- **MERCHANTS**: A list of merchant data used for enriching transaction data.
- **TRANSACTIONS_CLEAN & TRANSACTIONS_DIRTY**: The source transaction data files.
- **S3 Bucket**: Used for storing and retrieving pipeline-related data if needed.