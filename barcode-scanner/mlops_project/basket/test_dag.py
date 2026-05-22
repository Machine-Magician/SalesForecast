from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

def test_function():
    print("✅ Тестовый DAG работает!")
    return "OK"

default_args = {
    'owner': 'test',
    'start_date': datetime(2024, 1, 1),
}

with DAG(
    'test_dag',
    default_args=default_args,
    description='Тестовый DAG',
    schedule_interval=None,
    catchup=False,
    tags=['test'],
) as dag:

    test_task = PythonOperator(
        task_id='test_task',
        python_callable=test_function,
    )

    test_task
