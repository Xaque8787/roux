from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, date
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    hourly_wage = Column(Float, default=15.0)
    work_schedule = Column(String)  # JSON string of days: "mon,tue,wed,thu,fri"
    role = Column(String, default="user")  # admin, manager, user
    is_admin = Column(Boolean, default=False)
    is_user = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    contact_info = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    type = Column(String)  # 'ingredient', 'recipe', 'batch', 'dish', 'inventory'

class UsageUnit(Base):
    __tablename__ = "usage_units"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # lb, oz, tbsp, cup, can, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    
    # Purchase Level
    purchase_type = Column(String)  # 'case' or 'single'
    purchase_unit_name = Column(String)  # Case, Bag, Sack, Box
    purchase_quantity_description = Column(String)  # "36 × 1 lb blocks"
    purchase_total_cost = Column(Float)
    breakable_case = Column(Boolean, default=False)
    
    # Item Level (for cases)
    items_per_case = Column(Integer)
    item_unit_name = Column(String)  # "1 lb block", "#10 can"
    
    category = relationship("Category")
    vendor = relationship("Vendor")
    usage_units = relationship("IngredientUsageUnit", back_populates="ingredient")
    
    @property
    def item_cost(self):
        if self.purchase_type == 'case' and self.items_per_case:
            return self.purchase_total_cost / self.items_per_case
        return self.purchase_total_cost

class IngredientUsageUnit(Base):
    __tablename__ = "ingredient_usage_units"
    id = Column(Integer, primary_key=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    usage_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    conversion_factor = Column(Float)  # how many usage units per item/case
    
    ingredient = relationship("Ingredient", back_populates="usage_units")
    usage_unit = relationship("UsageUnit")

    @property
    def price_per_usage_unit(self):
        if self.ingredient.purchase_type == 'case' and self.ingredient.items_per_case:
            item_cost = self.ingredient.purchase_total_cost / self.ingredient.items_per_case
        else:
            item_cost = self.ingredient.purchase_total_cost
        return item_cost / self.conversion_factor if self.conversion_factor else 0

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")
    instructions = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    usage_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    quantity = Column(Float)
    
    ingredient = relationship("Ingredient")
    usage_unit = relationship("UsageUnit")
    
    @property
    def cost(self):
        """Calculate the cost of this recipe ingredient"""
        # Find the ingredient usage unit for this combination
        ingredient_usage = None
        for iu in self.ingredient.usage_units:
            if iu.usage_unit_id == self.usage_unit_id:
                ingredient_usage = iu
                break
        
        if ingredient_usage:
            return self.quantity * ingredient_usage.price_per_usage_unit
        return 0

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    yield_amount = Column(Float)
    yield_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    labor_minutes = Column(Integer)
    can_be_scaled = Column(Boolean, default=False)
    scale_double = Column(Boolean, default=False)
    scale_half = Column(Boolean, default=False)
    scale_quarter = Column(Boolean, default=False)
    scale_eighth = Column(Boolean, default=False)
    scale_sixteenth = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    recipe = relationship("Recipe")
    yield_unit = relationship("UsageUnit")

class Dish(Base):
    __tablename__ = "dishes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")
    sale_price = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class DishBatchPortion(Base):
    __tablename__ = "dish_batch_portions"
    id = Column(Integer, primary_key=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"))
    portion_size = Column(Float)
    portion_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    
    batch = relationship("Batch")
    portion_unit = relationship("UsageUnit")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")
    par_level = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class InventoryDay(Base):
    __tablename__ = "inventory_days"
    id = Column(Integer, primary_key=True)
    date = Column(Date, default=date.today)
    finalized = Column(Boolean, default=False)
    employees_working = Column(String)
    notes = Column(Text)  # Global notes for the day
    created_at = Column(DateTime, default=datetime.utcnow)

class InventoryDayItem(Base):
    __tablename__ = "inventory_day_items"
    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float, default=0)
    create_task = Column(Boolean, default=True)  # Override for task creation
    
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
    paused_at = Column(DateTime, nullable=True)
    total_pause_time = Column(Integer, default=0)  # in minutes
    notes = Column(Text)
    auto_generated = Column(Boolean, default=False)  # True if generated from below-par items
    
    assigned_to = relationship("User")
    day = relationship("InventoryDay")
    
    @property
    def total_time_minutes(self):
        if not self.started_at or not self.finished_at:
            return 0
        total_seconds = (self.finished_at - self.started_at).total_seconds()
        return int(total_seconds / 60) - self.total_pause_time

class UtilityCost(Base):
    __tablename__ = "utility_costs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    monthly_cost = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)