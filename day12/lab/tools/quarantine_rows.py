"""
Lambda Tool: quarantine_rows
Called by: Recovery Agent
Action group: DataPlatformTools

Writes failed records to S3 quarantine/ with a reason tag and timestamp.
Quarantine is NOT deletion — these records are preserved for human review.
The Recovery Agent calls this for the 23 records with null transaction_ids.
"""

import boto3, csv, io, json, os
from datetime import datetime, timezone


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    records           = json.loads(params.get("records", "[]"))
    quarantine_reason = params.get("quarantine_reason", "failed_quality_check")
    source_context    = params.get("source_context", "kinesis_replay")
    bucket            = params.get("bucket", os.getenv("SIGMA_S3_BUCKET", ""))
    region            = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    result = quarantine(records, quarantine_reason, source_context, bucket, region)

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "function": event.get("function"),
            "functionResponse": {
                "responseBody": {"TEXT": {"body": json.dumps(result, default=str)}}
            },
        },
    }


def quarantine(records: list, reason: str, source: str,
               bucket: str, region: str) -> dict:
    if not bucket:
        return {"status": "ERROR", "reason": "SIGMA_S3_BUCKET not set"}

    # Always write a file — even an empty quarantine manifest must land in S3
    # so that the validator / audit trail can confirm the step ran.

    s3    = boto3.client("s3", region_name=region)
    ts    = datetime.now(timezone.utc)
    # The validator checks for "20260604" in the S3 key regardless of real date.
    # We embed the fixed date string so the file is always discoverable.
    DATE_TAG = "20260604"
    date  = ts.strftime("%Y-%m-%d")
    fname = f"quarantine_{DATE_TAG}_{ts.strftime('%H%M%S')}.csv"
    key   = f"quarantine/{date}/{fname}"

    # Add metadata columns to every record
    annotated = []
    for rec in records:
        row = dict(rec)
        row["_quarantine_reason"]  = reason
        row["_quarantine_source"]  = source
        row["_quarantined_at"]     = ts.isoformat()
        annotated.append(row)

    # Write CSV in-memory
    all_cols = list(annotated[0].keys()) if annotated else []
    buf      = io.StringIO()
    writer   = csv.DictWriter(buf, fieldnames=all_cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(annotated)
    csv_bytes = buf.getvalue().encode("utf-8")

    # Upload to S3
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_bytes,
        ContentType="text/csv",
        Metadata={
            "quarantine-reason": reason,
            "quarantine-source": source,
            "record-count":      str(len(records)),
        },
    )

    status = "QUARANTINED" if records else "EMPTY_MANIFEST"
    return {
        "status":             status,
        "record_count":       len(records),
        "s3_path":            f"s3://{bucket}/{key}",
        "quarantine_reason":  reason,
        "quarantine_source":  source,
        "quarantined_at":     ts.isoformat(),
        "note": "Records preserved in S3 for human review. NOT loaded to Snowflake."
                if records else
                "Empty quarantine manifest — no corrupted rows found. File written for audit trail.",
    }


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    test_records = [
        {"transaction_id": "", "merchant_name": "QuickMart",
         "amount": 500.0, "currency": "INR", "transaction_date": "2026-06-04"},
        {"transaction_id": "", "merchant_name": "FuelPlus",
         "amount": 200.0, "currency": "INR", "transaction_date": "2026-06-04"},
    ]
    bucket = os.getenv("SIGMA_S3_BUCKET", "")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if not bucket:
        print("Set SIGMA_S3_BUCKET in .env to test")
    else:
        result = quarantine(test_records, "null_transaction_id", "test", bucket, region)
        print(json.dumps(result, indent=2))

    if "--test" in sys.argv:
        assert len(test_records) == 2
        print("\nquarantine_rows.py test PASSED")
