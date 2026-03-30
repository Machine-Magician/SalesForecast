import pandas as pd
import json
import numpy as np
from clickhouse_driver import Client
import os

class BatchInitializer:
    """Класс для инициализации батчей и создания конфигурационных файлов"""

    def __init__(self):
        self.ch_client = Client(host='my_clickhouse', port=9000, user='default', password='')
        self.data_path = '/home/jovyan/work/data/processed'
        os.makedirs(self.data_path, exist_ok=True)

    def get_all_products(self):
        """Получает список всех товаров из ClickHouse"""
        query = """
        SELECT DISTINCT `Номенклатура`
        FROM external_data.sales_raw
        """
        df = self.ch_client.query_dataframe(query)
        return df['Номенклатура'].tolist()

    def create_batches(self, products_per_batch=7):
        """Создает батчи по products_per_batch товаров с кластерами"""
        all_products = self.get_all_products()

        # Разбиваем на 37 батчей (как вы хотели)
        total_batches = 37
        products_per_batch = len(all_products) // total_batches + 1

        batches = []
        batch_num = 1
        for i in range(0, len(all_products), products_per_batch):
            if batch_num > total_batches:
                break
            batch_products = all_products[i:i+products_per_batch]
            # Определяем кластер (для простоты - все в кластере 1)
            cluster = 1
            batches.append({
                'batch_num': batch_num,
                'cluster': cluster,
                'cluster_name': f'cluster_{cluster}',
                'products': str(batch_products),
                'product_count': len(batch_products)
            })
            batch_num += 1

        # Сохраняем в CSV
        batches_df = pd.DataFrame(batches)
        batches_df.to_csv(f'{self.data_path}/batches_detail.csv', index=False)
        print(f" Создано {len(batches)} батчей")
        print(f"   Файл: {self.data_path}/batches_detail.csv")

        return batches_df

    def create_batch_config(self):
        """Создает конфигурацию для моделей"""
        config = {
            'clusters': {
                '1': {
                    'name': 'cluster_1',
                    'params': {
                        'n_estimators': 500,
                        'learning_rate': 0.05,
                        'max_depth': 5
                    }
                }
            }
        }

        with open(f'{self.data_path}/batch_config.json', 'w') as f:
            json.dump(config, f, indent=2)
        print(f" Конфигурация создана: {self.data_path}/batch_config.json")

        return config

    def initialize_all_batches(self):
        """Запускает обработку всех батчей для создания enriched файлов"""
        self.create_batches()
        self.create_batch_config()

        # Получаем список батчей
        batches_df = pd.read_csv(f'{self.data_path}/batches_detail.csv')

        from batch_processor import BatchProcessor

        for _, row in batches_df.iterrows():
            batch_num = row['batch_num']
            print(f"\n{'='*60}")
            print(f"Инициализация батча {batch_num}")
            print('='*60)

            try:
                bp = BatchProcessor(batch_num)
                df_enriched = bp.run()
                print(f" Батч {batch_num} инициализирован")
            except Exception as e:
                print(f" Ошибка батча {batch_num}: {e}")

if __name__ == "__main__":
    init = BatchInitializer()
    init.initialize_all_batches()