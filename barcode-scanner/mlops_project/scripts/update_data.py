# ~/mlops_project/scripts/update_data.py

from database_checker import DatabaseChecker
from clickhouse_driver import Client
import pandas as pd
from datetime import datetime, timedelta

def update_sales_data():
    """Загружает только новые данные (с последней даты в ClickHouse)"""
    checker = DatabaseChecker(use_sa_login=True)
    client = Client(host='my_clickhouse', port=9000, user='default', password='')

    # 1. Узнаём последнюю дату в ClickHouse
    result = client.execute("SELECT MAX(toDate(`Дата`)) FROM external_data.sales_raw")
    last_date = result[0][0]

    if last_date:
        start_date = last_date + timedelta(days=1)
        print(f" Последняя дата в базе: {last_date}")
        print(f" Загружаем с: {start_date}")
    else:
        start_date = datetime(2025, 1, 1)
        print(f" База пуста, загружаем с: {start_date}")

    end_date = datetime.now()

    if start_date > end_date:
        print(" Данные уже актуальны, новых записей нет")
        return "Нет новых данных"

    total_inserted = 0
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')

        # Запрос к MSSQL за конкретный день
        query = f"""
        SELECT 
            nomenklatura._Description as Номенклатура,
            DATEADD(year, -2000, [Дата]) as Дата,
            [Количество],
            [Цена],
            [Сумма],
            [НДС],
            kontrag._Description as Контрагент,
            organ._Description as Организация,
            SSO._description as город
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
        WHERE CAST(DATEADD(year, -2000, [Дата]) AS DATE) = '{date_str}'
            and svoystvoOB._description like '%Населенный пункт%'
        """

        conn = checker.get_connection()
        print(f" Читаем {date_str}...")

        chunks = []
        for chunk in pd.read_sql(query, conn, chunksize=50000):
            chunks.append(chunk)
            print(f"   Прочитано {len(chunk)} записей")

        df_day = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        conn.close()

        if not df_day.empty:
            data_to_insert = [tuple(x) for x in df_day.to_numpy()]
            client.execute("INSERT INTO external_data.sales_raw VALUES", data_to_insert)
            total_inserted += len(data_to_insert)
            print(f" {date_str}: загружено {len(data_to_insert)} записей")
        else:
            print(f" {date_str}: нет данных")

        current_date += timedelta(days=1)

    # Итог
    total = client.execute("SELECT COUNT(*) FROM external_data.sales_raw")[0][0]
    print(f"\n Всего записей в ClickHouse: {total}")
    print(f" Добавлено новых: {total_inserted}")

    return f"Загружено {total_inserted} новых записей"