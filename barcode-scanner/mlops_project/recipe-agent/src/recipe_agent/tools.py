from langchain_core.tools import tool

# Глобальные переменные
_db_instance = None
_active_collection_id = None
_active_recipe_id = None

def set_db(db):
    """Установить экземпляр базы данных."""
    global _db_instance
    _db_instance = db

def get_db():
    """Получить экземпляр базы данных."""
    global _db_instance
    if _db_instance is None:
        raise RuntimeError("Database not initialized. Call set_db() first.")
    return _db_instance


# ИНСТРУМЕНТЫ (РАБОЧАЯ ВЕРСИЯ)


@tool
def create_collection(name: str, description: str = "") -> str:
    """Создать новую коллекцию рецептов."""
    db = get_db()

    if db.collection_exists(name):
        return f" Коллекция '{name}' уже существует"

    collection_id = db.create_collection(name, description)
    return f"COLLECTION_CREATED:{collection_id}|{name}"


@tool
def list_collections() -> str:
    """Показать все коллекции."""
    db = get_db()
    collections = db.list_collections()

    if not collections:
        return " Нет коллекций"

    result = " Коллекции:\n"
    for col in collections:
        result += f"    {col['name']}\n"
    return result


@tool
def set_active_collection(name: str) -> str:
    """Выбрать активную коллекцию по названию."""
    global _active_collection_id
    db = get_db()
    collection = db.get_collection_by_name(name)
    if not collection:
        return f" Коллекция '{name}' не найдена"
    _active_collection_id = collection['id']
    return f"ACTIVE_COLLECTION:{collection['id']}|{name}"


@tool
def list_recipes() -> str:
    """Показать рецепты в активной коллекции."""
    global _active_collection_id
    db = get_db()

    if _active_collection_id is None:
        return " Нет активной коллекции. Сначала выберите коллекцию."

    recipes = db.list_recipes(_active_collection_id)
    collection = db.get_collection(_active_collection_id)

    if not recipes:
        return f" Нет рецептов в коллекции '{collection['name']}'"

    result = f" Рецепты в '{collection['name']}':\n"
    for i, r in enumerate(recipes, 1):
        result += f"   {i}. {r['name']}\n"
    return result


@tool
def create_recipe(name: str, servings: int, prep_time: int, description: str = "") -> str:
    """Создать новый рецепт в активной коллекции."""
    global _active_collection_id, _active_recipe_id
    db = get_db()

    if _active_collection_id is None:
        return " Нет активной коллекции"

    if db.recipe_exists(_active_collection_id, name):
        return f" Рецепт '{name}' уже существует"

    recipe_id = db.create_recipe(_active_collection_id, name, servings, prep_time, description)
    _active_recipe_id = recipe_id
    return f" Рецепт '{name}' создан"


@tool
def set_active_recipe(name: str) -> str:
    """Выбрать активный рецепт по названию."""
    global _active_collection_id, _active_recipe_id
    db = get_db()

    if _active_collection_id is None:
        return " Нет активной коллекции"

    recipe = db.get_recipe_by_name(_active_collection_id, name)
    if not recipe:
        return f" Рецепт '{name}' не найден"

    _active_recipe_id = recipe['id']
    return f" Активный рецепт: '{name}'"


@tool
def view_recipe() -> str:
    """Показать полный рецепт."""
    global _active_recipe_id
    db = get_db()

    if _active_recipe_id is None:
        return " Нет активного рецепта"

    full = db.get_full_recipe(_active_recipe_id)
    result = f"\n {full['name'].upper()}\n"
    result += f"   Порций: {full['servings']} | Время: {full['prep_time']} мин\n"
    result += "\n Ингредиенты:\n"
    for ing in full['ingredients']:
        amount = f"{ing['amount']} {ing['unit']}" if ing['amount'] else ""
        result += f"    {ing['name']}: {amount}\n"
    result += "\n Приготовление:\n"
    for step in full['steps']:
        result += f"   {step['step_order']}. {step['description']}\n"
    return result


@tool
def add_ingredient(name: str, amount: float, unit: str) -> str:
    """Добавить ингредиент в активный рецепт."""
    global _active_recipe_id
    db = get_db()

    if _active_recipe_id is None:
        return " Нет активного рецепта"

    db.add_ingredient(_active_recipe_id, name, amount, unit)
    return f" Ингредиент '{name} ({amount} {unit})' добавлен"


@tool
def add_step(description: str) -> str:
    """Добавить шаг в активный рецепт."""
    global _active_recipe_id
    db = get_db()

    if _active_recipe_id is None:
        return " Нет активного рецепта"

    steps = db.get_steps(_active_recipe_id)
    step_order = len(steps) + 1
    db.add_step(_active_recipe_id, step_order, description)
    return f" Шаг {step_order} добавлен"


@tool
def edit_step(step_number: int, new_description: str) -> str:
    """Редактировать шаг."""
    global _active_recipe_id
    db = get_db()

    if _active_recipe_id is None:
        return " Нет активного рецепта"

    db.update_step(_active_recipe_id, step_number, new_description)
    return f" Шаг {step_number} обновлен"



# СПИСОК ИНСТРУМЕНТОВ

tools = [
    create_collection,
    list_collections,
    set_active_collection,
    list_recipes,
    create_recipe,
    set_active_recipe,
    view_recipe,
    add_ingredient,
    add_step,
    edit_step
]