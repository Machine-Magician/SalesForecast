#функция версионирования датасетов для Minio
import json
import pickle
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from minio import Minio
from io import BytesIO
import re

def save_datasets_to_minio(
        train_df,
        test_df=None,
        product_name=None,
        bucket_name="ml-datasets",
        version=None,
        split_info=None
):
    """
    Сохраняет train/test датасеты в Minio с версионированием
    """
    # Проверяем тип данных
    if not isinstance(train_df, pd.DataFrame):
        print(f" Ошибка: train_df должен быть DataFrame, а это {type(train_df)}")
        return None

    print(f"\n{'='*60}")
    print(f" СОХРАНЕНИЕ ДАТАСЕТА В MINIO")
    print('='*60)
    print(f"   Продукт: {product_name[:50]}")
    print(f"   Train: {train_df.shape}, Test: {test_df.shape if test_df is not None else 'None'}")

    # Подключение к Minio
    try:
        client = Minio(
            endpoint="host.docker.internal:9002",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )
        # Проверка подключения
        client.list_buckets()
        print(" Подключение к Minio успешно")
    except Exception as e:
        print(f" Ошибка подключения к Minio: {e}")
        print("   Проверьте настройки подключения")
        return None

    # Создаем бакет если нет
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f" Создан бакет: {bucket_name}")

    # Очищаем имя продукта для пути
    clean_name = re.sub(r'[<>:"/\\|?*%\'"]', '_', product_name)
    clean_name = clean_name[:50]

    # Формируем версию
    if version is None:
        version = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Базовый путь
    base_path = f"datasets/{clean_name}/train_test_split"

    saved_files = []

    # Определяем колонку даты (date или Дата)
    date_col = 'date' if 'date' in train_df.columns else 'Дата'

    # 1. Сохраняем train
    try:
        train_buffer = BytesIO()
        train_df.to_parquet(train_buffer, index=False)
        train_buffer.seek(0)

        train_path = f"{base_path}/train_{version}.parquet"
        client.put_object(
            bucket_name,
            train_path,
            data=train_buffer,
            length=train_buffer.getbuffer().nbytes,
            content_type='application/parquet'
        )
        saved_files.append(f"{bucket_name}/{train_path}")
        print(f" Train сохранен: {train_path}")
        print(f"   Размер: {len(train_df)} записей, {len(train_df.columns)} признаков")
    except Exception as e:
        print(f" Ошибка при сохранении train (parquet): {e}")
        # Пробуем сохранить как csv
        try:
            train_buffer = BytesIO()
            train_df.to_csv(train_buffer, index=False)
            train_buffer.seek(0)
            train_path = f"{base_path}/train_{version}.csv"
            client.put_object(
                bucket_name,
                train_path,
                data=train_buffer,
                length=train_buffer.getbuffer().nbytes,
                content_type='text/csv'
            )
            print(f" Train сохранен как CSV: {train_path}")
        except Exception as e2:
            print(f" Ошибка при сохранении train (csv): {e2}")
            return None

    # 2. Сохраняем test (аналогично)
    test_path = None
    if test_df is not None and not test_df.empty:
        try:
            test_buffer = BytesIO()
            test_df.to_parquet(test_buffer, index=False)
            test_buffer.seek(0)

            test_path = f"{base_path}/test_{version}.parquet"
            client.put_object(
                bucket_name,
                test_path,
                data=test_buffer,
                length=test_buffer.getbuffer().nbytes,
                content_type='application/parquet'
            )
            saved_files.append(f"{bucket_name}/{test_path}")
            print(f" Test сохранен: {test_path}")
            print(f"   Размер: {len(test_df)} записей")
        except Exception as e:
            print(f" Ошибка при сохранении test (parquet): {e}")
            try:
                test_buffer = BytesIO()
                test_df.to_csv(test_buffer, index=False)
                test_buffer.seek(0)
                test_path = f"{base_path}/test_{version}.csv"
                client.put_object(
                    bucket_name,
                    test_path,
                    data=test_buffer,
                    length=test_buffer.getbuffer().nbytes,
                    content_type='text/csv'
                )
                print(f" Test сохранен как CSV: {test_path}")
            except Exception as e2:
                print(f" Ошибка при сохранении test: {e2}")

    # 3. Сохраняем метаданные
    if split_info is None:
        # Определяем период данных
        if date_col in train_df.columns:
            train_min = str(pd.to_datetime(train_df[date_col]).min().date())
            train_max = str(pd.to_datetime(train_df[date_col]).max().date())
        else:
            train_min = train_max = 'unknown'

        if test_df is not None and date_col in test_df.columns:
            test_min = str(pd.to_datetime(test_df[date_col]).min().date())
            test_max = str(pd.to_datetime(test_df[date_col]).max().date())
        else:
            test_min = test_max = 'unknown'

        split_info = {
            'product': product_name,
            'product_clean': clean_name,
            'version': version,
            'train_size': len(train_df),
            'test_size': len(test_df) if test_df is not None else 0,
            'train_period': {
                'start': train_min,
                'end': train_max
            },
            'test_period': {
                'start': test_min,
                'end': test_max
            },
            'features': list(train_df.columns),
            'feature_count': len(train_df.columns),
            'target_column': 'quantity' if 'quantity' in train_df.columns else 'Количество',
            'created_at': datetime.now().isoformat(),
            'minio_endpoint': 'host.docker.internal:9002',
            'bucket': bucket_name
        }

    meta_buffer = BytesIO()
    meta_buffer.write(json.dumps(split_info, indent=2, ensure_ascii=False).encode())
    meta_buffer.seek(0)

    meta_path = f"{base_path}/split_info_{version}.json"
    client.put_object(
        bucket_name,
        meta_path,
        data=meta_buffer,
        length=meta_buffer.getbuffer().nbytes,
        content_type='application/json'
    )
    print(f" Метаданные сохранены: {meta_path}")

    print(f"\n ВСЕ ФАЙЛЫ СОХРАНЕНЫ:")
    for f in saved_files:
        print(f"   - {f}")

    return {
        'train_path': train_path,
        'test_path': test_path,
        'meta_path': meta_path,
        'version': version,
        'bucket': bucket_name,
        'files': saved_files,
        'split_info': split_info
    }


