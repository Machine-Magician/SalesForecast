import numpy as np
import pandas as pd
import os
from pathlib import Path
from dotenv import load_dotenv
import re
import platform
import pymssql  # вместо pyodbc
from datetime import datetime, timedelta

# Загружаем переменные из .env файла
load_dotenv('/home/jovyan/work/.env')

class DatabaseChecker:
    """Класс для изъятия цен на прошедшие продажи из БД"""

    def __init__(self, use_sa_login=True):
        """
        use_sa_login: если True, использует SQL-логин (sa)
                     если False, использует доменную аутентификацию (только для Windows)
        """
        # Определяем, где мы запущены
        self.is_windows = platform.system() == 'Windows'
        self.is_linux = platform.system() == 'Linux'

        # Берем настройки из .env или используем значения по умолчанию
        self.db_host = os.getenv("DB_HOST", "172.16.0.108")
        self.db_name = os.getenv("DB_NAME", "ВитринаДанных")

        if self.is_linux or use_sa_login:
            # В контейнере используем SQL-логин (sa)
            self.db_user = os.getenv("DB_USER", "sa")
            self.db_password = os.getenv("DB_PASSWORD", "sasa")
            self.auth_type = "SQL логин"
        else:
            # На Windows (локально) оставляем доменную аутентификацию
            self.db_user = None
            self.db_password = None
            self.auth_type = "Windows аутентификация"

        print(f" Подключение через {self.auth_type}")
        print(f"   Сервер: {self.db_host}/{self.db_name}")
        if self.db_user:
            print(f"   Пользователь: {self.db_user}")

        # Не создаём engine заранее, будем создавать подключение при каждом запросе
        self.connection = None

    def get_connection(self):
        """Создаёт подключение к БД"""
        if self.is_windows and not self.db_user:
            # Для Windows с доменной аутентификацией
            import pyodbc
            conn_str = (
                f"DRIVER={os.getenv('DB_DRIVER', 'SQL Server')};"
                f"SERVER={self.db_host};"
                f"DATABASE={self.db_name};"
                f"Trusted_Connection=yes;"
                f"Connection Timeout=120;"
            )
            return pyodbc.connect(conn_str)
        else:
            # Для Linux или SQL-логина
            return pymssql.connect(
                server=self.db_host,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
                timeout=120,
                login_timeout=120,
                charset='UTF-8'
            )

    def get_sales_data(self, name=None, years_back=1) -> pd.DataFrame:
        """
        Получает агрегированные данные по продажам для указанной номенклатуры
        Возвращает одну строку на комбинацию товар + контрагент + город
        """
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=years_back*365)).strftime('%Y-%m-%d')

        if name is None:
            name = input("Название номенклатуры: ")

        try:
            query = """
            SELECT 
                nomenklatura._Description as [Номенклатура],
                COUNT(*) as [Количество_записей],
                SUM([Сумма]) as [Общая_сумма],
                AVG([Количество]) as [Среднее_количество],
                MIN(DATEADD(year, -2000, [Дата])) as [Первая_продажа],
                MAX(DATEADD(year, -2000, [Дата])) as [Последняя_продажа],
                kontrag._Description as [Контрагент],
                organ._Description as [Организация],
                SSO._description as [город]
            FROM [ВитринаДанных].[dbo].[ПродажиПервичные] as vypuskProduktNakoplenie
            inner join [onec-9].upp_2012.dbo._Reference154 as nomenklatura
                on nomenklatura._Idrref = vypuskProduktNakoplenie.[НоменклатураИД]
            left join [onec-9].upp_2012.dbo._Reference124 as kontrag
                on kontrag._Idrref = vypuskProduktNakoplenie.[КонтрагентИД]
            left join [onec-9].upp_2012.dbo._Reference164 as organ
                on organ._Idrref = vypuskProduktNakoplenie.[ОрганизацияИД]
            left join [onec-9].upp_2012.dbo._InfoRg19780 as zna4svoy
                on zna4svoy._fld19781_RRRef = vypuskProduktNakoplenie.[ОрганизацияИД]
            left join [onec-9].upp_2012.dbo._InfoRg19780 as obect
                on obect._fld19781_rrref = kontrag._idrref
            left join [onec-9].upp_2012.dbo._Chrc1140 as svoystvoOB
                on svoystvoOB._idrref = obect._fld19782rref
            left join [onec-9].upp_2012.dbo._reference97 as SSO
                on SSO._idrref = obect._fld19783_rrref
            WHERE nomenklatura._Description = %s
                and DATEADD(year, -2000, [Дата]) > %s
                and svoystvoOB._description like '%Населенный пункт%'
            GROUP BY nomenklatura._Description,
                    kontrag._Description,
                    organ._Description,
                    SSO._description
            HAVING COUNT(*) >= 300
            ORDER BY SUM([Сумма]) DESC
            """

            conn = self.get_connection()
            df = pd.read_sql(query, conn, params=(name, cutoff_date))
            conn.close()

            if len(df) > 0:
                print(f"\n Найдено {len(df)} агрегированных записей для '{name}'")
                return df
            else:
                print(f" Нет данных для '{name}'")
                return pd.DataFrame()

        except Exception as e:
            print(f" Ошибка запроса: {e}")
            return pd.DataFrame()

    def get_products_with_min_records(self, min_records=300, years_back=1):
        """
        Получает список товаров с количеством записей не меньше min_records
        Возвращает DataFrame с колонками: Номенклатура, записей, сумма, первая_дата, последняя_дата
        """
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=years_back*365)).strftime('%Y-%m-%d')

        query = """
        SELECT 
            nomenklatura._Description as [Номенклатура],
            COUNT(*) as [Количество_записей],
            SUM([Сумма]) as [Общая_сумма],
            MIN(DATEADD(year, -2000, [Дата])) as [Первая_продажа],
            MAX(DATEADD(year, -2000, [Дата])) as [Последняя_продажа]
        FROM [ВитринаДанных].[dbo].[ПродажиПервичные] as vypuskProduktNakoplenie
        inner join [onec-9].upp_2012.dbo._Reference154 as nomenklatura
            on nomenklatura._Idrref = vypuskProduktNakoplenie.[НоменклатураИД]
        WHERE DATEADD(year, -2000, [Дата]) > %s
        GROUP BY nomenklatura._Description
        HAVING COUNT(*) >= %s
        ORDER BY COUNT(*) DESC
        """

        conn = self.get_connection()
        df = pd.read_sql(query, conn, params=(cutoff_date, min_records))
        conn.close()

        print(f" Найдено {len(df)} товаров с >= {min_records} записями")
        return df

    def get_detailed_sales_data(self, name=None, years_back=1, limit=50000) -> pd.DataFrame:
        """Получает ДЕТАЛЬНЫЕ данные по продажам для указанной номенклатуры"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=years_back*365)

        if name is None:
            name = input("Название номенклатуры: ")

        try:
            query = """
            SELECT TOP %s nomenklatura._Description as [Номенклатура],
                DATEADD(year, -2000, [Дата]) as [Дата],
                [Количество],
                [Цена],
                [Сумма],
                [НДС],
                kontrag._Description as [Контрагент],
                organ._Description as [Организация],
                SSO._description as [город]
            FROM [ВитринаДанных].[dbo].[ПродажиПервичные] as vypuskProduktNakoplenie
            inner join [onec-9].upp_2012.dbo._Reference154 as nomenklatura
                on nomenklatura._Idrref = vypuskProduktNakoplenie.[НоменклатураИД]
            left join [onec-9].upp_2012.dbo._Reference124 as kontrag
                on kontrag._Idrref = vypuskProduktNakoplenie.[КонтрагентИД]
            left join [onec-9].upp_2012.dbo._Reference164 as organ
                on organ._Idrref = vypuskProduktNakoplenie.[ОрганизацияИД]
            left join [onec-9].upp_2012.dbo._InfoRg19780 as zna4svoy
                on zna4svoy._fld19781_RRRef = vypuskProduktNakoplenie.[ОрганизацияИД]
            left join [onec-9].upp_2012.dbo._InfoRg19780 as obect
                on obect._fld19781_rrref = kontrag._idrref
            left join [onec-9].upp_2012.dbo._Chrc1140 as svoystvoOB
                on svoystvoOB._idrref = obect._fld19782rref
            left join [onec-9].upp_2012.dbo._reference97 as SSO
                on SSO._idrref = obect._fld19783_rrref
            WHERE nomenklatura._Description = %s
                and DATEADD(year, -2000, [Дата]) > %s
                and svoystvoOB._description like '%Населенный пункт%'
            ORDER BY [Дата] DESC
            """

            conn = self.get_connection()
            df = pd.read_sql(query, conn, params=(limit, name, cutoff_date))
            conn.close()

            if len(df) > 0:
                print(f"\n Найдено {len(df)} детальных записей для '{name}'")
                return df
            else:
                print(f" Нет данных для '{name}'")
                return pd.DataFrame()

        except Exception as e:
            print(f" Ошибка запроса: {e}")
            return pd.DataFrame()
    # Функция для выгрузки всех данных за период
def load_all_sales_to_clickhouse(checker, years_back=1, clean_first=True):
    """Выгружает ВСЕ продажи за период и сохраняет в ClickHouse"""
    from datetime import datetime, timedelta
    from clickhouse_driver import Client
    import pandas as pd

    cutoff_date = datetime.now() - timedelta(days=years_back*365)

    query = """
    SELECT 
        nomenklatura._Description as [Номенклатура],
        DATEADD(year, -2000, [Дата]) as [Дата],
        [Количество],
        [Цена],
        [Сумма],
        [НДС],
        kontrag._Description as [Контрагент],
        organ._Description as [Организация],
        SSO._description as [город]
    FROM [ВитринаДанных].[dbo].[ПродажиПервичные] as vypuskProduktNakoplenie
    inner join [onec-9].upp_2012.dbo._Reference154 as nomenklatura
        on nomenklatura._Idrref = vypuskProduktNakoplenie.[НоменклатураИД]
    left join [onec-9].upp_2012.dbo._Reference124 as kontrag
        on kontrag._Idrref = vypuskProduktNakoplenie.[КонтрагентИД]
    left join [onec-9].upp_2012.dbo._Reference164 as organ
        on organ._Idrref = vypuskProduktNakoplenie.[ОрганизацияИД]
    left join [onec-9].upp_2012.dbo._InfoRg19780 as zna4svoy
        on zna4svoy._fld19781_RRRef = vypuskProduktNakoplenie.[ОрганизацияИД]
    left join [onec-9].upp_2012.dbo._InfoRg19780 as obect
        on obect._fld19781_rrref = kontrag._idrref
    left join [onec-9].upp_2012.dbo._Chrc1140 as svoystvoOB
        on svoystvoOB._idrref = obect._fld19782rref
    left join [onec-9].upp_2012.dbo._reference97 as SSO
        on SSO._idrref = obect._fld19783_rrref
    WHERE DATEADD(year, -2000, [Дата]) > %s
        and svoystvoOB._description like '%Населенный пункт%'
    ORDER BY [Дата] DESC
    """

    conn = checker.get_connection()
    print(" Выгружаем все данные из MSSQL...")

    chunks = []
    for chunk in pd.read_sql(query, conn, params=(cutoff_date,), chunksize=50000):
        chunks.append(chunk)
        print(f"   Загружено {len(chunk)} записей...")

    df_all = pd.concat(chunks, ignore_index=True)
    conn.close()

    print(f"\n Всего выгружено: {len(df_all)} записей")

    client = Client(host='my_clickhouse', port=9000, user='default', password='')

    if clean_first:
        print(" Очищаем таблицу sales_raw...")
        client.execute("TRUNCATE TABLE external_data.sales_raw")
        print(" Таблица очищена")

    data_to_insert = [tuple(x) for x in df_all.to_numpy()]
    print(f" Загружаем {len(data_to_insert)} записей в ClickHouse...")
    client.execute("INSERT INTO external_data.sales_raw VALUES", data_to_insert)

    print(f" Данные сохранены в ClickHouse")
    return df_all

# ============================================
# 2. ТЕПЕРЬ РАБОТАЕМ ТОЛЬКО С CLICKHOUSE
# ============================================

from clickhouse_driver import Client
ch_client = Client(host='my_clickhouse', port=9000, user='default', password='')

products_df = ch_client.query_dataframe("""
    SELECT 
        `Номенклатура`,
        COUNT(*) as cnt,
        SUM(`Сумма`) as total_sum
    FROM external_data.sales_raw
    GROUP BY `Номенклатура`
    HAVING cnt >= 300
    ORDER BY cnt DESC
""")

all_products = products_df['Номенклатура'].tolist()
print(f" Товаров с >=300 записями: {len(all_products)}")

# Для выборки по конкретному товару тоже экранируем
for product in all_products[:10]:
    df = ch_client.query_dataframe(f"""
        SELECT * FROM external_data.sales_raw
        WHERE `Номенклатура` = '{product}'
        ORDER BY `Дата` DESC
    """)
    print(f" {product[:50]}: {len(df)} записей")