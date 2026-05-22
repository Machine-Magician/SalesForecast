# model_trainer.py
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
import pickle
import json
import os
import re
import gc
from datetime import datetime, timedelta
from feature_engineering import (
    create_time_features, create_lag_features,
    create_org_features, create_type_features
)
from minio import Minio
from io import BytesIO

class ModelTrainer:
    def __init__(self, batch_processor, batch_num):
        self.bp = batch_processor
        self.batch_num = batch_num
        self.df_enriched = None
        self.products = None
        self.model_results = {}
        self.results_path = f'/home/jovyan/work/data/processed/batch{batch_num}_model_results.pkl'

        print(f"\n{'='*60}")
        print(f" ModelTrainer для БАТЧА {batch_num}")
        print('='*60)

    def load_batch_data(self):
        enriched_path = f'/home/jovyan/work/data/processed/batch{self.batch_num}_enriched.parquet'

        if os.path.exists(enriched_path):
            print(f" Загружаем обогащенный датасет батча {self.batch_num}")
            self.df_enriched = pd.read_parquet(enriched_path)
            print(f"   Размер: {self.df_enriched.shape}")
        else:
            print(f" Нет обогащенного файла, запускаем обработку через BatchProcessor")
            self.df_enriched = self.bp.run()

        self.products = self.df_enriched['Номенклатура'].unique().tolist()
        print(f"   Товаров в батче: {len(self.products)}")
        return self.df_enriched

    def prepare_product_data(self, product_name):
        df = self.df_enriched[self.df_enriched['Номенклатура'] == product_name].copy()

        if df.empty:
            return None
        if len(df) < 50:
            print(f"   Слишком мало данных для {product_name}: {len(df)} записей")
            return None

        rename_dict = {
            'date': 'Дата', 'quantity': 'Количество', 'amount': 'Сумма',
            'price': 'Цена', 'city': 'Город', 'counterparty': 'Контрагент',
            'organization': 'Организация'
        }
        rename_dict = {k: v for k, v in rename_dict.items() if k in df.columns}
        df = df.rename(columns=rename_dict)

        # Добавляем признаки
        from feature_engineering import (
            create_time_features, create_lag_features,
            create_org_features, create_type_features
        )

        df = create_time_features(df)
        df = create_lag_features(df)
        df = create_org_features(df)
        df = create_type_features(df)

        # Подготовка числовых данных
        df['Дата'] = pd.to_datetime(df['Дата'])

        for col in df.columns:
            if col != 'Дата' and col not in ['Номенклатура', 'Организация', 'Контрагент', 'Город']:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    pass

        # ========== ФИКСИРОВАННОЕ РАЗДЕЛЕНИЕ ПО ВРЕМЕНИ ==========
        df = df.sort_values('Дата')

        # Отрезаем последние 30% данных для теста
        test_size = 0.3
        split_idx = int(len(df) * (1 - test_size))

        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()

        print(f"   Train: {len(train_df)} записей ({train_df['Дата'].min().date()} - {train_df['Дата'].max().date()})")
        print(f"   Test: {len(test_df)} записей ({test_df['Дата'].min().date()} - {test_df['Дата'].max().date()})")

        if len(test_df) < 10:
            print(f"   Слишком мало тестовых данных ({len(test_df)}), пропускаем")
            return None

        # Удаляем нечисловые колонки
        exclude_cols = ['Номенклатура', 'Дата', 'Час_начало', 'Организация', 'Контрагент', 'Город']
        existing_to_drop = [col for col in exclude_cols if col in train_df.columns]

        train_df_numeric = train_df.drop(columns=existing_to_drop)
        test_df_numeric = test_df.drop(columns=existing_to_drop)

        feature_cols = [col for col in train_df_numeric.columns if col != 'Количество']

        # Заполняем NaN и преобразуем в float
        X_train = train_df_numeric[feature_cols].fillna(0).astype(float)
        y_train = train_df['Количество'].fillna(0).astype(float)
        X_test = test_df_numeric[feature_cols].fillna(0).astype(float)
        y_test = test_df['Количество'].fillna(0).astype(float)

        # Удаляем строки с нулевыми значениями (опционально)
        mask = (y_train > 0) | (y_train == 0)
        X_train = X_train[mask]
        y_train = y_train[mask]

        if len(X_train) < 30:
            print(f"   После очистки осталось {len(X_train)} записей - мало")
            return None

        return {
            'X_train': X_train,
            'y_train': y_train,
            'X_test': X_test,
            'y_test': y_test,
            'feature_cols': feature_cols,
            'train_df': train_df,
            'test_df': test_df,
            'train_size': len(train_df),
            'test_size': len(test_df)
        }

    def train_model(self, product_name, product_data):
        X_train = product_data['X_train']
        y_train = product_data['y_train']
        X_test = product_data['X_test']
        y_test = product_data['y_test']
        feature_cols = product_data['feature_cols']

        print(f"\n   Обучение модели...")
        print(f"   X_train: {X_train.shape}, X_test: {X_test.shape}")

        # Проверяем, что нет бесконечных значений
        X_train = X_train.replace([np.inf, -np.inf], 0)
        X_test = X_test.replace([np.inf, -np.inf], 0)

        # Проверяем, что y_train не пустой
        if len(y_train) == 0 or y_train.sum() == 0:
            print(f"   Нет положительных значений в y_train")
            return None

        try:
            model = xgb.XGBRegressor(
                n_estimators=200,  # уменьшил для скорости
                learning_rate=0.05,
                max_depth=5,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=0.1,
                random_state=42,
                early_stopping_rounds=30,
                eval_metric='rmse'
            )

            model.fit(X_train, y_train,
                      eval_set=[(X_train, y_train), (X_test, y_test)],
                      verbose=False)
        except Exception as e:
            print(f"   Ошибка обучения XGBoost: {e}")
            # Пробуем RandomForest как fallback
            from sklearn.ensemble import RandomForestRegressor
            print(f"   Пробуем RandomForest...")
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=1  # избегаем проблем с многопоточностью
            )
            model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        mape = mean_absolute_percentage_error(y_test, y_pred) * 100

        importance = model.feature_importances_
        feature_importance = sorted(zip(feature_cols, importance), key=lambda x: x[1], reverse=True)

        return {
            'model': model,
            'mae': mae,
            'mape': mape,
            'y_pred': y_pred,
            'feature_importance': feature_importance
        }

    def run(self):
        print(f"\n{'='*60}")
        print(f" Запуск обучения для БАТЧА {self.batch_num}")
        print('='*60)

        self.load_batch_data()

        if self.df_enriched is None or len(self.products) == 0:
            print(" Нет данных для обучения")
            return None

        for idx, product_name in enumerate(self.products, 1):
            print(f"\n{'='*70}")
            print(f" {idx}/{len(self.products)}: {product_name[:70]}")
            print('='*70)

            product_data = self.prepare_product_data(product_name)
            if product_data is None:
                continue

            result = self.train_model(product_name, product_data)
            if result is None:
                print(f"   Пропускаем товар {product_name}")
                continue

            self.model_results[product_name] = {
                'mape': result['mape'],
                'mae': result['mae'],
                'y_test': product_data['y_test'],
                'y_pred': result['y_pred'],
                'feature_cols': product_data['feature_cols'],
                'feature_importance': result['feature_importance'],
                'train_size': product_data['train_size'],
                'test_size': product_data['test_size'],
                'model': result['model']
            }

            print(f"\n    Результаты:")
            print(f"      MAE: {result['mae']:.2f}")
            print(f"      MAPE: {result['mape']:.1f}%")

            top_features = result['feature_importance'][:3]
            print(f"      Топ-3 признака: {[f[0] for f in top_features]}")

        self.save_results()

        # Сохраняем анализ в MinIO
        self.save_full_analysis_to_minio(self.df_enriched, self.model_results, self.batch_num)

        print(f"\n{'='*60}")
        print(f" Обучение батча {self.batch_num} завершено")
        print(f"   Обработано товаров: {len(self.model_results)}")
        print('='*60)

        return self.model_results

    def save_results(self):
        os.makedirs(os.path.dirname(self.results_path), exist_ok=True)

        with open(self.results_path, 'wb') as f:
            pickle.dump(self.model_results, f)
        print(f"\n Результаты сохранены: {self.results_path}")

        json_results = {}
        for prod, res in self.model_results.items():
            json_results[prod] = {
                'mape': float(res['mape']),
                'mae': float(res['mae']),
                'train_size': res['train_size'],
                'test_size': res['test_size'],
                'top_features': [{'name': f[0], 'importance': float(f[1])}
                                 for f in res['feature_importance'][:5]]
            }

        json_path = f'/home/jovyan/work/data/processed/batch{self.batch_num}_metrics.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_results, f, ensure_ascii=False, indent=2)
        print(f" Метрики сохранены: {json_path}")


    def save_full_analysis_to_minio(self, df_enriched, model_results, batch_num):
        """
        Сохраняет полный анализ по городам и контрагентам в MinIO
        """
        from datetime import datetime, timedelta
        from minio import Minio
        from io import BytesIO
        # Фиксированные названия колонок
        city_col = 'Город'
        counterparty_col = 'Контрагент'
        quantity_col = 'Количество'
        amount_col = 'Сумма'
        date_col = 'Дата'
        # Определяем даты для прогноза
        start_date = datetime.now().date() + timedelta(days=1)
        end_date = start_date + timedelta(days=6)

        # Собираем весь вывод в одну строку
        full_analysis = []

        full_analysis.append("="*70)
        full_analysis.append(f" АНАЛИЗ ПО ГОРОДАМ И КОНТРАГЕНТАМ ДЛЯ БАТЧА {batch_num}")
        full_analysis.append(f" Дата формирования: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        full_analysis.append(f" Период прогноза: {start_date} - {end_date}")
        full_analysis.append("="*70)

        # Блок качества моделей
        full_analysis.append("\n" + "="*70)
        full_analysis.append(" КАЧЕСТВО МОДЕЛЕЙ")
        full_analysis.append("="*70)

        for prod, res in model_results.items():
            mape = res['mape']
            mae = res['mae']
            train_size = res.get('train_size', 0)
            test_size = res.get('test_size', 0)

            if mape < 10:
                quality = " ОТЛИЧНАЯ"
            elif mape < 20:
                quality = " ХОРОШАЯ"
            else:
                quality = " НИЗКАЯ"

            full_analysis.append(f"\n   {prod[:60]}...")
            full_analysis.append(f"      Качество: {quality} (MAPE: {mape:.1f}%, MAE: {mae:.2f})")
            full_analysis.append(f"      Обучающая выборка: {train_size} записей | Тестовая: {test_size} записей")

        # Сводная статистика
        full_analysis.append("\n" + "="*70)
        full_analysis.append(" СВОДНАЯ СТАТИСТИКА")
        full_analysis.append("="*70)

        good_count = sum(1 for res in model_results.values() if res['mape'] < 10)
        medium_count = sum(1 for res in model_results.values() if 10 <= res['mape'] < 20)
        bad_count = sum(1 for res in model_results.values() if res['mape'] >= 20)

        full_analysis.append(f"\n   Отличные модели (MAPE < 10%): {good_count} товаров")
        full_analysis.append(f"   Хорошие модели (MAPE 10-20%): {medium_count} товаров")
        full_analysis.append(f"   Низкая точность (MAPE > 20%): {bad_count} товаров")

        # Данные по каждому товару
        for prod, res in model_results.items():
            mape = res['mape']
            mae = res['mae']

            full_analysis.append(f"\n ТОВАР: {prod[:70]}")
            full_analysis.append("-" * 60)

            if mape < 10:
                quality = " ОТЛИЧНАЯ ТОЧНОСТЬ"
            elif mape < 20:
                quality = " ХОРОШАЯ ТОЧНОСТЬ"
            else:
                quality = " НИЗКАЯ ТОЧНОСТЬ"

            full_analysis.append(f"   {quality} (MAPE: {mape:.1f}%, MAE: {mae:.2f} шт)")
            full_analysis.append(f"   Обучающая выборка: {res.get('train_size', 0)} записей | Тестовая: {res.get('test_size', 0)} записей")
            full_analysis.append("-" * 60)

            df_product = df_enriched[df_enriched['Номенклатура'] == prod].copy()

            # Определяем колонки (русские названия)
            city_col = 'Город' if 'Город' in df_product.columns else 'city'
            counterparty_col = 'Контрагент' if 'Контрагент' in df_product.columns else 'counterparty'
            quantity_col = 'Количество'
            amount_col = 'Сумма'
            date_col = 'Дата' if 'Дата' in df_product.columns else 'date'

            if city_col in df_product.columns:
                # Статистика по городам
                city_stats = df_product.groupby(city_col).agg({
                    quantity_col: ['sum', 'mean', 'count'],
                    amount_col: 'sum'
                }).round(2)
                city_stats.columns = ['всего_шт', 'среднее_шт', 'кол_заказов', 'сумма_руб']
                city_stats = city_stats.sort_values('сумма_руб', ascending=False)
                city_stats['средний_чек'] = city_stats['сумма_руб'] / city_stats['кол_заказов']

                # Получаем основного контрагента для каждого города
                main_contractor = df_product.groupby(city_col)[counterparty_col].agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'неизвестно')

                full_analysis.append("\n    ТОП-10 ГОРОДОВ ПО СУММЕ:")
                for city, row in city_stats.head(10).iterrows():
                    contractor = main_contractor.get(city, 'неизвестно')
                    contractor_short = contractor[:30] + '...' if len(contractor) > 30 else contractor
                    full_analysis.append(f"      {city[:20]:20} ({contractor_short}) - {row['сумма_руб']:>12,.0f} руб ({row['всего_шт']:>6.0f} шт, {row['кол_заказов']:>4.0f} заказов)")

                full_analysis.append("\n    ТОП-10 ГОРОДОВ ПО СРЕДНЕМУ ЧЕКУ:")
                for city, row in city_stats.sort_values('средний_чек', ascending=False).head(10).iterrows():
                    contractor = main_contractor.get(city, 'неизвестно')
                    contractor_short = contractor[:30] + '...' if len(contractor) > 30 else contractor
                    full_analysis.append(f"      {city[:20]:20} ({contractor_short}) - {row['средний_чек']:>8,.0f} руб/заказ")

                # ПРОГНОЗ С КОНКРЕТНЫМИ ДАТАМИ
                full_analysis.append(f"\n    ПРОГНОЗ НА НЕДЕЛЮ: {start_date} - {end_date}")
                full_analysis.append("-" * 60)

                for city in city_stats.head(10).index:
                    city_data = df_product[df_product[city_col] == city].copy()
                    city_data = city_data.sort_values(date_col)
                    contractor = main_contractor.get(city, 'неизвестно')
                    contractor_short = contractor[:25] + '...' if len(contractor) > 25 else contractor

                    if len(city_data) > 7:
                        last_week = city_data.tail(7)
                        avg_last_week = last_week[quantity_col].mean()

                        if len(city_data) > 30:
                            recent = city_data.tail(30)[quantity_col].mean()
                            if len(city_data) > 60:
                                old = city_data.iloc[-60:-30][quantity_col].mean()
                            else:
                                old = city_data.head(30)[quantity_col].mean()
                            trend = ((recent - old) / old * 100) if old > 0 else 0
                        else:
                            trend = 0

                        forecast_daily = avg_last_week * (1 + trend/100/4)
                        forecast_weekly = forecast_daily * 7

                        if trend > 50:
                            trend_symbol = "🔥🔥 СИЛЬНЫЙ РОСТ"
                        elif trend > 10:
                            trend_symbol = "📈 рост"
                        elif trend > -10:
                            trend_symbol = "➡️ стабильно"
                        elif trend > -50:
                            trend_symbol = "📉 падение"
                        else:
                            trend_symbol = "💥💥 СИЛЬНОЕ ПАДЕНИЕ"

                        full_analysis.append(f"\n      {trend_symbol} {city[:20]:20} ({contractor_short})")
                        full_analysis.append(f"         Текущие: {avg_last_week:.1f} шт/день")
                        full_analysis.append(f"         Тренд: {trend:+.1f}%")
                        full_analysis.append(f"         Прогноз на неделю ({start_date} - {end_date}): {forecast_weekly:.0f} шт")

                        if trend < -50:
                            full_analysis.append(f"          РЕКОМЕНДАЦИЯ: Снизить цену на 15-20%")

        # Рекомендации
        full_analysis.append("\n" + "="*70)
        full_analysis.append(" РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ")
        full_analysis.append("="*70)

        # Товары с низкой точностью
        problematic = [prod for prod, res in model_results.items() if res['mape'] > 20]
        if problematic:
            full_analysis.append(f"\n Товары с низкой точностью прогноза (MAPE > 20%):")
            for prod in problematic[:10]:
                mape = model_results[prod]['mape']
                full_analysis.append(f"   - {prod[:60]}... (MAPE: {mape:.1f}%)")

        # Товары с отличной точностью
        good = [prod for prod, res in model_results.items() if res['mape'] < 10]
        if good:
            full_analysis.append(f"\n Товары с отличной точностью (MAPE < 10%):")
            for prod in good[:10]:
                mape = model_results[prod]['mape']
                full_analysis.append(f"   - {prod[:60]}... (MAPE: {mape:.1f}%)")

        # Города с ростом и падением
        full_analysis.append("\n Города с СИЛЬНЫМ РОСТОМ (>50%) - увеличить отгрузки:")
        full_analysis.append("-" * 60)

        growing_recommendations = {}
        falling_recommendations = {}

        for prod in model_results.keys():
            df_product = df_enriched[df_enriched['Номенклатура'] == prod].copy()
            city_col = 'Город' if 'Город' in df_product.columns else 'city'
            counterparty_col = 'Контрагент' if 'Контрагент' in df_product.columns else 'counterparty'
            quantity_col = 'Количество' if 'Количество' in df_product.columns else 'quantity'
            date_col = 'Дата' if 'Дата' in df_product.columns else 'date'

            if city_col in df_product.columns:
                main_contractor = df_product.groupby(city_col)[counterparty_col].agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'неизвестно')

                for city in df_product[city_col].unique()[:15]:
                    city_data = df_product[df_product[city_col] == city].sort_values(date_col)
                    if len(city_data) > 30:
                        recent = city_data.tail(30)[quantity_col].mean()
                        old = city_data.head(30)[quantity_col].mean()
                        if old > 0:
                            growth = ((recent - old) / old * 100)
                            contractor = main_contractor.get(city, 'неизвестно')
                            contractor_short = contractor[:25] + '...' if len(contractor) > 25 else contractor

                            if growth > 50:
                                if city not in growing_recommendations:
                                    growing_recommendations[city] = []
                                growing_recommendations[city].append((prod[:50], growth, contractor_short))
                            elif growth < -50:
                                if city not in falling_recommendations:
                                    falling_recommendations[city] = []
                                falling_recommendations[city].append((prod[:50], growth, contractor_short))

        if growing_recommendations:
            for city, products in sorted(growing_recommendations.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
                full_analysis.append(f"\n    {city}:")
                for prod, growth, contractor in sorted(products, key=lambda x: x[1], reverse=True)[:3]:
                    full_analysis.append(f"       {prod} ({contractor}): рост {growth:+.1f}% - УВЕЛИЧИТЬ ОТГРУЗКУ")
        else:
            full_analysis.append("   Нет городов с сильным ростом")

        if falling_recommendations:
            full_analysis.append("\n ГОРОДА С СИЛЬНЫМ ПАДЕНИЕМ (<-50%) - рассмотреть скидки:")
            full_analysis.append("-" * 60)

            for city, products in sorted(falling_recommendations.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
                full_analysis.append(f"\n    {city}:")
                for prod, growth, contractor in sorted(products, key=lambda x: x[1])[:3]:
                    discount = min(30, int(abs(growth)/3))
                    full_analysis.append(f"       {prod} ({contractor}): падение {growth:.1f}% - рекомендовать скидку {discount}%")

        full_analysis.append(f"\n{'='*70}")
        full_analysis.append(f" КОНЕЦ ОТЧЕТА")
        full_analysis.append(f"{'='*70}")

        # Сохраняем в MinIO
        analysis_text = "\n".join(full_analysis)

        try:
            client = Minio(
                endpoint="host.docker.internal:9002",
                access_key="minioadmin",
                secret_key="minioadmin",
                secure=False
            )

            bucket_name = "sales-analytics"
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                print(f" Создан бакет: {bucket_name}")

            date_str = datetime.now().strftime('%Y%m%d')
            time_str = datetime.now().strftime('%H%M%S')

            filename = f"full_city_analysis_{date_str}_{time_str}.txt"
            file_path = f"{date_str}/batch{batch_num}/{filename}"

            analysis_buffer = BytesIO()
            analysis_buffer.write(analysis_text.encode('utf-8-sig'))
            analysis_buffer.seek(0)

            client.put_object(
                bucket_name,
                file_path,
                data=analysis_buffer,
                length=analysis_buffer.getbuffer().nbytes,
                content_type='text/plain; charset=utf-8'
            )

            file_url = f"http://localhost:9003/{bucket_name}/{file_path}"
            print(f" Анализ сохранен: {file_url}")

            return file_url
        except Exception as e:
            print(f" Ошибка сохранения анализа в MinIO: {e}")
            return None