def load_datasets_from_minio(
        bucket_name="ml-datasets",
        product_name=None,
        version=None,
        latest=True
):
    """
    Загружает датасеты из Minio
    """
    print(f"\n{'='*60}")
    print(f" ЗАГРУЗКА ДАТАСЕТА ИЗ MINIO")
    print('='*60)

    try:
        client = Minio(
            endpoint="host.docker.internal:9002",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )
    except Exception as e:
        print(f" Ошибка подключения к Minio: {e}")
        return None, None, None

    clean_name = re.sub(r'[<>:"/\\|?*%\'"]', '_', product_name)
    clean_name = clean_name[:50]

    base_path = f"datasets/{clean_name}/train_test_split"

    if latest:
        # Находим последнюю версию
        try:
            objects = list(client.list_objects(bucket_name, prefix=base_path, recursive=True))
            versions = set()
            for obj in objects:
                if 'train_' in obj.object_name:
                    ver = obj.object_name.split('train_')[-1].split('.parquet')[0]
                    versions.add(ver)

            if not versions:
                print(f" Нет датасетов для продукта {product_name}")
                return None, None, None

            version = sorted(versions)[-1]
            print(f" Загружаем последнюю версию: {version}")
        except Exception as e:
            print(f" Ошибка при поиске версий: {e}")
            return None, None, None

    try:
        # Загружаем train
        train_path = f"{base_path}/train_{version}.parquet"
        train_response = client.get_object(bucket_name, train_path)
        train_df = pd.read_parquet(BytesIO(train_response.read()))
        print(f" Train загружен: {len(train_df)} записей")

        # Загружаем test
        test_path = f"{base_path}/test_{version}.parquet"
        test_response = client.get_object(bucket_name, test_path)
        test_df = pd.read_parquet(BytesIO(test_response.read()))
        print(f" Test загружен: {len(test_df)} записей")

        # Загружаем метаданные
        meta_path = f"{base_path}/split_info_{version}.json"
        meta_response = client.get_object(bucket_name, meta_path)
        meta_info = json.loads(meta_response.read().decode())
        print(f" Метаданные загружены")

        return train_df, test_df, meta_info

    except Exception as e:
        print(f" Ошибка при загрузке: {e}")
        return None, None, None


