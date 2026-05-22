import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import re
import pickle
import json
from minio import Minio
from io import BytesIO

# ============================================
# КЛАСС SALESFORECASTER
# ============================================

class SalesForecaster:
    def __init__(self, model_opt, model_roz, feature_cols, product_name, model_metrics=None):
        """
        Класс для прогнозирования продаж

        Parameters:
        model_opt: обученная модель для опта
        model_roz: обученная модель для розницы
        feature_cols: список признаков
        product_name: название товара
        model_metrics: словарь с метриками (mape, mae, train_size, test_size)
        """
        self.model_opt = model_opt
        self.model_roz = model_roz
        self.feature_cols = feature_cols
        self.product_name = product_name
        self.model_metrics = model_metrics or {}
        self.last_known = None
        self.numeric_stats = {}

    def update_last_known(self, df):
        """Обновляет последние известные данные"""
        print(f"\n ЗАГРУЗКА ПОСЛЕДНИХ ДАННЫХ ДЛЯ {self.product_name[:50]}")
        print("-" * 60)

        date_col = 'date' if 'date' in df.columns else 'Дата'
        self.last_known = df.sort_values(date_col).tail(168).copy()
        print(f"   Период: {self.last_known[date_col].min()} - {self.last_known[date_col].max()}")

        numeric_cols = self.last_known.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            self.numeric_stats[col] = {
                'mean': self.last_known[col].mean(),
                'std': self.last_known[col].std(),
                'last': self.last_known[col].iloc[-1]
            }

        if 'тип_опт' not in self.last_known.columns:
            q67 = self.last_known['quantity'].quantile(0.67)
            self.last_known['тип_опт'] = (self.last_known['quantity'] > q67).astype(int)
            self.last_known['тип_розница'] = (self.last_known['quantity'] <= q67).astype(int)

    def _get_quality_text(self):
        """Возвращает текстовую оценку качества модели"""
        if not self.model_metrics:
            return " Нет данных о качестве модели"

        mape = self.model_metrics.get('mape', 100)

        if mape < 10:
            return " ОТЛИЧНАЯ ТОЧНОСТЬ"
        elif mape < 20:
            return " ХОРОШАЯ ТОЧНОСТЬ"
        else:
            return " НИЗКАЯ ТОЧНОСТЬ"

    def _prepare_features(self, record):
        """Подготавливает признаки для одной записи"""
        record = record.copy()
        non_numeric_cols = ['season', 'region', 'date_only', 'sales_type', 'trend_name']
        for col in non_numeric_cols:
            if col in record:
                del record[col]

        for col in self.feature_cols:
            if col not in record and col in self.numeric_stats:
                record[col] = float(self.numeric_stats[col]['mean'])
            elif col not in record:
                record[col] = 0.0

        return record

    def _predict_row(self, row):
        """Предсказание для одной строки"""
        try:
            X_dict = {}
            for col in self.feature_cols:
                if col in row:
                    try:
                        val = float(row[col])
                        X_dict[col] = val
                    except (ValueError, TypeError):
                        if col in self.numeric_stats:
                            X_dict[col] = float(self.numeric_stats[col]['mean'])
                        else:
                            X_dict[col] = 0.0
                elif col in self.numeric_stats:
                    X_dict[col] = float(self.numeric_stats[col]['mean'])
                else:
                    X_dict[col] = 0.0

            X_row = pd.DataFrame([X_dict])[self.feature_cols]
            X_row = X_row.fillna(0)

            is_opt = row.get('тип_опт', 0)
            try:
                is_opt = float(is_opt)
            except:
                is_opt = 0

            if is_opt == 1 and self.model_opt is not None:
                pred = self.model_opt.predict(X_row)[0]
            else:
                pred = self.model_roz.predict(X_row)[0]

            return max(0, float(pred))

        except Exception as e:
            print(f"    Ошибка предсказания: {e}")
            return 0.0

    def forecast(self, start_date, days=7, cities=None):
        """Прогноз на указанный период"""
        if self.last_known is None:
            raise ValueError(" Сначала вызовите update_last_known()")

        end_date = start_date + timedelta(days=days-1)

        print(f"\n{'='*60}")
        print(f" ПРОГНОЗ ДЛЯ {self.product_name[:50]}")
        print('='*60)

        quality = self._get_quality_text()
        print(f"   {quality}")

        if self.model_metrics:
            mape = self.model_metrics.get('mape', 0)
            mae = self.model_metrics.get('mae', 0)
            train_size = self.model_metrics.get('train_size', 0)
            test_size = self.model_metrics.get('test_size', 0)
            print(f"   MAPE: {mape:.1f}%, MAE: {mae:.2f} шт")
            print(f"   Обучающая выборка: {train_size} записей | Тестовая: {test_size} записей")

        print(f"   Период прогноза: {start_date.date()} - {end_date.date()}")
        print(f"   Дней: {days}")
        print('='*60)

        city_col = 'city' if 'city' in self.last_known.columns else 'Город'
        org_col = 'organization' if 'organization' in self.last_known.columns else 'Организация'

        forecast_data = []
        cities = self.last_known[city_col].unique().tolist()
        organizations = self.last_known[org_col].unique() if org_col in self.last_known.columns else ['default']
        total_records = days * len(cities) * len(organizations) * 5
        print(f"   Всего прогнозных записей: {total_records}")

        record_count = 0
        for day in range(days):
            current_date = start_date + timedelta(days=day)

            for city in cities:
                for org in organizations:
                    for hour in [8, 11, 14, 17, 20]:
                        record = {}
                        record['date'] = pd.Timestamp(current_date.year, current_date.month, current_date.day, hour, 0)
                        record['organization'] = org
                        record['city'] = city

                        record['year'] = current_date.year
                        record['month'] = current_date.month
                        record['day'] = current_date.day
                        record['dayofweek'] = current_date.weekday()
                        record['hour'] = hour

                        record['month_sin'] = float(np.sin(2 * np.pi * current_date.month / 12))
                        record['month_cos'] = float(np.cos(2 * np.pi * current_date.month / 12))
                        record['hour_sin'] = float(np.sin(2 * np.pi * hour / 24))
                        record['hour_cos'] = float(np.cos(2 * np.pi * hour / 24))
                        record['dow_sin'] = float(np.sin(2 * np.pi * current_date.weekday() / 7))
                        record['dow_cos'] = float(np.cos(2 * np.pi * current_date.weekday() / 7))

                        record['is_weekend'] = 1 if current_date.weekday() >= 5 else 0

                        record['тип_опт'] = 0
                        record['тип_розница'] = 1

                        record = self._prepare_features(record)
                        forecast_data.append(record)
                        record_count += 1

                        if record_count % 500 == 0:
                            print(f"      Создано {record_count}/{total_records} записей")

        forecast_df = pd.DataFrame(forecast_data)
        print(f"\n    Создано {len(forecast_df)} записей для прогноза")

        print(f"\n    Вычисляем прогноз...")
        predictions = []

        for i in range(0, len(forecast_df), 100):
            batch = forecast_df.iloc[i:i+100]
            batch_preds = []
            for _, row in batch.iterrows():
                pred = self._predict_row(row)
                batch_preds.append(pred)
            predictions.extend(batch_preds)

            if (i + 100) % 500 == 0:
                print(f"      Обработано {min(i+100, len(forecast_df))}/{len(forecast_df)}")

        forecast_df['forecast'] = predictions

        print(f"\n АГРЕГИРОВАННЫЙ ПРОГНОЗ:")
        print("-" * 60)

        date_col = 'date' if 'date' in forecast_df.columns else 'Дата'
        daily_forecast = forecast_df.groupby(forecast_df[date_col].dt.date)['forecast'].sum().round(0)
        print(f"\n   Прогноз по дням:")
        total = 0
        for date, value in daily_forecast.items():
            print(f"      {date}: {value:,.0f} шт")
            total += value
        print(f"      {'='*30}")
        print(f"      ИТОГО: {total:,.0f} шт")

        city_col = 'city' if 'city' in forecast_df.columns else 'Город'
        city_forecast = forecast_df.groupby(city_col)['forecast'].sum().sort_values(ascending=False)
        print(f"\n   Прогноз по городам (топ-5):")
        for city, value in city_forecast.head(5).items():
            print(f"      {city[:20]:20} - {value:,.0f} шт")

        return forecast_df

    def save_forecast(self, forecast_df, filename=None):
        """Сохраняет прогноз в файл"""
        if filename is None:
            filename = f"forecast_{self.product_name[:30]}_{datetime.now().strftime('%Y%m%d')}.csv"

        filename = re.sub(r'[<>:"/\\|?*%\'"]', '_', filename)
        forecast_df.to_csv(filename, index=False)
        print(f"\n Прогноз сохранен в файл: {filename}")

        return filename


# ============================================
# ФУНКЦИЯ ДЛЯ СОЗДАНИЯ ПРОГНОЗА
# ============================================

def create_forecast_for_product(product_name, model_results, start_date=None, days=7):
    """
    Создает прогноз для конкретного товара
    """
    if product_name not in model_results:
        print(f" Товар {product_name} не найден в результатах")
        return None, None

    res = model_results[product_name]

    df_product = full_df_enriched[full_df_enriched['Номенклатура'] == product_name].copy()

    forecaster = SalesForecaster(
        model_opt=res['opt_model'],
        model_roz=res['roz_model'],
        feature_cols=res['feature_cols'],
        product_name=product_name,
        model_metrics={
            'mape': res['mape'],
            'mae': res['mae'],
            'train_size': res['train_size'],
            'test_size': res['test_size']
        }
    )

    forecaster.update_last_known(df_product)

    if start_date is None:
        start_date = datetime.now()

    forecast_df = forecaster.forecast(start_date, days=days)

    return forecaster, forecast_df