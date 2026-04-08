from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'ftp_agent',
    'depends_on_past': False,
    'start_date': datetime(2026, 4, 7),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
        'ftp_validator',
        default_args=default_args,
        schedule_interval='0 */6 * * *',  # каждые 6 часов
        catchup=False,
) as dag:

    run_validator = BashOperator(
        task_id='run_validator',
        bash_command='docker exec my_jupyter python /home/jovyan/work/projects/ftp_agent/src/validator.py'
    )

    run_validator