import shutil
import logging
import json
import os
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, max as spark_max, broadcast
from pyspark.sql.types import FloatType, StringType, DateType

logging.basicConfig(level=logging.INFO)

def ingest_bronze(spark, input_path, output_path, run_date, run_id):
    try:
        logging.info("Starting ingest_bronze stage")
        transactions_df = (spark.read.format("csv")
                         .option("header", "true")
                         .option("inferSchema", "false")
                          .load(input_path)
                         .withColumn("ingestion_timestamp", lit(run_date))
                          .withColumn("source_file", lit("transactions.csv"))
                          .withColumn("pipeline_run_id", lit(run_id)))
        
        merchants_df = (spark.read.format("csv")
                      .option("header", "true")
                       .option("inferSchema", "false")
                       .load(input_path.replace("transactions.csv", "merchants.csv"))
                      .withColumn("ingestion_timestamp", lit(run_date))
                      .withColumn("source_file", lit("merchants.csv"))
                      .withColumn("pipeline_run_id", lit(run_id)))

        transactions_partition_path = os.path.join(output_path, "transactions", "date={}".format(run_date))
        merchants_partition_path = os.path.join(output_path, "merchants", "date={}".format(run_date))

        shutil.rmtree(transactions_partition_path, ignore_errors=True)
        shutil.rmtree(merchants_partition_path, ignore_errors=True)

        transactions_df.write.mode("overwrite").parquet(transactions_partition_path)
        merchants_df.write.mode("overwrite").parquet(merchants_partition_path)

        logging.info(f"[Stage: ingest_bronze] transactions: {transactions_df.count():,} rows")
        logging.info(f"[Stage: ingest_bronze] merchants: {merchants_df.count():,} rows")

    except Exception as e:
        logging.error(f"Error in ingest_bronze: {e}")
        raise

def transform_silver(spark, bronze_path, merchants_path, output_path, run_date):
    try:
        logging.info("Starting transform_silver stage")
        transactions_df = (spark.read.parquet(os.path.join(bronze_path, "transactions"))
                          .filter(col("date") == run_date)
                          .withColumn("amount", col("amount").cast(FloatType()))
                          .withColumn("transaction_date", col("transaction_date").cast(DateType()))
                          .withColumn("transaction_id", col("transaction_id").cast(StringType()))
                          .withColumn("merchant_id", col("merchant_id").cast(StringType())))
        
        merchants_df = (spark.read.parquet(os.path.join(merchants_path, "merchants"))
                        .filter(col("date") == run_date)
                       .withColumn("merchant_id", col("merchant_id").cast(StringType())))
        
        merchants_df.cache()

        filtered_transactions_df = transactions_df.filter((col("transaction_id").isNotNull()) & (col("amount") >= 0))
        logging.info(f"[Stage: transform_silver] after_filter: {filtered_transactions_df.count():,} rows")

        latest_transactions_df = (filtered_transactions_df
                                 .groupBy("transaction_id")
                                  .agg(spark_max("ingestion_timestamp").alias("max_ingestion_timestamp"))
                                  .join(filtered_transactions_df, on=["transaction_id", "ingestion_timestamp"], how="inner"))
        
        enriched_transactions_df = (latest_transactions_df.join(broadcast(merchants_df), on="merchant_id", how="left_outer")
                                   .withColumn("quality_flag", 
                                                col("merchant_id").when(col("merchant_id").isNotNull(), "CLEAN").otherwise("UNMATCHED")))
        
        silver_partition_path = os.path.join(output_path, "silver", "date={}".format(run_date))
        shutil.rmtree(silver_partition_path, ignore_errors=True)
        
        enriched_transactions_df.write.mode("overwrite").parquet(silver_partition_path)
        logging.info(f"[Stage: transform_silver] output: {enriched_transactions_df.count():,} rows")

    except Exception as e:
        logging.error(f"Error in transform_silver: {e}")
        raise

def main(spark, input_path, merchants_path, output_path, run_date, run_id):
    try:
        started_at = datetime.now().isoformat()
        ingest_bronze(spark, input_path, output_path, run_date, run_id)
        transform_silver(spark, output_path, merchants_path, output_path, run_date)
        completed_at = datetime.now().isoformat()
        run_status = "SUCCESS"
        error_message = None
    except Exception as e:
        completed_at = datetime.now().isoformat()
        run_status = "FAILED"
        error_message = str(e)
        raise
    finally:
        run_metadata = {
            "pipeline_name": "Sigma DataTech Transaction Analytics Pipeline",
            "run_date": run_date,
            "run_id": run_id,
            "run_status": run_status,
            "error_message": error_message,
            "started_at": started_at,
            "completed_at": completed_at
        }
        with open(os.path.join(output_path, f"run_metadata_{run_date}.json"), "w") as f:
            json.dump(run_metadata, f, indent=4)

if __name__ == "__main__":
    spark = (SparkSession.builder
           .appName("Sigma DataTech Transaction Analytics Pipeline")
            .getOrCreate())

    input_path = "s3://sigma-datatech-raw/transactions/"
    merchants_path = "s3://sigma-datatech-raw/merchants/"
    output_path = "s3://sigma-datatech-analytics/silver/"
    run_date = "2026-05-27"
    run_id = "run_id_12345"

    main(spark, input_path, merchants_path, output_path, run_date, run_id)
