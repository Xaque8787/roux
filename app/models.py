from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, date
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    hourly_wage = Column(Float, default=15.0)
    is_admin = Column(Boolean, default=False)
    is_user = Column(Boolean, default=True)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    type = Column(String)  # 'ingredient', 'recipe', 'batch', 'dish', 'inventory'

class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    unit = Column(String)
    unit_cost = Column(Float)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")
    instructions = Column(Text)

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    quantity = Column(Float)
    ingredient = relationship("Ingredient")

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    yield_amount = Column(Float)
    labor_minutes = Column(Integer)
    can_be_broken_down = Column(Boolean, default=False)
    breakdown_sizes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    recipe = relationship("Recipe")

class Dish(Base):
    __tablename__ = "dishes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")
    sale_price = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

class DishBatchPortion(Base):
    __tablename__ = "dish_batch_portions"
    id = Column(Integer, primary_key=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"))
    portion_size = Column(Float)
    batch = relationship("Batch")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")
    par_level = Column(Float, default=0.0)

class InventoryDay(Base):
    __tablename__ = "inventory_days"
    id = Column(Integer, primary_key=True)
    date = Column(Date, default=date.today)
    finalized = Column(Boolean, default=False)
    employees_working = Column(String)

class InventoryDayItem(Base):
    __tablename__ = "inventory_day_items"
    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float, default=0)
    inventory_item = relationship("InventoryItem")
    day = relationship("InventoryDay")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    assigned_to_id = Column(Integer, ForeignKey("users.id"))
    description = Column(String)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    assigned_to = relationship("User")
    day = relationship("InventoryDay")

class UtilityCost(Base):
    __tablename__ = "utility_costs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    monthly_cost = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)