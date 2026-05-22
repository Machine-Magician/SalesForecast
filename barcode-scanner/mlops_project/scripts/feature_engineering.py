# ~/mlops_project/scripts/feature_engineering.py

import numpy as np
import pandas as pd

def create_time_features(df):
    """Добавляет циклические временные признаки"""
    df = df.copy()
    df['Год'] = df['Дата'].dt.year
    df['Месяц'] = df['Дата'].dt.month
    df['День_месяца'] = df['Дата'].dt.day
    df['День_недели'] = df['Дата'].dt.dayofweek
    df['Час'] = df['Дата'].dt.hour
    df['Неделя_года'] = df['Дата'].dt.isocalendar().week
    df['Месяц_sin'] = np.sin(2 * np.pi * df['Месяц'] / 12)
    df['Месяц_cos'] = np.cos(2 * np.pi * df['Месяц'] / 12)
    df['День_недели_sin'] = np.sin(2 * np.pi * df['День_недели'] / 7)
    df['День_недели_cos'] = np.cos(2 * np.pi * df['День_недели'] / 7)
    df['Час_sin'] = np.sin(2 * np.pi * df['Час'] / 24)
    df['Час_cos'] = np.cos(2 * np.pi * df['Час'] / 24)
    df['Выходной'] = df['День_недели'].isin([5, 6]).astype(int)
    return df

def create_lag_features(df):
    """Добавляет лаговые признаки и скользящие средние"""
    df = df.copy()
    df = df.sort_values('Дата')
    df['Количество_лаг_1час'] = df['Количество'].shift(1)
    df['Количество_лаг_3час'] = df['Количество'].shift(3)
    df['Количество_лаг_6час'] = df['Количество'].shift(6)
    df['Количество_лаг_12час'] = df['Количество'].shift(12)
    df['Количество_лаг_24час'] = df['Количество'].shift(24)
    df['Количество_лаг_168час'] = df['Количество'].shift(168)
    df['Количество_среднее_3ч'] = df['Количество'].rolling(window=3, min_periods=1).mean().shift(1)
    df['Количество_среднее_6ч'] = df['Количество'].rolling(window=6, min_periods=1).mean().shift(1)
    df['Количество_среднее_12ч'] = df['Количество'].rolling(window=12, min_periods=1).mean().shift(1)
    df['Количество_среднее_24ч'] = df['Количество'].rolling(window=24, min_periods=1).mean().shift(1)
    return df

def create_org_features(df):
    """Добавляет признаки по организациям и контрагентам"""
    df = df.copy()
    if 'Организация' in df.columns:
        org_stats = df.groupby('Организация')['Количество'].agg(['mean', 'std']).fillna(0)
        org_stats_dict = org_stats.to_dict('index')
        df['org_mean_sales'] = df['Организация'].map(lambda x: org_stats_dict.get(x, {}).get('mean', 0))
        df['org_std_sales'] = df['Организация'].map(lambda x: org_stats_dict.get(x, {}).get('std', 0))
    if 'Контрагент' in df.columns:
        kontr_stats = df.groupby('Контрагент')['Количество'].agg(['mean', 'std']).fillna(0)
        kontr_stats_dict = kontr_stats.to_dict('index')
        df['kontr_mean_sales'] = df['Контрагент'].map(lambda x: kontr_stats_dict.get(x, {}).get('mean', 0))
        df['kontr_std_sales'] = df['Контрагент'].map(lambda x: kontr_stats_dict.get(x, {}).get('std', 0))
    return df

def create_type_features(df):
    """Добавляет признаки типов продаж"""
    df = df.copy()
    q33 = df['Количество'].quantile(0.33)
    q67 = df['Количество'].quantile(0.67)
    df['тип_продажи'] = df['Количество'].apply(
        lambda x: 'крупные' if x > q67 else ('средние' if x > q33 else 'мелкие')
    )
    dummies = pd.get_dummies(df['тип_продажи'], prefix='тип')
    rename_map = {
        'тип_крупные': 'тип_опт',
        'тип_средние': 'тип_розница',
        'тип_мелкие': 'тип_мелкая_розница'
    }
    existing_cols = {k: v for k, v in rename_map.items() if k in dummies.columns}
    if existing_cols:
        dummies = dummies.rename(columns=existing_cols)
    df = pd.concat([df, dummies], axis=1)
    df = df.drop('тип_продажи', axis=1)
    return df