from clickhouse_driver import Client
import json
import requests
import time

client = Client(host='my_clickhouse', port=9000, user='default', password='', database='external_data')

# Получаем список городов
cities = client.execute("SELECT DISTINCT `город` FROM sales_raw WHERE `город` IS NOT NULL AND `город` != ''")
cities = [c[0] for c in cities]

print(f"Найдено {len(cities)} городов")

# Загружаем существующие координаты
with open('/opt/airflow/scripts/city_coordinates.json', 'r') as f:
    city_coords = json.load(f)

# Функция для получения координат через API
def get_coords(city_name):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=ru&format=json"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if 'results' in data and len(data['results']) > 0:
            result = data['results'][0]
            return {"lat": result['latitude'], "lon": result['longitude']}
    except Exception as e:
        print(f"    Ошибка: {e}")
    return None

# Обновляем координаты для городов, у которых координаты Москвы
updated = 0
not_found = []
for city in cities:
    if city in city_coords and city_coords[city]["lat"] == 55.7558 and city_coords[city]["lon"] == 37.6173:
        print(f"Ищем координаты для {city}...")
        coords = get_coords(city)
        if coords:
            city_coords[city] = coords
            updated += 1
            print(f"  ✅ {coords['lat']}, {coords['lon']}")
        else:
            not_found.append(city)
            print(f"  ❌ не найдено")
        time.sleep(0.5)

# Сохраняем
with open('/opt/airflow/scripts/city_coordinates.json', 'w') as f:
    json.dump(city_coords, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"✅ Обновлено координат для {updated} городов")
print(f"❌ Не найдено: {len(not_found)} городов")
if not_found:
    print(f"   {not_found[:10]}")
print(f"✅ Всего городов в файле: {len(city_coords)}")
