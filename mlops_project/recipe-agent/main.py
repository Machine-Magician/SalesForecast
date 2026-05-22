#!/usr/bin/env python3
"""Entry point for Recipe Agent CLI."""

import os
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from recipe_agent.database import RecipeDB
from recipe_agent.tools import set_db
from recipe_agent.agent import run_cli

def init_db():
    """Initialize database and set up demo data."""
    db = RecipeDB(db_path="data/recipes.db")
    set_db(db)

    # Создаем коллекцию Italian Cuisine если нет
    if not db.collection_exists("Italian Cuisine"):
        italian_id = db.create_collection("Italian Cuisine", "Classic Italian recipes")
        print(f" Создана коллекция Italian Cuisine (ID: {italian_id})")
    else:
        italian = db.get_collection_by_name("Italian Cuisine")
        italian_id = italian['id']

    # Добавляем рецепты если нет
    if not db.recipe_exists(italian_id, "Carbonara"):
        recipe_id = db.create_recipe(italian_id, "Carbonara", 2, 30, "Classic Roman pasta dish")
        db.add_ingredient(recipe_id, "spaghetti", 400, "g")
        db.add_ingredient(recipe_id, "guanciale", 200, "g")
        db.add_ingredient(recipe_id, "eggs", 4, "pcs")
        db.add_ingredient(recipe_id, "pecorino cheese", 100, "g")
        db.add_ingredient(recipe_id, "black pepper", 5, "g")
        for i, step in enumerate([
            "Bring a large pot of salted water to boil",
            "Cook spaghetti according to package instructions",
            "Fry guanciale until golden and crispy",
            "Mix eggs with pecorino cheese and pepper",
            "Combine pasta with guanciale, then add egg mixture",
            "Stir well, serve immediately"
        ], 1):
            db.add_step(recipe_id, i, step)

    if not db.recipe_exists(italian_id, "Margherita Pizza"):
        recipe_id = db.create_recipe(italian_id, "Margherita Pizza", 1, 20, "Classic Neapolitan pizza")
        db.add_ingredient(recipe_id, "pizza dough", 250, "g")
        db.add_ingredient(recipe_id, "tomato sauce", 100, "g")
        db.add_ingredient(recipe_id, "mozzarella di bufala", 125, "g")
        db.add_ingredient(recipe_id, "fresh basil leaves", 8, "pcs")
        db.add_ingredient(recipe_id, "extra virgin olive oil", 15, "ml")
        db.add_ingredient(recipe_id, "salt", 5, "g")
        for i, step in enumerate([
            "Preheat oven to 250°C (480°F)",
            "Roll out pizza dough to 30cm diameter",
            "Spread tomato sauce evenly over dough",
            "Tear mozzarella and distribute over sauce",
            "Season with salt and drizzle with olive oil",
            "Bake for 10-12 minutes until golden",
            "Add fresh basil leaves",
            "Drizzle with olive oil and serve"
        ], 1):
            db.add_step(recipe_id, i, step)

    if not db.recipe_exists(italian_id, "Tiramisu"):
        recipe_id = db.create_recipe(italian_id, "Tiramisu", 6, 45, "Classic Italian dessert")
        db.add_ingredient(recipe_id, "ladyfingers (savoiardi)", 300, "g")
        db.add_ingredient(recipe_id, "mascarpone cheese", 500, "g")
        db.add_ingredient(recipe_id, "eggs", 4, "pcs")
        db.add_ingredient(recipe_id, "sugar", 100, "g")
        db.add_ingredient(recipe_id, "espresso coffee", 300, "ml")
        db.add_ingredient(recipe_id, "unsweetened cocoa powder", 30, "g")
        for i, step in enumerate([
            "Brew espresso and let it cool",
            "Separate egg yolks from whites",
            "Whisk egg yolks with sugar until pale",
            "Add mascarpone and mix until smooth",
            "Beat egg whites with salt until stiff",
            "Fold egg whites into mascarpone mixture",
            "Dip ladyfingers in coffee",
            "Layer ladyfingers and cream",
            "Dust with cocoa powder",
            "Refrigerate for 4 hours"
        ], 1):
            db.add_step(recipe_id, i, step)

    print(" База данных инициализирована с демо-рецептами")

if __name__ == "__main__":
    init_db()
    run_cli()