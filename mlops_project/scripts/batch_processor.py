# ~/mlops_project/scripts/batch_processor.py

import re
import numpy as np
import pandas as pd
import json
import ast
from datetime import datetime
from clickhouse_driver import Client
import os
from feature_engineering import (
    create_time_features,
    create_lag_features,
    create_org_features,
    create_type_features
)


# Расширенный словарь сопоставления (добавьте все ваши города!)
city_to_region = {
    # Центральный федеральный округ
    'Москва': 'г. Москва',
    'Московская область': 'Московская область',
    'Дмитров': 'Московская область',
    'Ногинск': 'Московская область',
    'Подольск': 'Московская область',
    'Мытищи': 'Московская область',
    'Люберцы': 'Московская область',
    'Красногорск': 'Московская область',
    'Одинцово': 'Московская область',
    'Химки': 'Московская область',
    'Балашиха': 'Московская область',

    'Воронеж': 'Воронежская область',
    'Воронежская область': 'Воронежская область',
    'Борисоглебск': 'Воронежская область',
    'Бобров': 'Воронежская область',
    'Семилуки': 'Воронежская область',
    'Лиски': 'Воронежская область',
    'Острогожск': 'Воронежская область',
    'Россошь': 'Воронежская область',

    'Тула': 'Тульская область',
    'Тульская область': 'Тульская область',
    'Новомосковск': 'Тульская область',
    'Алексин': 'Тульская область',
    'Щекино': 'Тульская область',

    'Орел': 'Орловская область',
    'Орловская область': 'Орловская область',
    'Ливны': 'Орловская область',
    'Мценск': 'Орловская область',

    'Курск': 'Курская область',
    'Курская область': 'Курская область',
    'Железногорск': 'Курская область',
    'Курчатов': 'Курская область',

    'Смоленск': 'Смоленская область',
    'Смоленская область': 'Смоленская область',
    'Вязьма': 'Смоленская область',
    'Рославль': 'Смоленская область',
    'Ярцево': 'Смоленская область',
    'Гагарин': 'Смоленская область',
    'Велиж': 'Смоленская область',
    'Демидов': 'Смоленская область',

    'Брянск': 'Брянская область',
    'Брянская область': 'Брянская область',
    'Клинцы': 'Брянская область',
    'Новозыбков': 'Брянская область',

    'Тамбов': 'Тамбовская область',
    'Тамбовская область': 'Тамбовская область',
    'Мичуринск': 'Тамбовская область',

    'Ярославль': 'Ярославская область',
    'Ярославская область': 'Ярославская область',
    'Рыбинск': 'Ярославская область',
    'Переславль-Залесский': 'Ярославская область',

    'Иваново': 'Ивановская область',
    'Ивановская область': 'Ивановская область',
    'Кинешма': 'Ивановская область',
    'Шуя': 'Ивановская область',

    'Владимир': 'Владимирская область',
    'Владимирская область': 'Владимирская область',
    'Муром': 'Владимирская область',
    'Ковров': 'Владимирская область',
    'Александров': 'Владимирская область',

    'Вологда': 'Вологодская область',
    'Вологодская область': 'Вологодская область',
    'Череповец': 'Вологодская область',
    'Сокол': 'Вологодская область',
    'Великий Устюг': 'Вологодская область',

    'Калуга': 'Калужская область',
    'Калужская область': 'Калужская область',
    'Обнинск': 'Калужская область',

    'Рязань': 'Рязанская область',
    'Рязанская область': 'Рязанская область',
    'Касимов': 'Рязанская область',

    'Тверь': 'Тверская область',
    'Тверская область': 'Тверская область',
    'Ржев': 'Тверская область',

    'Липецк': 'Липецкая область',
    'Липецкая область': 'Липецкая область',
    'Елец': 'Липецкая область',

    'Белгород': 'Белгородская область',
    'Белгородская область': 'Белгородская область',
    'Старый Оскол': 'Белгородская область',

    # Северо-Западный федеральный округ
    'Санкт-Петербург': 'г. Санкт-Петербург',
    'Ленинградская область': 'Ленинградская область',
    'Выборг': 'Ленинградская область',
    'Гатчина': 'Ленинградская область',
    'Тихвин': 'Ленинградская область',

    'В. Новгород': 'Новгородская область',
    'Новгородская область': 'Новгородская область',
    'Боровичи': 'Новгородская область',
    'Старая Русса': 'Новгородская область',

    'Псков': 'Псковская область',
    'Псковская область': 'Псковская область',
    'Великие Луки': 'Псковская область',

    'Петрозаводск': 'Республика Карелия',
    'Карелия': 'Республика Карелия',
    'Кондопога': 'Республика Карелия',
    'Сегежа': 'Республика Карелия',

    'Мурманск': 'Мурманская область',
    'Мурманская область': 'Мурманская область',
    'Апатиты': 'Мурманская область',
    'Североморск': 'Мурманская область',

    'Калининград': 'Калининградская область',
    'Калининградская область': 'Калининградская область',

    # Южный федеральный округ
    'Астрахань': 'Астраханская область',
    'Астраханская область': 'Астраханская область',
    'Ахтубинск': 'Астраханская область',
    'Знаменск': 'Астраханская область',

    'Волгоград': 'Волгоградская область',
    'Волгоградская область': 'Волгоградская область',
    'Волжский': 'Волгоградская область',
    'Камышин': 'Волгоградская область',
    'Михайловка': 'Волгоградская область',

    'Ростов-на-Дону': 'Ростовская область',
    'Ростовская область': 'Ростовская область',
    'Таганрог': 'Ростовская область',
    'Шахты': 'Ростовская область',
    'Новочеркасск': 'Ростовская область',
    'Волгодонск': 'Ростовская область',
    'Батайск': 'Ростовская область',
    'Новошахтинск': 'Ростовская область',

    'Краснодар': 'Краснодарский край',
    'Краснодарский край': 'Краснодарский край',
    'Сочи': 'Краснодарский край',
    'Новороссийск': 'Краснодарский край',
    'Армавир': 'Краснодарский край',
    'Ейск': 'Краснодарский край',
    'Кропоткин': 'Краснодарский край',
    'Славянск-на-Кубани': 'Краснодарский край',
    'Туапсе': 'Краснодарский край',
    'Лабинск': 'Краснодарский край',
    'Тихорецк': 'Краснодарский край',
    'Крымск': 'Краснодарский край',
    'Анапа': 'Краснодарский край',
    'Геленджик': 'Краснодарский край',

    'Симферополь': 'Республика Крым',
    'Крым': 'Республика Крым',
    'Севастополь': 'г. Севастополь',
    'Керчь': 'Республика Крым',
    'Ялта': 'Республика Крым',
    'Феодосия': 'Республика Крым',
    'Евпатория': 'Республика Крым',

    # Северо-Кавказский федеральный округ
    'Ставрополь': 'Ставропольский край',
    'Ставропольский край': 'Ставропольский край',
    'Пятигорск': 'Ставропольский край',
    'Кисловодск': 'Ставропольский край',
    'Ессентуки': 'Ставропольский край',
    'Минеральные Воды': 'Ставропольский край',
    'Георгиевск': 'Ставропольский край',
    'Буденновск': 'Ставропольский край',
    'Лермонтов': 'Ставропольский край',

    'Владикавказ': 'Республика Северная Осетия - Алания',
    'Северная Осетия': 'Республика Северная Осетия - Алания',
    'Моздок': 'Республика Северная Осетия - Алания',

    'Махачкала': 'Республика Дагестан',
    'Дагестан': 'Республика Дагестан',
    'Дербент': 'Республика Дагестан',
    'Хасавюрт': 'Республика Дагестан',
    'Каспийск': 'Республика Дагестан',

    'Грозный': 'Чеченская Республика',
    'Чечня': 'Чеченская Республика',

    'Нальчик': 'Кабардино-Балкарская Республика',
    'Кабардино-Балкария': 'Кабардино-Балкарская Республика',

    'Черкесск': 'Карачаево-Черкесская Республика',
    'Карачаево-Черкесия': 'Карачаево-Черкесская Республика',
    'Адыге-Хабль аул.': 'Карачаево-Черкесская Республика',

    'Майкоп': 'Республика Адыгея',
    'Адыгея': 'Республика Адыгея',

    'Назрань': 'Республика Ингушетия',
    'Ингушетия': 'Республика Ингушетия',

    # Приволжский федеральный округ
    'Нижний Новгород': 'Нижегородская область',
    'Нижегородская область': 'Нижегородская область',
    'Дзержинск': 'Нижегородская область',
    'Арзамас': 'Нижегородская область',
    'Саров': 'Нижегородская область',
    'Бор': 'Нижегородская область',
    'Кстово': 'Нижегородская область',
    'Павлово': 'Нижегородская область',
    'Выкса': 'Нижегородская область',
    'Балахна': 'Нижегородская область',

    'Казань': 'Республика Татарстан',
    'Татарстан': 'Республика Татарстан',
    'Набережные Челны': 'Республика Татарстан',
    'Нижнекамск': 'Республика Татарстан',
    'Альметьевск': 'Республика Татарстан',
    'Зеленодольск': 'Республика Татарстан',
    'Бугульма': 'Республика Татарстан',
    'Елабуга': 'Республика Татарстан',
    'Лениногорск': 'Республика Татарстан',
    'Чистополь': 'Республика Татарстан',

    'Самара': 'Самарская область',
    'Самарская область': 'Самарская область',
    'Тольятти': 'Самарская область',
    'Сызрань': 'Самарская область',
    'Новокуйбышевск': 'Самарская область',
    'Чапаевск': 'Самарская область',
    'Жигулевск': 'Самарская область',

    'Уфа': 'Республика Башкортостан',
    'Башкортостан': 'Республика Башкортостан',
    'Стерлитамак': 'Республика Башкортостан',
    'Салават': 'Республика Башкортостан',
    'Нефтекамск': 'Республика Башкортостан',
    'Октябрьский': 'Республика Башкортостан',

    'Пермь': 'Пермский край',
    'Пермский край': 'Пермский край',
    'Березники': 'Пермский край',
    'Соликамск': 'Пермский край',
    'Чайковский': 'Пермский край',
    'Лысьва': 'Пермский край',
    'Краснокамск': 'Пермский край',

    'Саратов': 'Саратовская область',
    'Саратовская область': 'Саратовская область',
    'Энгельс': 'Саратовская область',
    'Балаково': 'Саратовская область',
    'Вольск': 'Саратовская область',
    'Ртищево': 'Саратовская область',
    'Пугачев': 'Саратовская область',

    'Оренбург': 'Оренбургская область',
    'Оренбургская область': 'Оренбургская область',
    'Орск': 'Оренбургская область',
    'Новотроицк': 'Оренбургская область',
    'Бузулук': 'Оренбургская область',

    'Пенза': 'Пензенская область',
    'Пензенская область': 'Пензенская область',
    'Кузнецк': 'Пензенская область',
    'Заречный': 'Пензенская область',

    'Киров': 'Кировская область',
    'Кировская область': 'Кировская область',
    'Кирово-Чепецк': 'Кировская область',

    'Ижевск': 'Удмуртская Республика',
    'Удмуртия': 'Удмуртская Республика',
    'Сарапул': 'Удмуртская Республика',
    'Глазов': 'Удмуртская Республика',
    'Воткинск': 'Удмуртская Республика',

    'Ульяновск': 'Ульяновская область',
    'Ульяновская область': 'Ульяновская область',
    'Димитровград': 'Ульяновская область',

    'Саранск': 'Республика Мордовия',
    'Мордовия': 'Республика Мордовия',
    'Рузаевка': 'Республика Мордовия',

    'Чебоксары': 'Чувашская Республика',
    'Чувашия': 'Чувашская Республика',
    'Новочебоксарск': 'Чувашская Республика',

    'Йошкар-Ола': 'Республика Марий Эл',
    'Марий Эл': 'Республика Марий Эл',

    # Уральский федеральный округ
    'Екатеринбург': 'Свердловская область',
    'Свердловская область': 'Свердловская область',
    'Нижний Тагил': 'Свердловская область',
    'Каменск-Уральский': 'Свердловская область',
    'Первоуральск': 'Свердловская область',
    'Серов': 'Свердловская область',
    'Новоуральск': 'Свердловская область',
    'Асбест': 'Свердловская область',
    'Полевской': 'Свердловская область',
    'Ревда': 'Свердловская область',
    'Краснотурьинск': 'Свердловская область',

    'Челябинск': 'Челябинская область',
    'Челябинская область': 'Челябинская область',
    'Магнитогорск': 'Челябинская область',
    'Златоуст': 'Челябинская область',
    'Миасс': 'Челябинская область',
    'Копейск': 'Челябинская область',
    'Озерск': 'Челябинская область',
    'Троицк': 'Челябинская область',
    'Снежинск': 'Челябинская область',
    'Сатка': 'Челябинская область',

    'Тюмень': 'Тюменская область',
    'Тюменская область': 'Тюменская область',
    'Тобольск': 'Тюменская область',
    'Ишим': 'Тюменская область',
    'Ялуторовск': 'Тюменская область',

    'Ханты-Мансийск': 'Ханты-Мансийский автономный округ - Югра',
    'ХМАО': 'Ханты-Мансийский автономный округ - Югра',
    'Сургут': 'Ханты-Мансийский автономный округ - Югра',
    'Нижневартовск': 'Ханты-Мансийский автономный округ - Югра',
    'Нефтеюганск': 'Ханты-Мансийский автономный округ - Югра',
    'Когалым': 'Ханты-Мансийский автономный округ - Югра',

    'Салехард': 'Ямало-Ненецкий автономный округ',
    'Ноябрьск': 'Ямало-Ненецкий автономный округ',
    'Новый Уренгой': 'Ямало-Ненецкий автономный округ',

    # Сибирский федеральный округ
    'Новосибирск': 'Новосибирская область',
    'Новосибирская область': 'Новосибирская область',
    'Бердск': 'Новосибирская область',
    'Искитим': 'Новосибирская область',

    'Омск': 'Омская область',
    'Омская область': 'Омская область',

    'Красноярск': 'Красноярский край',
    'Красноярский край': 'Красноярский край',
    'Норильск': 'Красноярский край',
    'Ачинск': 'Красноярский край',
    'Канск': 'Красноярский край',
    'Железногорск': 'Красноярский край',

    'Иркутск': 'Иркутская область',
    'Иркутская область': 'Иркутская область',
    'Ангарск': 'Иркутская область',
    'Братск': 'Иркутская область',

    'Кемерово': 'Кемеровская область - Кузбасс',
    'Кемеровская область': 'Кемеровская область - Кузбасс',
    'Новокузнецк': 'Кемеровская область - Кузбасс',
    'Прокопьевск': 'Кемеровская область - Кузбасс',

    'Барнаул': 'Алтайский край',
    'Алтайский край': 'Алтайский край',
    'Бийск': 'Алтайский край',
    'Рубцовск': 'Алтайский край',

    'Томск': 'Томская область',
    'Томская область': 'Томская область',
    'Северск': 'Томская область',

    # Дальневосточный федеральный округ
    'Владивосток': 'Приморский край',
    'Приморский край': 'Приморский край',
    'Находка': 'Приморский край',
    'Уссурийск': 'Приморский край',

    'Хабаровск': 'Хабаровский край',
    'Хабаровский край': 'Хабаровский край',
    'Комсомольск-на-Амуре': 'Хабаровский край',

    'Якутск': 'Республика Саха (Якутия)',
    'Якутия': 'Республика Саха (Якутия)',
    'Нерюнгри': 'Республика Саха (Якутия)',

    'Петропавловск-Камчатский': 'Камчатский край',
    'Камчатка': 'Камчатский край',

    'Южно-Сахалинск': 'Сахалинская область',
    'Сахалин': 'Сахалинская область',

    'Магадан': 'Магаданская область',
    'Магаданская область': 'Магаданская область',

    'Анадырь': 'Чукотский автономный округ',
    'Чукотка': 'Чукотский автономный округ',

    'Биробиджан': 'Еврейская автономная область',

    # Страны ближнего зарубежья
    'Минск': 'Беларусь',
    'Беларусь': 'Беларусь',
    'Гомель': 'Беларусь',
    'Витебск': 'Беларусь',
    'Могилев': 'Беларусь',

    'Киев': 'Украина',
    'Украина': 'Украина',
    'Харьков': 'Украина',
    'Одесса': 'Украина',
    'Днепр': 'Украина',
    'Донецк': 'Украина',
    'Луганск': 'Украина',
    'Запорожье': 'Украина',

    'Алматы': 'Казахстан',
    'Казахстан': 'Казахстан',
    'Астана': 'Казахстан',
    'Шымкент': 'Казахстан',
    'Караганда': 'Казахстан',
    'Актау': 'Казахстан',
    'Атырау': 'Казахстан',

    'Баку': 'Азербайджан',
    'Азербайджан': 'Азербайджан',
    'Гянджа': 'Азербайджан',

    'Тбилиси': 'Грузия',
    'Грузия': 'Грузия',
    'Батуми': 'Грузия',
    'Кутаиси': 'Грузия',

    'Ереван': 'Армения',
    'Армения': 'Армения',

    'Ташкент': 'Узбекистан',
    'Узбекистан': 'Узбекистан',
    'Самарканд': 'Узбекистан',

    'Бишкек': 'Кыргызстан',
    'Кыргызстан': 'Кыргызстан',
    'Ош': 'Кыргызстан',

    'Кишинев': 'Молдова',
    'Молдова': 'Молдова',

    'Ашхабад': 'Туркменистан',
    'Туркменистан': 'Туркменистан',

    'Душанбе': 'Таджикистан',
    'Таджикистан': 'Таджикистан',

    # Учреждения и особые территории
    'д. Богородицкое': 'д. Богородицкое',
    'п. Пригорское': 'п. Пригорское',
    'ЗАТО Солнечный': 'ЗАТО Солнечный',
}



