#!/usr/bin/env python3
"""
Script to populate slugs for all existing records in the database.
Run this once after adding slug support to ensure all existing records have slugs.
"""

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import Ingredient, Recipe, Batch, Dish, User, InventoryItem, Task
from app.utils.slugify import generate_unique_slug


def populate_slugs():
    """Populate slugs for all models that need them."""
    db = SessionLocal()

    try:
        print("Starting slug population...")

        # Populate Ingredient slugs
        print("\n📦 Populating Ingredient slugs...")
        ingredients = db.query(Ingredient).filter(Ingredient.slug == None).all()
        for ingredient in ingredients:
            ingredient.slug = generate_unique_slug(db, Ingredient, ingredient.name, exclude_id=ingredient.id)
        db.commit()
        print(f"✅ Populated {len(ingredients)} ingredient slugs")

        # Populate Recipe slugs
        print("\n📝 Populating Recipe slugs...")
        recipes = db.query(Recipe).filter(Recipe.slug == None).all()
        for recipe in recipes:
            recipe.slug = generate_unique_slug(db, Recipe, recipe.name, exclude_id=recipe.id)
        db.commit()
        print(f"✅ Populated {len(recipes)} recipe slugs")

        # Populate Batch slugs
        print("\n🍳 Populating Batch slugs...")
        batches = db.query(Batch).filter(Batch.slug == None).all()
        for batch in batches:
            if batch.recipe:
                batch.slug = generate_unique_slug(db, Batch, batch.recipe.name, exclude_id=batch.id)
            else:
                batch.slug = generate_unique_slug(db, Batch, f"batch-{batch.id}", exclude_id=batch.id)
        db.commit()
        print(f"✅ Populated {len(batches)} batch slugs")

        # Populate Dish slugs
        print("\n🍽️  Populating Dish slugs...")
        dishes = db.query(Dish).filter(Dish.slug == None).all()
        for dish in dishes:
            dish.slug = generate_unique_slug(db, Dish, dish.name, exclude_id=dish.id)
        db.commit()
        print(f"✅ Populated {len(dishes)} dish slugs")

        # Populate User slugs
        print("\n👤 Populating User slugs...")
        users = db.query(User).filter(User.slug == None).all()
        for user in users:
            user.slug = generate_unique_slug(db, User, user.username, exclude_id=user.id)
        db.commit()
        print(f"✅ Populated {len(users)} user slugs")

        # Populate InventoryItem slugs
        print("\n📋 Populating InventoryItem slugs...")
        items = db.query(InventoryItem).filter(InventoryItem.slug == None).all()
        for item in items:
            item.slug = generate_unique_slug(db, InventoryItem, item.name, exclude_id=item.id)
        db.commit()
        print(f"✅ Populated {len(items)} inventory item slugs")

        # Note: Tasks don't need population since they use a computed property

        print("\n✅ All slugs populated successfully!")

    except Exception as e:
        print(f"\n❌ Error populating slugs: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_slugs()
