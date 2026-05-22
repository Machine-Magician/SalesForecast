from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys

# Добавляем путь к скриптам
sys.path.append('/opt/airflow/scripts')

# Импортируем только существующие функции
from weather_tasks import collect_weather_for_all_cities
# from weather_tasks import get_weather_stats  # <-- УДАЛИ ЭТУ СТРОКУ

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': ['your_email@example.com']
}

with DAG(
        'weather_collector',
        default_args=default_args,
        description='Сбор погодных данных',
        schedule_interval='0 2 * * *',
        start_date=datetime(2024, 1, 1),
        catchup=False,
        tags=['weather'],
) as dag:

    collect_weather = PythonOperator(
        task_id='collect_weather',
        python_callable=collect_weather_for_all_cities,
    )

    collect_weather