class BatchProcessor:
    def __init__(self, batch_num):
        self.batch_num = batch_num
        self.ch_client = Client(host='my_clickhouse', port=9000, user='default', password='', database='external_data')

        # Пути к файлам
        self.data_path = '/home/jovyan/work/data/processed'
        self.batches_detail_path = f'{self.data_path}/batches_detail.csv'
        self.batch_config_path = f'{self.data_path}/batch_config.json'

        # Загружаем конфигурацию батчей
        self.batches_df = pd.read_csv(self.batches_detail_path)
        with open(self.batch_config_path, 'r') as f:
            self.full_config = json.load(f)

        # Проверяем, что батч существует
        if self.batch_num not in self.batches_df['batch_num'].values:
            raise ValueError(f"Батч {self.batch_num} не найден! Доступны: 1-{len(self.batches_df)}")

        # Получаем информацию о батче
        self.batch_info = self.batches_df[self.batches_df['batch_num'] == self.batch_num].iloc[0]
        self.cluster_id = str(int(self.batch_info['cluster']))
        self.cluster_params = self.full_config['clusters'][self.cluster_id]['params']

        print(f"\n{'='*60}")
        print(f" РАБОТА С БАТЧЕМ №{self.batch_num}")
        print('='*60)
        print(f"   Кластер: {int(self.batch_info['cluster'])} ({self.batch_info['cluster_name'].upper()})")
        print(f"   Товаров в батче: {int(self.batch_info['product_count'])}")
        print(f"\n   Параметры модели:")
        for param, value in self.cluster_params.items():
            print(f"      {param}: {value}")

    def _get_cluster_products(self, cluster_id):
        """Получает все товары для указанного кластера"""
        try:
            query = """
            SELECT 
                `Номенклатура`,
                COUNT(*) as record_count,
                AVG(`Количество`) as avg_quantity,
                stddevSamp(`Количество`) as std_quantity,
                COUNT(DISTINCT `город`) as city_count
            FROM external_data.sales_raw
            GROUP BY `Номенклатура`
            HAVING record_count >= 300
            ORDER BY record_count DESC
            """

            all_products_df = self.ch_client.query_dataframe(query)
            print(f"   Загружено {len(all_products_df)} товаров из ClickHouse")

            batches_df_local = pd.read_csv(self.batches_detail_path)
            cluster_batches = batches_df_local[batches_df_local['cluster'] == float(cluster_id)]

            all_products = []
            for _, batch in cluster_batches.iterrows():
                products_sample = ast.literal_eval(batch['products'])
                all_products.extend(products_sample)

            return list(set(all_products))

        except Exception as e:
            print(f"   Ошибка: {e}, используем данные из CSV")
            batches_df_local = pd.read_csv(self.batches_detail_path)
            cluster_batches = batches_df_local[batches_df_local['cluster'] == float(cluster_id)]

            all_products = []
            for _, batch in cluster_batches.iterrows():
                products_sample = ast.literal_eval(batch['products'])
                all_products.extend(products_sample)

            return list(set(all_products))

    def get_batch_products(self):
        """Получает список товаров для текущего батча"""
        cluster_products = self._get_cluster_products(self.cluster_id)

        cluster_batches = self.batches_df[self.batches_df['cluster'] == float(self.cluster_id)].sort_values('batch_num')

        prev_batches = cluster_batches[cluster_batches['batch_num'] < self.batch_num]
        prev_count = prev_batches['product_count'].sum() if not prev_batches.empty else 0

        start_idx = prev_count
        end_idx = start_idx + int(self.batch_info['product_count'])

        batch_products = cluster_products[start_idx:end_idx]

        print(f"\n Товаров в батче {self.batch_num}: {len(batch_products)}")
        print(f"   Индексы: {start_idx} - {end_idx}")

        return batch_products

    def load_product_data(self, product_name):
        """Загружает данные по одному товару из ClickHouse"""
        product_escaped = product_name.replace("'", "\\'")

        query = f"""
        SELECT 
            `Номенклатура`,
            `Дата` as date,
            `Количество` as quantity,
            `Цена` as price,
            `Сумма` as amount,
            `НДС` as vat,
            `Контрагент` as counterparty,
            `Организация` as organization,
            `город` as city
        FROM external_data.sales_raw
        WHERE `Номенклатура` = '{product_escaped}'
        ORDER BY `Дата`
        """

        try:
            df = self.ch_client.query_dataframe(query)
            return df
        except Exception as e:
            print(f"   Ошибка загрузки {product_name[:50]}: {e}")
            return pd.DataFrame()

    def enrich_dataset(self, df):
        """Обогащает датасет внешними признаками из ClickHouse"""
        print("\n" + "="*60)
        print(" ОБОГАЩЕНИЕ ДАННЫХ")
        print("="*60)
        print(f" Исходный датасет: {df.shape}")

        df_enriched = df.copy()

        #  ИСПРАВЛЕНО: проверяем наличие колонки
        if 'date' not in df_enriched.columns:
            print("   Ошибка: колонка 'date' не найдена!")
            return df_enriched

        # Переименовываем колонки
        rename_dict = {
            'date': 'Дата',
            'quantity': 'Количество',
            'amount': 'Сумма',
            'price': 'Цена',
            'city': 'Город',
            'counterparty': 'Контрагент',
            'organization': 'Организация'
        }
        rename_dict = {k: v for k, v in rename_dict.items() if k in df_enriched.columns}
        df_enriched = df_enriched.rename(columns=rename_dict)

        # Добавляем признаки (ТОЛЬКО ОДИН РАЗ!)
        df_enriched = create_time_features(df_enriched)
        df_enriched = create_lag_features(df_enriched)
        df_enriched = create_org_features(df_enriched)
        df_enriched = create_type_features(df_enriched)

        # Временные признаки для мерджа с внешними данными
        df_enriched['year'] = df_enriched['Дата'].dt.year
        df_enriched['month'] = df_enriched['Дата'].dt.month
        df_enriched['day'] = df_enriched['Дата'].dt.day
        df_enriched['dayofweek'] = df_enriched['Дата'].dt.dayofweek
        df_enriched['hour'] = df_enriched['Дата'].dt.hour
        df_enriched['is_weekend'] = (df_enriched['dayofweek'] >= 5).astype(int)

        # Циклические признаки (если не были добавлены)
        if 'month_sin' not in df_enriched.columns:
            df_enriched['month_sin'] = np.sin(2 * np.pi * df_enriched['month'] / 12)
            df_enriched['month_cos'] = np.cos(2 * np.pi * df_enriched['month'] / 12)
            df_enriched['hour_sin'] = np.sin(2 * np.pi * df_enriched['hour'] / 24)
            df_enriched['hour_cos'] = np.cos(2 * np.pi * df_enriched['hour'] / 24)

        # 1. Инфляция
        print("\n1. ДОБАВЛЯЕМ ИНФЛЯЦИЮ...")
        try:
            inflation = self.ch_client.query_dataframe("""
                SELECT 
                    year,
                    month,
                    inflation_rate as inflation_rate_monthly
                FROM external_data.inflation_monthly
                WHERE year >= 2024 AND year <= 2026
            """)
            df_enriched = df_enriched.merge(inflation, on=['year', 'month'], how='left')
            print(f"   Добавлено {len(inflation)} записей инфляции")
        except Exception as e:
            print(f"   Ошибка: {e}")

        # 2. Демография
        print("\n2. ДОБАВЛЯЕМ ДЕМОГРАФИЮ...")
        try:
            population = self.ch_client.query_dataframe("""
                SELECT 
                    year,
                    SUM(total_population) as total_population
                FROM external_data.demographic_data
                WHERE year >= 2024 AND year <= 2026
                GROUP BY year
            """)
            df_enriched = df_enriched.merge(population, on='year', how='left')
            print(f"   Добавлено {len(population)} записей")
        except Exception as e:
            print(f"   Ошибка: {e}")

        # 3. Погода
        print("\n3. ДОБАВЛЯЕМ ПОГОДУ...")
        cities = df_enriched['Город'].unique().tolist()

        if cities and len(cities) > 0:
            cities_str = "', '".join(cities)
            try:
                weather = self.ch_client.query_dataframe(f"""
                    SELECT 
                        city,
                        toYear(timestamp) as year,
                        toMonth(timestamp) as month,
                        AVG(temperature) as avg_temperature,
                        AVG(humidity) as avg_humidity
                    FROM external_data.weather_hourly
                    WHERE city IN ('{cities_str}')
                    GROUP BY city, year, month
                """)

                # Переименовываем city в Город для мерджа
                weather = weather.rename(columns={'city': 'Город'})
                df_enriched = df_enriched.merge(weather, on=['Город', 'year', 'month'], how='left')
                print(f"   Добавлено {len(weather)} записей погоды")
            except Exception as e:
                print(f"   Ошибка: {e}")

        print(f"\n Обогащение завершено! Размер: {df_enriched.shape}")
        return df_enriched

    def save_batch_data(self, df_raw, df_enriched):
        """Сохраняет данные батча"""
        os.makedirs(self.data_path, exist_ok=True)

        # Сырые данные
        raw_path = f'{self.data_path}/batch{self.batch_num}_raw.parquet'
        df_raw.to_parquet(raw_path)
        print(f"\n Сырые данные сохранены: {raw_path}")

        # Обогащённые данные
        enriched_path = f'{self.data_path}/batch{self.batch_num}_enriched.parquet'
        df_enriched.to_parquet(enriched_path)
        print(f" Обогащённые данные сохранены: {enriched_path}")
        date_col = 'Дата' if 'Дата' in df_raw.columns else 'date'

        # Метаданные
        metadata = {
            'batch_num': self.batch_num,
            'cluster': int(self.batch_info['cluster']),
            'cluster_name': self.batch_info['cluster_name'],
            'product_count': int(df_raw['Номенклатура'].nunique()),
            'expected_count': int(self.batch_info['product_count']),
            'params': self.cluster_params,
            'data_stats': {
                'total_records': len(df_raw),
                'unique_products': int(df_raw['Номенклатура'].nunique()),
                'unique_cities': int(df_raw['city'].nunique()),
                'total_amount': float(df_raw['amount'].sum()),
                'date_min': df_raw['date'].min().isoformat(),
                'date_max': df_raw['date'].max().isoformat()
            },
            'enriched_columns': len(df_enriched.columns),
            'processed_at': datetime.now().isoformat()
        }

        meta_path = f'{self.data_path}/batch{self.batch_num}_metadata.json'
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print(f" Метаданные сохранены: {meta_path}")

    def create_trend_features(self):
        """
        Создает признаки на основе исторических трендов зарплат из ClickHouse
        """
        print("="*60)
        print(" ЗАГРУЗКА ИСТОРИЧЕСКИХ ДАННЫХ О ЗАРПЛАТАХ")
        print("="*60)

        salary_query = """
        SELECT 
            region_name,
            year,
            salary_value
        FROM median_salaries_regional
        WHERE year >= 2013
        ORDER BY region_name, year
        """

        try:
            salary_df = self.ch_client.query_dataframe(salary_query)
            print(f"   Загружено {len(salary_df)} записей")
            print(f"   Регионов: {salary_df['region_name'].nunique()}")
            print(f"   Годы: {salary_df['year'].min()}-{salary_df['year'].max()}")

            trend_features = []

            for region in salary_df['region_name'].unique():
                region_data = salary_df[salary_df['region_name'] == region].sort_values('year')

                if len(region_data) >= 3:
                    years = region_data['year'].values
                    salaries = region_data['salary_value'].values

                    # Линейный тренд
                    x = np.arange(len(years))
                    coeffs = np.polyfit(x, salaries, 1)
                    slope = coeffs[0]

                    # Рост за последние 3 года
                    if len(region_data) >= 3:
                        last_3 = region_data.tail(3)
                        growth_3y = (last_3['salary_value'].iloc[-1] / last_3['salary_value'].iloc[0] - 1) * 100
                    else:
                        growth_3y = 0

                    # Рост за весь период
                    total_growth = (salaries[-1] / salaries[0] - 1) * 100 if salaries[0] > 0 else 0

                    # Средний годовой рост
                    pct_changes = region_data['salary_value'].pct_change() * 100
                    avg_annual_growth = pct_changes.mean() if len(pct_changes) > 1 else 0

                    # Волатильность
                    volatility = salaries.std()
                    cv = volatility / salaries.mean() if salaries.mean() > 0 else 0

                    trend_features.append({
                        'region_name': region,
                        'salary_trend_slope': slope,
                        'salary_avg_annual_growth': avg_annual_growth,
                        'salary_growth_3y': growth_3y,
                        'salary_total_growth': total_growth,
                        'salary_volatility': volatility,
                        'salary_cv': cv,
                        'salary_last_known': salaries[-1],
                        'salary_last_year': years[-1],
                        'salary_min': salaries.min(),
                        'salary_max': salaries.max(),
                        'salary_avg': salaries.mean()
                    })

            trend_df = pd.DataFrame(trend_features)
            print(f"\n Рассчитаны тренды для {len(trend_df)} регионов")
            return trend_df

        except Exception as e:
            print(f" Ошибка при загрузке: {e}")
            return pd.DataFrame()

    def add_trend_features(self, df, trend_df):
        """
        Добавляет трендовые признаки в датасет
        """
        df_result = df.copy()

        print("\n" + "="*60)
        print(" ДОБАВЛЕНИЕ ТРЕНДОВЫХ ПРИЗНАКОВ")
        print("="*60)

        # Определяем название колонки с городом
        city_col = 'city' if 'city' in df_result.columns else 'Город'

        # Добавляем регион
        df_result['region'] = df_result[city_col].map(city_to_region)

        # Сопоставление
        matched = df_result['region'].notna().sum()
        total = len(df_result)
        print(f"\n Сопоставлено городов: {matched}/{total} ({matched/total*100:.1f}%)")

        # Для несопоставленных городов используем название города
        df_result.loc[df_result['region'].isna(), 'region'] = df_result.loc[df_result['region'].isna(), city_col]

        # Добавляем тренды
        df_result = df_result.merge(
            trend_df,
            left_on='region',
            right_on='region_name',
            how='left'
        )

        # Заполняем пропуски
        trend_cols = ['salary_trend_slope', 'salary_avg_annual_growth',
                      'salary_growth_3y', 'salary_last_known', 'salary_total_growth',
                      'salary_volatility', 'salary_cv']

        for col in trend_cols:
            if col in df_result.columns:
                filled = df_result[col].notna().sum()
                if filled < len(df_result):
                    mean_val = df_result[col].mean()
                    df_result[col] = df_result[col].fillna(mean_val)

        # Удаляем лишние колонки
        if 'region_name' in df_result.columns:
            df_result = df_result.drop('region_name', axis=1)

        print(f"\n Трендовые признаки добавлены")
        return df_result


    def add_google_trends(self, df):
        """
        Добавляет Google Trends к датасету
        """
        print("\n" + "="*60)
        print(" ДОБАВЛЕНИЕ GOOGLE TRENDS")
        print("="*60)
    
        # 1. ЗАГРУЗКА ТРЕНДОВ
        print("\n1. ЗАГРУЗКА ТРЕНДОВ...")

        trends_df = self.ch_client.query_dataframe("""
            SELECT 
                date,
                product_name,
                trend_value
            FROM google_trends_monthly
        """)

        print(f"   Загружено {len(trends_df)} записей")
        print(f"   Продукты: {trends_df['product_name'].unique().tolist()}")
        trends_df['date'] = pd.to_datetime(trends_df['date'])

        # 2. ЗАГРУЗКА МАППИНГА
        print("\n2. ЗАГРУЗКА МАППИНГА КАТЕГОРИЙ...")

        mapping_df = self.ch_client.query_dataframe("""
            SELECT 
                product_name,
                trend_name
            FROM product_category_mapping
            WHERE trend_name IS NOT NULL AND trend_name != ''
        """)

        print(f"   Загружено {len(mapping_df)} записей маппинга")

        # 3. ПОДГОТОВКА ДАТАСЕТА
        print("\n3. ПОДГОТОВКА ДАТАСЕТА...")

        # Удаляем старые трендовые колонки
        old_trends = [col for col in df.columns if col.startswith('trend_')]
        if old_trends:
            df = df.drop(columns=old_trends)
            print(f"   Удалено старых трендов: {len(old_trends)}")

        # Добавляем trend_name к товарам
        trend_dict = dict(zip(mapping_df['product_name'], mapping_df['trend_name']))
        df['trend_name'] = df['Номенклатура'].map(trend_dict)

        # Для несопоставленных товаров определяем категорию по названию
        missing_mask = df['trend_name'].isna()
        if missing_mask.any():
            print(f"   Для {missing_mask.sum()} товаров определим категорию автоматически...")

            def guess_category(name):
                name_lower = name.lower()
                if 'творог' in name_lower or 'твор' in name_lower:
                    return 'Кварк'
                elif 'йогурт' in name_lower:
                    return 'йогурт'
                elif 'смет' in name_lower:
                    return 'Сметана'
                elif 'сыр' in name_lower:
                    return 'Сыр'
                elif 'масло' in name_lower:
                    return 'Сливочное масло'
                elif 'кефир' in name_lower:
                    return 'кефир'
                elif 'молоко' in name_lower:
                    return 'Молоко'
                elif 'спред' in name_lower or 'марг' in name_lower:
                    return 'Намазка'
                else:
                    return None

            df['trend_name'] = df['trend_name'].fillna(df['Номенклатура'].apply(guess_category))

        print(f"\n   Распределение по trend_name:")
        print(df['trend_name'].value_counts())

        # 4. ПРИСОЕДИНЕНИЕ ТРЕНДОВ
        print("\n4. ПРИСОЕДИНЕНИЕ ТРЕНДОВ...")

        # ИСПРАВЛЕНИЕ: используем колонку 'Дата' вместо 'date'
        df['date_join'] = pd.to_datetime(df['Дата']).dt.date  # <--- ИСПРАВЛЕНО
        trends_df['date_join'] = trends_df['date'].dt.date

        # Создаем отдельные колонки для каждого тренда
        for product in trends_df['product_name'].unique():
            product_trends = trends_df[trends_df['product_name'] == product][['date_join', 'trend_value']]
            product_trends = product_trends.rename(columns={'trend_value': f'trend_{product}'})

            df = df.merge(
                product_trends,
                on='date_join',
                how='left'
            )

        # Удаляем временную колонку
        df = df.drop('date_join', axis=1)

        # 5. ПРОВЕРКА ЗАПОЛНЕНИЯ
        print(f"\n5. ПРОВЕРКА ЗАПОЛНЕНИЯ:")

        trend_columns = [col for col in df.columns if col.startswith('trend_') and col != 'trend_name']
        for col in trend_columns:
            filled = df[col].notna().sum()
            pct = filled / len(df) * 100
            print(f"   {col}: {filled}/{len(df)} ({pct:.1f}%)")

            # Заполняем пропуски средними
            if filled < len(df):
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)

        # 6. ПРИМЕР ДАННЫХ
        print(f"\n6. ПРИМЕР ДАННЫХ:")
        sample = df[['Дата', 'Номенклатура', 'trend_name'] + trend_columns[:3]].head(5)  # <--- ИСПРАВЛЕНО
        for _, row in sample.iterrows():
            print(f"\n   {row['Дата'].date()}: {row['Номенклатура'][:40]}...")
            for col in trend_columns[:3]:
                print(f"      {col}: {row[col]:.1f}")

        print(f"\n Google Trends добавлены! Новый размер: {df.shape}")
        return df

    def run(self):
        """Основной метод обработки батча"""
        print(f"\n НАЧАЛО ОБРАБОТКИ БАТЧА {self.batch_num}")

        # 1. Получаем товары батча
        products = self.get_batch_products()
        if not products:
            print(" Нет товаров для обработки")
            return None

        # 2. Загружаем данные по каждому товару
        all_dfs = []
        for i, product in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] {product[:70]}...")
            df = self.load_product_data(product)
            if not df.empty:
                all_dfs.append(df)
                print(f"    {len(df)} записей, {df['city'].nunique()} городов")
            else:
                print(f"    Нет данных")

        if not all_dfs:
            print(" Нет данных ни по одному товару")
            return None

        # 3. Объединяем
        df_raw = pd.concat(all_dfs, ignore_index=True)
        print(f"\n ИТОГО: {len(df_raw)} записей, {df_raw['Номенклатура'].nunique()} товаров")

        # 4. Обогащаем (погода, инфляция, демография)
        df_enriched = self.enrich_dataset(df_raw)

        # 5. Добавляем трендовые признаки (зарплаты)
        trend_features = self.create_trend_features()
        if not trend_features.empty:
            df_enriched = self.add_trend_features(df_enriched, trend_features)

        # 6.  НОВОЕ: Добавляем Google Trends
        df_enriched = self.add_google_trends(df_enriched)

        # 7. Сохраняем
        self.save_batch_data(df_raw, df_enriched)

        print(f"\n БАТЧ {self.batch_num} УСПЕШНО ОБРАБОТАН")
        return df_enriched