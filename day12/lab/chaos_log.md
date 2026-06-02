# Chaos Log — Team Name: Sigma DataTech Lab Team
## Day 12 | Thursday 4 June 2026

---

## Pre-Exercise Answer

**Question:** Should the 9 tool functions be one Lambda or separate Lambdas? What breaks if they are one?

**Your answer:**
The tool functions should be separate Lambdas because each tool has a different blast radius, IAM permission set, runtime dependency, and operational owner. If they are one Lambda, a Snowflake connector packaging issue can break CloudWatch checks, IAM must become too broad, and the MCP tool contract becomes harder to test. If they are too fragmented without a registry, discovery and deployment become painful, so MCP is the contract that keeps separate tools usable.

---

## Phase 2 — Manual Investigation

*You have 60 minutes. Find the root cause before the agents do.*

**Records in Kinesis (02:00–02:20 UTC):** 847 records sent during the failure window.

**Records in S3 (02:00–02:20 UTC):** Firehose delivered the records to the bronze prefix; files existed and were non-empty.

**Records in Snowflake (02:00–02:20):** 0 rows loaded for the malformed batch.

---

**Failure timestamp:** 02:11 UTC, from Lambda version history and the sudden Snowflake zero-load behavior.

**What changed at that timestamp:**
The producer Lambda alias moved from stable v1 to broken v2.

**Root cause (your hypothesis):**
Lambda v2 changed the data contract by renaming `merchant_name` to `merchant_nm` and changing `transaction_date` from `YYYY-MM-DD` to `DD-MM-YYYY`, so Snowflake COPY processing silently loaded zero rows.

**Why no alert fired:**
The monitoring checked infrastructure health but did not alarm on business-level row count divergence or repeated zero-row Snowflake loads.

**Time taken to find this:** 45 minutes.

---

**Signals you connected:**
Kinesis records were produced, Firehose/S3 delivery was healthy, Snowflake row counts dropped to zero, and Lambda version history changed at the same timestamp.

**Signal you missed:**
The exact merchant-level SLA impact. I found the technical failure but did not fully calculate the QuickMart threshold breach from the SLA contract.

---

## Phase 3 — Comparison

**What I found (Phase 2 manual):**
- Time taken: 45 minutes
- Root cause found? Partial
- SLA breach identified? No
- Prevention created? No

**What the agent found (Phase 3):**
- Time taken: 26 seconds
- Root cause found? Yes
- SLA breach identified? Yes
- Prevention created? Yes (3 live alarms)

**What I missed that the agent caught:**
The agent connected the failure to business impact: 847 missing records, 824 recoverable records, 23 quarantined records, GMV loss, and QuickMart SLA breach.

**Why the agent caught it:**
The supervisor delegated to specialist agents. Forensics correlated Lambda, Kinesis, S3, and Snowflake; Impact queried Snowflake and retrieved SLA terms; Recovery replayed records idempotently; Hardening created alarms after the fix.

---

## Judgment Questions

**Forensics Agent:**
*The agent found the root cause by correlating Lambda version history with Snowflake query history. What is the one CloudWatch alarm that would have caught this at 02:12 instead of 09:03? Write it as a metric alarm definition.*

Your answer:
Create a business metric alarm on `SigmaPlatform/Pipeline` metric `SnowflakeRowsLoaded` for table `SILVER.TRANSACTIONS`: `Statistic=Sum`, `Period=300`, `EvaluationPeriods=2`, `ComparisonOperator=LessThanThreshold`, `Threshold=1`, `TreatMissingData=breaching`, with SNS notification to the on-call topic. This catches two consecutive zero-row load windows even when Lambda, Kinesis, Firehose, and S3 all look healthy.

---

**Recovery Agent:**
*The recovery used transaction_id as the idempotency key. What happens if a legitimate duplicate transaction_id exists in the source data? How would you change the deduplication logic?*

Your answer:
If a legitimate duplicate `transaction_id` exists, the MERGE will treat the second event as a duplicate and skip it, which could undercount GMV. I would change the idempotency key to a source event key such as `(transaction_id, merchant_id, event_timestamp, amount, source_sequence_number)` or use the Kinesis sequence number as the replay id while keeping `transaction_id` as a business reference.

---

**Hardening Agent:**
*The sigma-lambda-version-change alarm fires on any Lambda error spike after a version change. Your team deploys 20 Lambda functions per day in prod. Would you keep this alarm? If yes, how do you stop it from spamming? If no, what replaces it?*

Your answer:
I would keep the detection but route it through deployment context instead of paging on every deploy. The alarm should fire only when a version change is followed by an error spike, zero-row load, or row-count divergence, and it should be suppressed during approved canary windows unless the canary violates the rollback threshold.

---

## Your Honest Reflection

**Which part of the manual investigation took longest and why:**
Correlating across services took longest because each service looked healthy in isolation. The failure only became obvious after comparing Kinesis/S3 delivery with Snowflake row counts and Lambda version history.

**What would have happened if this hit prod at 2 AM with no agents:**
The dashboard would stay wrong until a human noticed the business metric gap. The team would spend hours manually checking logs, and merchant notification would likely be late.

**One thing you would add to this platform that none of the 6 agents currently do:**
I would add a Contract Validation Agent that checks every incoming batch against the active data contract before Snowflake load and blocks breaking schema changes before they become silent failures.

---

*Completed for the Day 12 self-healing pipeline lab.*
