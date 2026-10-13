"""
Airflow DAG: runs the claims pipeline every weekday morning.

Each task calls one step from nemt_claims/run_pipeline.py, so the logic lives in
one place and Airflow only handles scheduling, retries and alerting.
In production on AWS this would run on Amazon MWAA (managed Airflow).
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from nemt_claims.run_pipeline import STEPS, run_step

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": True,
}

with DAG(
    dag_id="nemt_claims_pipeline",
    description="Trips -> claims -> validation -> 837P -> 835 -> star schema -> reports",
    start_date=datetime(2026, 1, 1),
    schedule="0 6 * * 1-5",  # 6:00 AM, Monday to Friday
    catchup=False,
    default_args=default_args,
    tags=["claims", "healthcare", "nemt"],
) as dag:
    previous = None
    for name, _ in STEPS:
        task = PythonOperator(task_id=name, python_callable=run_step, op_args=[name])
        if previous:
            previous >> task
        previous = task
