WITH transactions AS (
    SELECT *
    FROM {{ ref('stg_transactions') }}
),

merchants AS (
    SELECT
        merchant_id,
        merchant_name,
        category,
        city
    FROM {{ source('sigma_raw', 'dim_merchant') }}
),

merchant_metrics AS (
    SELECT
        t.merchant_id,
        m.merchant_name,
        m.category,
        m.city,
        COUNT(*) AS total_transactions,
        SUM(CASE WHEN t.status = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
        SUM(CASE WHEN t.status = 'COMPLETED' THEN t.amount ELSE 0 END) AS total_revenue,
        AVG(CASE WHEN t.status = 'COMPLETED' THEN t.amount END) AS avg_transaction_value,
        COUNT(DISTINCT t.customer_id) AS unique_customers
    FROM transactions t
    JOIN merchants m
      ON t.merchant_id = m.merchant_id
    GROUP BY
        t.merchant_id,
        m.merchant_name,
        m.category,
        m.city
)

SELECT
    merchant_id,
    merchant_name,
    category,
    city,
    total_transactions,
    failed_count,
    total_revenue,
    ROUND(100.0 * failed_count / NULLIF(total_transactions, 0), 2) AS failure_rate_pct,
    avg_transaction_value,
    unique_customers
FROM merchant_metrics
