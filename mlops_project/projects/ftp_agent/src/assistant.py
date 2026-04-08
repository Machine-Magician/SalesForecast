#!/usr/bin/env python3
"""AI-помощник для поиска по FTP-файлам"""

from clickhouse_driver import Client
from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
import sys

# Настройка кодировки для ввода
sys.stdin.reconfigure(encoding='utf-8')

load_dotenv()

client = Client(host='my_clickhouse', port=9000, user='default', password='')
model = SentenceTransformer('all-MiniLM-L6-v2')

llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    temperature=0
)

def search_similar(query, top_k=10):
    """Поиск похожих файлов"""
    query_embedding = model.encode(query).tolist()

    result = client.execute(f"""
        SELECT file_name, region, folder_date, content,
               cosineDistance(embedding, {query_embedding}) as distance
        FROM procedures_metadata.file_embeddings
        ORDER BY distance
        LIMIT {top_k}
    """)
    return result

def ask_question(question):
    similar = search_similar(question)

    if not similar:
        return "Не найдено relevant файлов"

    print(f"\n Найдено {len(similar)} файлов:")
    for r in similar:
        print(f"   - {r[0]} ({r[1]}/{r[2]})")

    context = "\n\n".join([
        f"Файл: {r[0]} (регион: {r[1]}, дата: {r[2]})\n{r[3][:800]}"
        for r in similar[:5]  # в контекст только топ-5
    ])

    prompt = f"""
    Ты — помощник по данным из FTP-файлов компании.
    Отвечай кратко и по делу на русском языке.
    
    ВОПРОС: {question}
    
    ФАЙЛЫ (для контекста):
    {context}
    
    ОТВЕТ:"""

    response = llm.invoke(prompt)
    return response.content

if __name__ == "__main__":
    print(" FTP-помощник запущен")
    while True:
        try:
            q = input("\n Ваш вопрос: ")
            if q.lower() in ['exit', 'quit', 'выход']:
                break
            print(f"\n Ответ: {ask_question(q)}")
        except UnicodeDecodeError:
            print(" Ошибка кодировки, попробуйте ещё раз")