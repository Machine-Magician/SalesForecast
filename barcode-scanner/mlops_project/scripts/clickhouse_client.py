from clickhouse_driver import Client

def get_client():
    """Возвращает подключение к ClickHouse"""
    return Client(
        host='my_clickhouse',
        port=9000,
        user='default',
        password='',
        database='external_data'
    )