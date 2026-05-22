
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os
import pickle
import pandas as pd

import sys
sys.path.insert(0, '/home/airflow/.local/lib/python3.10/site-packages')
sys.path.insert(0, '/opt/airflow/scripts')

from batch_processor import BatchProcessor
from sales_forecaster import SalesForecaster
from minio_utilits import save_datasets_to_minio

default_args = {
    'owner': 'data_scientist',
    'start_date': datetime(2024, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def process_batch(batch_num, execution_date):
    print(f"\n{'='*60}")
    print(f"ОБРАБОТКА БАТЧА {batch_num}/37")
    print('='*60)

    enriched_path = f'/home/jovyan/work/data/processed/batch{batch_num}_enriched.parquet'
    models_path = f'/home/jovyan/work/data/processed/batch{batch_num}_model_results.pkl'

    # 1. Загружаем или создаем данные
    if not os.path.exists(enriched_path):
        print(f"Данные не найдены, запускаем BatchProcessor...")
        bp = BatchProcessor(batch_num)
        df_enriched = bp.run()
    else:
        df_enriched = pd.read_parquet(enriched_path)
        print(f"Загружены данные: {len(df_enriched)} записей")

    # 2. ОБУЧАЕМ МОДЕЛИ (всегда)
    print(f"Запускаем обучение моделей для батча {batch_num}...")
    from batch_processor import BatchProcessor
    from model_trainer import ModelTrainer
    bp = BatchProcessor(batch_num)
    trainer = ModelTrainer(bp, batch_num)
    model_results = trainer.run()

    # Сохраняем модели
    with open(models_path, 'wb') as f:
        pickle.dump(model_results, f)
    print(f" Модели сохранены: {models_path}")

    # 3. Делаем прогноз
    all_forecasts = []
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for product_name, model_data in model_results.items():
        print(f"\nПрогноз: {product_name[:50]}")

        df_product = df_enriched[df_enriched['Номенклатура'] == product_name].copy()
        if df_product.empty:
            continue

        forecaster = SalesForecaster(
            model_opt=model_data.get('model'),
            model_roz=model_data.get('model'),
            feature_cols=model_data.get('feature_cols', []),
            product_name=product_name,
            model_metrics={
                'mape': model_data.get('mape', 0),
                'mae': model_data.get('mae', 0),
            }
        )

        forecaster.update_last_known(df_product)
        forecast_df = forecaster.forecast(start_date, days=7)
        forecast_df['product_name'] = product_name
        forecast_df['batch_num'] = batch_num
        all_forecasts.append(forecast_df)

    # 4. Сохраняем в MinIO
    if all_forecasts:
        combined_df = pd.concat(all_forecasts, ignore_index=True)
        result = save_datasets_to_minio(
            train_df=combined_df,
            product_name=f"batch_{batch_num}_forecast",
            bucket_name="sales-analytics",
            version=execution_date.strftime('%Y%m%d')
        )
        print(f" Батч {batch_num}: {len(all_forecasts)} прогнозов сохранено")
        return result

def run_all_batches(**context):
    execution_date = context['execution_date']

    print("="*60)
    print(f"НАЧАЛО ОБРАБОТКИ 37 БАТЧЕЙ")
    print("="*60)

    successful = 0
    for batch_num in range(1, 38):
        try:
            result = process_batch(batch_num, execution_date)
            if result:
                successful += 1
                print(f" Батч {batch_num} УСПЕШНО")
        except Exception as e:
            print(f" Батч {batch_num} ОШИБКА: {e}")

    print(f"\nИТОГ: Успешно {successful}/37")
    return successful

with DAG(
        'weekly_forecast_37',
        default_args=default_args,
        description='Прогноз для 37 батчей',
        schedule_interval='0 2 * * 1',
        catchup=False,
        max_active_runs=1,
) as dag:

    run_all = PythonOperator(
        task_id='run_all_batches',
        python_callable=run_all_batches,
        provide_context=True,
    )
