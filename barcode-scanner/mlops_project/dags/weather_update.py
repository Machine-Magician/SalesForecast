# dags/weather_update.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

sys.path.append('/opt/airflow/scripts')
from weather_tasks import collect_weather_for_all_cities

default_args = {
    'owner': 'data_team',
    'start_date': datetime(2024, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
        'weather_update',
        default_args=default_args,
        description='Еженедельное обновление погоды',
        schedule_interval='0 3 * * 1',  # Каждый понедельник в 3:00
        catchup=False,
) as dag:

    update_weather = PythonOperator(
        task_id='update_weather',
        python_callable=collect_weather_for_all_cities,
        op_kwargs={'years_back': 2},
    )