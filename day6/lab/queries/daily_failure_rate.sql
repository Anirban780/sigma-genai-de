SELECT transaction_date,
       (SELECT COUNT(*)
        FROM fact_transactions f2
        WHERE f2.status = 'FAILED'
          AND f2.transaction_date = t.transaction_date) AS failed_count,
       COUNT(*) AS total_count,
       failed_count / total_count * 100 AS failure_rate
FROM fact_transactions t
GROUP BY transaction_date
ORDER BY transaction_date;
