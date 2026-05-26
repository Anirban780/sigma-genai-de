from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
import logging
import json

# DAG default arguments
default_args = {
    'owner': 'data-engineering',
   'retries': 2,
   'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
}

# DAG definition
dag = DAG(
    dag_id='sigma_transaction_pipeline',
    default_args=default_args,
    schedule='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['sigma', 'transactions', 'daily'],
    description="Daily Bronze->Silver->Gold pipeline for Sigma DataTech transactions",
    sla_miss_callback=lambda context: logging.info(f"SLA miss for {context['dag'].dag_id} at {context['execution_date']}"),
)

def log_failure(context):
    """Logs failure details."""
    dag_id = context['dag'].dag_id
    task_id = context['task_instance'].task_id
    execution_date = context['execution_date']
    exception = context['exception']
    logging.error(f"Failed task: {task_id} in DAG: {dag_id} at {execution_date}. Error: {exception}")

def extract_bronze(**context):
    """Ingest raw CSVs to Bronze Parquet."""
    logging.info(f"Starting extract_bronze task for {context['execution_date']}")
    # Add code to read CSVs and write to Bronze Parquet
    logging.info(f"Completed extract_bronze task for {context['execution_date']}")
    raise Exception("Simulated failure")  # For testing

def transform_silver(**context):
    """Clean, enrich, deduplicate to Silver."""
    logging.info(f"Starting transform_silver task for {context['execution_date']}")
    # Add code to transform data to Silver Parquet
    logging.info(f"Completed transform_silver task for {context['execution_date']}")
    raise Exception("Simulated failure")  # For testing

def build_gold(**context):
    """Generate the 3 Gold aggregation tables."""
    logging.info(f"Starting build_gold task for {context['execution_date']}")
    # Add code to build Gold tables
    logging.info(f"Completed build_gold task for {context['execution_date']}")
    raise Exception("Simulated failure")  # For testing

# Tasks
start_task = DummyOperator(task_id='start', dag=dag)

extract_bronze_task = PythonOperator(
    task_id='extract_bronze',
    python_callable=extract_bronze,
    on_failure_callback=log_failure,
    dag=dag,
)

transform_silver_task = PythonOperator(
    task_id='transform_silver',
    python_callable=transform_silver,
    on_failure_callback=log_failure,
    dag=dag,
)

build_gold_task = PythonOperator(
    task_id='build_gold',
    python_callable=build_gold,
    on_failure_callback=log_failure,
    dag=dag,
)

end_task = DummyOperator(task_id='end', dag=dag)

# Task dependencies
start_task >> extract_bronze_task >> transform_silver_task >> build_gold_task >> end_task
