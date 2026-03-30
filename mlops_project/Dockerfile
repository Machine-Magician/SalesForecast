# Используем официальный образ Airflow как основу
FROM apache/airflow:2.7.1-python3.10

# Устанавливаем нужные пакеты
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    xgboost \
    scikit-learn \
    pandas \
    numpy \
    clickhouse-driver \
    minio \
    papermill

# Копируем скрипты в контейнер
COPY scripts/ /opt/airflow/scripts/