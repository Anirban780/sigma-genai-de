
    
    

with  __dbt__cte__stg_transactions as (
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
), all_values as (

    select
        payment_method as value_field,
        count(*) as n_records

    from __dbt__cte__stg_transactions
    group by payment_method

)

select *
from all_values
where value_field not in (
    'CREDIT_CARD','DEBIT_CARD','UPI'
)


