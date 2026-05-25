
    
    



with __dbt__cte__stg_transactions as (
WITH source_transactions AS (
    SELECT
        transaction_id,
        amount,
        status,
        merchant_id,
        customer_id,
        transaction_date,
        payment_method
    FROM SIGMA_DE.PUBLIC.FACT_TRANSACTIONS
),

cleaned_transactions AS (
    SELECT
        transaction_id,
        CAST(amount AS DECIMAL(10, 2)) AS amount,
        UPPER(status) AS status,
        merchant_id,
        customer_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        UPPER(payment_method) AS payment_method,
        CURRENT_TIMESTAMP() AS loaded_at
    FROM source_transactions
    WHERE UPPER(merchant_id) NOT LIKE 'TEST_%'
)

SELECT *
FROM cleaned_transactions
),  __dbt__cte__mart_merchant_performance as (
WITH transactions AS (
    SELECT *
    FROM __dbt__cte__stg_transactions
),

merchants AS (
    SELECT
        merchant_id,
        merchant_name,
        category,
        city
    FROM SIGMA_DE.PUBLIC.DIM_MERCHANT
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
) select merchant_id
from __dbt__cte__mart_merchant_performance
where merchant_id is null


