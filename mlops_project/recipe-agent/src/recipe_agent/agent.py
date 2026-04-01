import os
from typing import TypedDict, Optional, List, Annotated
import operator
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

from .state import AgentState
from .tools import tools, set_db, get_db
from .database import RecipeDB

load_dotenv()

def call_llm(state: AgentState) -> AgentState:
    """Вызывает LLM с инструментами."""
    llm = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        temperature=0
    )

    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(state["messages"])

    return {"messages": [response]}

def create_agent():
    """Создает и компилирует граф агента."""
    # Создаем узел для инструментов с помощью ToolNode
    tool_node = ToolNode(tools)

    # Строим граф
    workflow = StateGraph(AgentState)

    # Добавляем узлы
    workflow.add_node("agent", call_llm)
    workflow.add_node("tools", tool_node)

    # Добавляем ребра
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        lambda state: "tools" if state["messages"][-1].tool_calls else "end",
        {"tools": "tools", "end": END}
    )
    workflow.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

def run_cli():
    """Запуск CLI для общения с агентом."""
    import uuid
    print("\n Recipe Agent готов к работе!")
    print("Команды: /exit для выхода\n")

    # Используем новый уникальный thread_id
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    app = create_agent()

    print(f"Сессия: {thread_id[:8]}...\n")

    while True:
        try:
            user_input = input(" Вы: ")
        except (KeyboardInterrupt, EOFError):
            print("\n До свидания!")
            break

        if user_input.lower() in ["/exit", "exit", "quit"]:
            print(" До свидания!")
            break

        # Очищаем пользовательский ввод от плохих символов
        user_input = user_input.encode('utf-8', errors='ignore').decode('utf-8')

        try:
            for event in app.stream(
                    {"messages": [("user", user_input)]},
                    config=config,
                    stream_mode="values"
            ):
                if "messages" in event:
                    last_message = event["messages"][-1]
                    if hasattr(last_message, "content") and last_message.content:
                        # Очищаем вывод от плохих символов
                        clean_content = last_message.content.encode('utf-8', errors='ignore').decode('utf-8')
                        print(f" Агент: {clean_content}")
        except Exception as e:
            print(f" Ошибка: {e}")
            # Создаём новую сессию при ошибке
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            print(f" Новая сессия: {thread_id[:8]}...")

if __name__ == "__main__":
    run_cli()