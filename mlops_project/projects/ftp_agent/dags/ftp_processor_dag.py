# dags/ftp_processor_dag.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'ftp_agent',
    'depends_on_past': False,
    'start_date': datetime(2026, 4, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
        'ftp_processor',
        default_args=default_args,
        schedule_interval='@hourly',  # каждый час
        catchup=False,
) as dag:

    # Шаг 1: Копирование файлов из FTP (PowerShell)
    copy_files = BashOperator(
        task_id='copy_ftp_files',
        bash_command='pwsh.exe -File C:\\copy_all_ftp_files.ps1'
    )

    # Шаг 2: Валидация и эмбеддинги (Python в контейнере)
    validate_and_embed = BashOperator(
        task_id='validate_and_embed',
        bash_command='docker-compose -f /home/forestwn/mlops_project/docker-compose.yaml exec -T jupyter python /home/jovyan/work/projects/ftp_agent/src/validator.py'
    )

    copy_files >> validate_and_embed