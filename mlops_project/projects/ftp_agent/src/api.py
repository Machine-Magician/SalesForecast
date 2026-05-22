#!/usr/bin/env python3
"""FastAPI сервер для AI-помощника"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from assistant import ask_question
import os

app = FastAPI(title="FTP AI Assistant")

# Читаем HTML файл
html_file = "/app/templates/index.html"
with open(html_file, 'r', encoding='utf-8') as f:
    HTML_CONTENT = f.read()

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=HTML_CONTENT, status_code=200)

class Question(BaseModel):
    text: str

@app.post("/ask")
async def ask(question: Question):
    answer = ask_question(question.text)
    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
