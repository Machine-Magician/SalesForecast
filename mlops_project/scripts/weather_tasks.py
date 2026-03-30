# weather_tasks.py
from clickhouse_driver import Client
from datetime import datetime, timedelta
import requests
import time

def fetch_openmeteo_for_city(city, lat, lon, start_date, end_date):
    """Собирает данные для одного города за период"""
    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        'latitude': lat,
        'longitude': lon,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'daily': ['temperature_2m_mean', 'relative_humidity_2m_mean',
                  'precipitation_sum', 'pressure_msl_mean', 'wind_speed_10m_mean'],
        'timezone': 'Europe/Moscow'
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()

        if 'error' in data:
            return []

        records = []
        dates = data['daily']['time']

        for i in range(len(dates)):
            temp = data['daily']['temperature_2m_mean'][i]
            if temp is None:
                continue

            dt = datetime.strptime(dates[i], '%Y-%m-%d')
            timestamp = datetime(dt.year, dt.month, dt.day, 12, 0, 0)

            records.append((
                city,
                timestamp,
                temp,
                data['daily']['relative_humidity_2m_mean'][i] or 0,
                data['daily']['pressure_msl_mean'][i] or 1013,
                (data['daily']['wind_speed_10m_mean'][i] or 0) / 3.6,
                data['daily']['precipitation_sum'][i] or 0,
                'historical'
            ))
        return records
    except Exception as e:
        print(f"Ошибка для {city}: {e}")
        return []

def collect_weather_for_all_cities(years_back=2):
    """
    Собирает погоду за последние years_back лет
    Только для отсутствующих дат
    """
    client = Client(
        host='my_clickhouse',
        port=9000,
        user='default',
        password='',
        database='external_data'
    )

    # Загружаем координаты (нужно сохранить из Jupyter)
    import json
    with open('/home/jovyan/work/scripts/city_coordinates.json', 'r') as f:
        city_coords = json.load(f)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years_back)

    total_saved = 0

    for city, coords in city_coords.items():
        # Получаем последнюю дату в таблице
        result = client.execute(f"""
            SELECT MAX(timestamp) 
            FROM weather_hourly 
            WHERE city = '{city}'
        """)
        last_date = result[0][0]

        if last_date:
            # Собираем только после последней даты
            start = last_date + timedelta(days=1)
            if start > end_date:
                continue
        else:
            start = start_date

        records = fetch_openmeteo_for_city(city, coords['lat'], coords['lon'], start, end_date)

        if records:
            client.execute(
                "INSERT INTO weather_hourly (city, timestamp, temperature, humidity, pressure, wind_speed, precipitation, weather_condition) VALUES",
                records
            )
            total_saved += len(records)
            print(f"{city}: добавлено {len(records)} записей")

        time.sleep(1)

    print(f"Всего добавлено {total_saved} записей")
    return total_saved