def save_features_to_minio(
        X_train, X_test, y_train, y_test,
        feature_names,
        product_name,
        version=None
):
    """
    Сохраняет признаки и целевые переменные для модели
    """
    print(f"\n{'='*60}")
    print(f" СОХРАНЕНИЕ ПРИЗНАКОВ В MINIO")
    print('='*60)

    try:
        client = Minio(
            endpoint="host.docker.internal:9002",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )
    except Exception as e:
        print(f" Ошибка подключения к Minio: {e}")
        return None

    bucket_name = "ml-datasets"
    clean_name = re.sub(r'[<>:"/\\|?*%\'"]', '_', product_name)
    clean_name = clean_name[:50]

    if version is None:
        version = datetime.now().strftime('%Y%m%d_%H%M%S')

    base_path = f"features/{clean_name}/{version}"
    print(f" Путь: {base_path}")

    # Сохраняем признаки
    features_dict = {
        'X_train': X_train,
        'X_test': X_test,
        'y_train': y_train,
        'y_test': y_test
    }

    for name, data in features_dict.items():
        if data is None:
            continue

        buffer = BytesIO()

        # Обрабатываем разные типы данных
        if isinstance(data, pd.DataFrame):
            data.to_parquet(buffer, index=False)
            ext = 'parquet'
        elif isinstance(data, pd.Series):
            pd.DataFrame({name: data}).to_parquet(buffer, index=False)
            ext = 'parquet'
        elif isinstance(data, np.ndarray):
            if data.ndim == 1:
                pd.DataFrame({name: data}).to_parquet(buffer, index=False)
            else:
                pd.DataFrame(data, columns=[f'feature_{i}' for i in range(data.shape[1])]).to_parquet(buffer, index=False)
            ext = 'parquet'
        else:
            buffer.write(json.dumps({'data': data}, ensure_ascii=False).encode())
            ext = 'json'

        buffer.seek(0)
        file_path = f"{base_path}/{name}.{ext}"
        client.put_object(
            bucket_name,
            file_path,
            data=buffer,
            length=buffer.getbuffer().nbytes,
            content_type=f'application/{ext}'
        )
        print(f" {name}.{ext} сохранен")

    # Сохраняем метаданные признаков
    features_meta = {
        'product': product_name,
        'version': version,
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'X_train_shape': str(X_train.shape) if hasattr(X_train, 'shape') else None,
        'X_test_shape': str(X_test.shape) if hasattr(X_test, 'shape') else None,
        'y_train_shape': str(y_train.shape) if hasattr(y_train, 'shape') else None,
        'y_test_shape': str(y_test.shape) if hasattr(y_test, 'shape') else None,
        'created_at': datetime.now().isoformat()
    }

    meta_buffer = BytesIO()
    meta_buffer.write(json.dumps(features_meta, indent=2).encode())
    meta_buffer.seek(0)

    meta_path = f"{base_path}/features_meta.json"
    client.put_object(
        bucket_name,
        meta_path,
        data=meta_buffer,
        length=meta_buffer.getbuffer().nbytes,
        content_type='application/json'
    )
    print(f" features_meta.json сохранен")

    print(f"\n ВСЕ ПРИЗНАКИ СОХРАНЕНЫ В {bucket_name}/{base_path}")

    return {
        'path': base_path,
        'version': version,
        'bucket': bucket_name,
        'meta': features_meta
    }


# ============================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ ПОСЛЕ ОБУЧЕНИЯ
# ============================================

def save_model_artifacts(model, X_train, X_test, y_train, y_test,
                         product_name, feature_names, metrics=None):
    """
    Сохраняет все артефакты модели одним вызовом
    """
    version = datetime.now().strftime('%Y%m%d_%H%M%S')

    print(f"\n{'='*60}")
    print(f" СОХРАНЕНИЕ АРТЕФАКТОВ МОДЕЛИ")
    print('='*60)

    # 1. Сохраняем датасеты
    train_df = X_train.copy()
    if isinstance(y_train, pd.Series):
        train_df['target'] = y_train.values
    else:
        train_df['target'] = y_train

    test_df = X_test.copy()
    if isinstance(y_test, pd.Series):
        test_df['target'] = y_test.values
    else:
        test_df['target'] = y_test

    dataset_result = save_datasets_to_minio(
        train_df=train_df,
        test_df=test_df,
        product_name=product_name,
        version=version
    )

    # 2. Сохраняем признаки отдельно
    features_result = save_features_to_minio(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        feature_names=feature_names,
        product_name=product_name,
        version=version
    )

    # 3. Сохраняем модель
    model_buffer = BytesIO()
    pickle.dump(model, model_buffer)
    model_buffer.seek(0)

    client = Minio(
        endpoint="host.docker.internal:9002",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )

    clean_name = re.sub(r'[<>:"/\\|?*%\'"]', '_', product_name)
    clean_name = clean_name[:50]

    model_path = f"models/{clean_name}/{version}/model.pkl"
    client.put_object(
        "ml-datasets",
        model_path,
        data=model_buffer,
        length=model_buffer.getbuffer().nbytes,
        content_type='application/octet-stream'
    )
    print(f" Модель сохранена: {model_path}")

    # 4. Сохраняем метрики
    if metrics:
        metrics_buffer = BytesIO()
        metrics_buffer.write(json.dumps(metrics, indent=2).encode())
        metrics_buffer.seek(0)

        metrics_path = f"models/{clean_name}/{version}/metrics.json"
        client.put_object(
            "ml-datasets",
            metrics_path,
            data=metrics_buffer,
            length=metrics_buffer.getbuffer().nbytes,
            content_type='application/json'
        )
        print(f" Метрики сохранены: {metrics_path}")

    print(f"\n ВСЕ АРТЕФАКТЫ СОХРАНЕНЫ ВЕРСИИ {version}")

    return {
        'version': version,
        'datasets': dataset_result,
        'features': features_result,
        'model_path': model_path
    }