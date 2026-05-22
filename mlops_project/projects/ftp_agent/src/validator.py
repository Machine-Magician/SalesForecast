#!/usr/bin/env python3
"""FTP файлов валидатор + создание эмбеддингов"""

from pathlib import Path
from datetime import datetime, timedelta
from clickhouse_driver import Client
from sentence_transformers import SentenceTransformer
import json
import os


def main():
    # Подключение к ClickHouse
    client = Client(host='my_clickhouse', port=9000, user='default', password='', settings={'async_insert': 0})

    # Загружаем модель эмбеддингов
    print("Загрузка модели...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Модель загружена")

    # Загружаем маппинг
    result = client.execute("SELECT file_name, proc_name, column_mapping, delimiter FROM procedures_metadata.file_mapping")
    mapping = {}
    for row in result:
        file_name, proc_name, column_mapping, delimiter = row
        mapping[file_name] = {"proc_name": proc_name, "delimiter": delimiter, **json.loads(column_mapping)}

    # Сканируем файлы
    ftp_base = Path("/home/jovyan/work/ftp_local")
    cutoff_date = datetime.now() - timedelta(days=7)

    validation_results = []
    embeddings_batch = []
    batch_size = 50
    total_files = 0

    for region in ftp_base.iterdir():
        if not region.is_dir():
            continue
        print(f"\n {region.name}")

        for folder in region.iterdir():
            if not folder.is_dir():
                continue
            try:
                folder_date = datetime.strptime(folder.name, '%Y-%m-%d')
                if folder_date < cutoff_date:
                    continue
            except:
                continue

            for file_path in folder.glob("DMT_*.txt"):
                total_files += 1
                file_name = file_path.name

                # ========== 1. ВАЛИДАЦИЯ ==========
                if file_name in mapping:
                    errors = []
                    try:
                        with open(file_path, 'r', encoding='windows-1251') as f:
                            lines = f.readlines()
                        if not lines:
                            errors.append("File is empty")
                        else:
                            expected = mapping[file_name]["columns"]
                            delim = mapping[file_name]["delimiter"]
                            for i, line in enumerate(lines, 1):
                                if not line.strip():
                                    continue
                                if len(line.strip().split(delim)) != expected:
                                    errors.append(f"Line {i}: wrong columns")
                        status = "ERROR" if errors else "OK"
                        validation_results.append((region.name, folder.name, file_name, status, "; ".join(errors)))
                    except Exception as e:
                        validation_results.append((region.name, folder.name, file_name, "ERROR", str(e)[:200]))
                else:
                    validation_results.append((region.name, folder.name, file_name, "UNKNOWN", "No mapping"))

                # ========== 2. ЭМБЕДДИНГИ ==========
                try:
                    with open(file_path, 'r', encoding='windows-1251') as f:
                        content = f.read()[:3000]

                    embedding = model.encode(content).tolist()
                    embeddings_batch.append((file_name, region.name, folder_date.date(), content, embedding))

                    if len(embeddings_batch) >= batch_size:
                        client.execute(
                            "INSERT INTO procedures_metadata.file_embeddings (file_name, region, folder_date, content, embedding) VALUES",
                            embeddings_batch
                        )
                        print(f"   Вставлено {len(embeddings_batch)} эмбеддингов...")
                        embeddings_batch = []

                except Exception as e:
                    print(f"    Ошибка эмбеддинга {file_name}: {str(e)[:50]}")

    # Вставляем остатки эмбеддингов
    if embeddings_batch:
        client.execute(
            "INSERT INTO procedures_metadata.file_embeddings (file_name, region, folder_date, content, embedding) VALUES",
            embeddings_batch
        )
        print(f"   Вставлено {len(embeddings_batch)} эмбеддингов...")

    # Сохраняем результаты валидации
    client.execute("""
        INSERT INTO procedures_metadata.validation_log (region, folder_date, file_name, status, error_message)
        VALUES
    """, validation_results)

    print(f"\n📊 ИТОГО:")
    print(f"   Проверено файлов: {total_files}")
    print(f"   Валидация сохранена: {len(validation_results)} записей")
    print(f"   Эмбеддинги сохранены: проверь через SELECT COUNT(*) FROM procedures_metadata.file_embeddings")

if __name__ == "__main__":
    main()