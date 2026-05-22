from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import pandas as pd
import psycopg2
from sqlalchemy import create_engine

# Настройки по умолчанию
default_args = {
    'owner': 'data_analyst',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

# Параметры подключения к БД
DB_CONN = "postgresql://postgres:postgres@postgres/mydatabase"

def extract_sales_data(**context):
    """Извлечение данных за вчерашний день"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    engine = create_engine(DB_CONN)
    query = f"""
    SELECT * FROM sales 
    WHERE date = '{yesterday}'
    """
    df = pd.read_sql(query, engine)
    
    # Сохраняем в CSV для передачи между тасками
    df.to_csv(f'/opt/airflow/data/sales_{yesterday}.csv', index=False)
    print(f"✅ Извлечено {len(df)} записей за {yesterday}")
    return f'/opt/airflow/data/sales_{yesterday}.csv'

def aggregate_sales_data(**context):
    """Агрегация данных по продуктам"""
    ti = context['ti']
    file_path = ti.xcom_pull(task_ids='extract_sales')
    
    df = pd.read_csv(file_path)
    
    # Агрегация
    agg_df = df.groupby(['product_id', 'product_name']).agg({
        'quantity': 'sum',
        'revenue': 'sum',
        'customers_count': 'mean'
    }).reset_index()
    
    # Добавляем дату
    agg_df['date'] = pd.to_datetime(df['date'].iloc[0]).date()
    
    # Сохраняем результат
    output_file = file_path.replace('.csv', '_agg.csv')
    agg_df.to_csv(output_file, index=False)
    print(f"✅ Агрегировано {len(agg_df)} записей")
    return output_file

def load_to_analytics(**context):
    """Загрузка агрегированных данных в аналитическую таблицу"""
    ti = context['ti']
    file_path = ti.xcom_pull(task_ids='aggregate_sales')
    
    df = pd.read_csv(file_path)
    
    engine = create_engine(DB_CONN)
    
    # Создаем таблицу для агрегированных данных, если её нет
    create_table = """
    CREATE TABLE IF NOT EXISTS sales_daily_agg (
        date DATE,
        product_id VARCHAR(50),
        product_name VARCHAR(200),
        total_quantity INTEGER,
        total_revenue DECIMAL(10, 2),
        avg_customers DECIMAL(5, 2),
        PRIMARY KEY (date, product_id)
    );
    """
    with engine.connect() as conn:
        conn.execute(create_table)
    
    # Загружаем данные
    df.to_sql('sales_daily_agg', engine, if_exists='append', index=False, 
              method='multi')
    print(f"✅ Загружено {len(df)} записей в аналитику")

# Определение DAG [citation:3]
with DAG(
    'sales_etl_pipeline',
    default_args=default_args,
    description='ETL пайплайн для данных о продажах',
    schedule_interval='0 8 * * *',  # Каждый день в 8:00
    catchup=False,
    tags=['sales', 'etl'],
) as dag:
    
    # Таск 1: Извлечение данных
    extract_task = PythonOperator(
        task_id='extract_sales',
        python_callable=extract_sales_data
    )
    
    # Таск 2: Агрегация
    aggregate_task = PythonOperator(
        task_id='aggregate_sales',
        python_callable=aggregate_sales_data
    )
    
    # Таск 3: Загрузка в аналитику
    load_task = PythonOperator(
        task_id='load_to_analytics',
        python_callable=load_to_analytics
    )
    
    # Таск 4: Отправка уведомления (опционально)
    notify_task = BashOperator(
        task_id='send_notification',
        bash_command='echo "ETL pipeline completed successfully"'
    )
    
    # Определение зависимостей [citation:3]
    extract_task >> aggregate_task >> load_task >> notify_task
