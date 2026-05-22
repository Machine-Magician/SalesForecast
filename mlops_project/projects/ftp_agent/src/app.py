#!/usr/bin/env python3
"""Gradio интерфейс для AI-помощника по FTP-файлам"""

import sys
sys.path.append('/home/jovyan/work/projects/ftp_agent/src')

from assistant import ask_question
import gradio as gr

def chat_with_agent(message, history):
    """Обработка сообщения от пользователя"""
    if not message:
        return ""
    response = ask_question(message)
    return response

# Создаём интерфейс
with gr.Blocks(title="FTP AI Assistant", theme="soft") as demo:
    gr.Markdown("#  AI-помощник по FTP-файлам")
    gr.Markdown("""
    Задайте вопрос о данных из FTP-файлов. Например:
    - Какие цены на ...?
    - Покажи счета-фактуры за март
    - Есть ли ошибки в файлах от контрагента?
    - Какие товары были в прайс-листах?
    """)

    with gr.Row():
        with gr.Column(scale=4):
            chatbot = gr.Chatbot(height=500, label="Диалог")
        with gr.Column(scale=1):
            gr.Markdown("### Информация")
            gr.Markdown("Агент ищет ответы в 2570 файлах из 40+ регионов.")
            gr.Markdown("Данные обновляются каждый час.")

    with gr.Row():
        msg = gr.Textbox(
            label="Ваш вопрос",
            placeholder="Напишите вопрос здесь...",
            scale=4
        )
        send_btn = gr.Button("Отправить", variant="primary", scale=1)

    clear = gr.Button("Очистить диалог")

    def respond(message, chat_history):
        bot_message = chat_with_agent(message, chat_history)
        chat_history.append((message, bot_message))
        return "", chat_history

    msg.submit(respond, [msg, chatbot], [msg, chatbot])
    send_btn.click(respond, [msg, chatbot], [msg, chatbot])
    clear.click(lambda: None, None, chatbot, queue=False)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)