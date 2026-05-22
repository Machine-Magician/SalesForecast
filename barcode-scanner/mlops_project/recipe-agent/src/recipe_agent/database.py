import sqlite3
import os
from pathlib import Path

class RecipeDB:
    def __init__(self, db_path="../data/recipes.db"):
        """Initialize database connection."""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_tables()

    def _init_tables(self):
        """Create all tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    servings INTEGER,
                    prep_time INTEGER,
                    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    amount REAL,
                    unit TEXT,
                    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    step_order INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
                )
            """)

    # Collection methods
    def collection_exists(self, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM collections WHERE name = ?", (name,))
            return cursor.fetchone() is not None

    def create_collection(self, name: str, description: str = "") -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO collections (name, description) VALUES (?, ?)",
                (name, description)
            )
            conn.commit()
            return cursor.lastrowid

    def get_collection_by_name(self, name: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM collections WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_collection(self, collection_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_collections(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM collections ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    # Recipe methods
    def recipe_exists(self, collection_id: int, name: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM recipes WHERE collection_id = ? AND name = ?",
                (collection_id, name)
            )
            return cursor.fetchone() is not None

    def create_recipe(self, collection_id: int, name: str, servings: int = None,
                      prep_time: int = None, description: str = "") -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO recipes 
                   (collection_id, name, description, servings, prep_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (collection_id, name, description, servings, prep_time)
            )
            conn.commit()
            return cursor.lastrowid

    def get_recipe(self, recipe_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recipe_by_name(self, collection_id: int, name: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM recipes WHERE collection_id = ? AND name = ?",
                (collection_id, name)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_recipes(self, collection_id: int) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM recipes WHERE collection_id = ? ORDER BY name",
                (collection_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # Ingredient methods
    def add_ingredient(self, recipe_id: int, name: str, amount: float = None, unit: str = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO ingredients (recipe_id, name, amount, unit) VALUES (?, ?, ?, ?)",
                (recipe_id, name, amount, unit)
            )
            conn.commit()
            return cursor.lastrowid

    def get_ingredients(self, recipe_id: int) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM ingredients WHERE recipe_id = ?",
                (recipe_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # Step methods
    def add_step(self, recipe_id: int, step_order: int, description: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO steps (recipe_id, step_order, description) VALUES (?, ?, ?)",
                (recipe_id, step_order, description)
            )
            conn.commit()
            return cursor.lastrowid

    def get_steps(self, recipe_id: int) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM steps WHERE recipe_id = ? ORDER BY step_order",
                (recipe_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_step(self, recipe_id: int, step_order: int, new_description: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE steps SET description = ? WHERE recipe_id = ? AND step_order = ?",
                (new_description, recipe_id, step_order)
            )
            conn.commit()
            return cursor.rowcount > 0

    # Full recipe
    def get_full_recipe(self, recipe_id: int) -> dict:
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            return None
        recipe['ingredients'] = self.get_ingredients(recipe_id)
        recipe['steps'] = self.get_steps(recipe_id)
        return recipe