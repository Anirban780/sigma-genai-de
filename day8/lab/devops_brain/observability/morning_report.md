# DataOps Morning Report — 2023-10-05

### Pipeline Status
**DEGRADED**  
The pipeline is marked as degraded due to the detected drift in the 'customer_id' column between the Bronze and Silver layers.

### 5 Key Findings
- **Silver Layer Quality:**  
  - Total rows: 14  
  - Columns with nulls: None  
  - Transaction status breakdown: {'COMPLETED': 11, 'FAILED': 2, 'PENDING': 1}  
  - Amount range: 65.0 to 3400.0  
  - Amount mean: 1002.86  
  - **Observation:** The pipeline is processing a small number of transactions, and the majority are completed. However, there are two failed transactions which need attention.
  
- **Bronze → Silver Drift:**  
  - Dataset drifted: True  
  - Drift share: 0.16666666666666666  
  - Drifted columns: ['customer_id']  
  - **Observation:** A drift has been detected in the 'customer_id' column, which could potentially impact the data quality and consistency.

- **Gold Layer Active Merchants:**  
  - Active merchants: 8  
  - **Observation:** There are currently 8 active merchants contributing to the pipeline.

- **Gold Layer Total Revenue:**  
  - Total revenue: 13161.0  
  - **Observation:** The total revenue generated is 13161.0, which is a significant amount considering the small number of transactions.

- **Gold Layer Failure Rate:**  
  - Average failure rate: 18.75%  
  - Highest failure rate: 100.0% (Zomato)  
  - **Observation:** The average failure rate is 18.75%, with Zomato having the highest failure rate at 100%. This needs immediate investigation.

### Alerts to Watch
- **Bronze → Silver Drift:**  
  - Monitor for any further drift in the 'customer_id' column.
  
- **Gold Layer Failure Rate:**  
  - Keep an eye on the failure rate, especially for Zomato, as it currently stands at 100%.

- **Transaction Failures:**  
  - Investigate the cause of the two failed transactions in the Silver layer.

### Recommended Actions
- **Investigate and Resolve Drift:**  
  - Look into the cause of the drift in the 'customer_id' column and take corrective actions to ensure data consistency.

- **Analyze Zomato Failure Rate:**  
  - Investigate why Zomato has a 100% failure rate and address the issue promptly.

- **Review Failed Transactions:**  
  - Examine the two failed transactions in the Silver layer to understand the cause and prevent future occurrences.