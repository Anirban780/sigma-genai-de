SELECT c.customer_name,
       c.email,
       m.merchant_name,
       SUM(t.amount) AS revenue_usd,
       COUNT(*) AS transaction_count
FROM fact_transactions t
JOIN dim_customer c
  ON t.customer_id = c.customer_id
JOIN dim_merchant m
  ON t.merchant_id = m.merchant_id
WHERE t.transaction_date >= '2024-01-01'
GROUP BY c.customer_name,
         c.email,
         m.merchant_name
ORDER BY revenue_usd DESC;
