from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    role = Column(String, default="user")  # admin, manager, user
    hourly_wage = Column(Float, default=15.0)
    work_schedule = Column(String)  # comma-separated days
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)  # ingredient, recipe, dish, inventory
    
    # Add unique constraint on name + type combination
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class Vendor(Base):
    __tablename__ = "vendors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    contact_info = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class VendorUnit(Base):
    __tablename__ = "vendor_units"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    
    # Relationships
    conversions = relationship("VendorUnitConversion", back_populates="vendor_unit")

class UsageUnit(Base):
    __tablename__ = "usage_units"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    
    # Relationships
    vendor_conversions = relationship("VendorUnitConversion", back_populates="usage_unit")

class VendorUnitConversion(Base):
    __tablename__ = "vendor_unit_conversions"
    
    id = Column(Integer, primary_key=True, index=True)
    vendor_unit_id = Column(Integer, ForeignKey("vendor_units.id"))
    usage_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    conversion_factor = Column(Float)  # How many usage units per vendor unit
    
    # Relationships
    vendor_unit = relationship("VendorUnit", back_populates="conversions")
    usage_unit = relationship("UsageUnit", back_populates="vendor_conversions")

class Ingredient(Base):
    __tablename__ = "ingredients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    
    # Purchase level information
    purchase_type = Column(String, default="single")  # single, case
    purchase_unit_name = Column(String)  # Case, Bag, Sack, etc.
    vendor_unit_id = Column(Integer, ForeignKey("vendor_units.id"))
    purchase_weight_volume = Column(Float)
    purchase_total_cost = Column(Float)
    breakable_case = Column(Boolean, default=False)
    
    # Case-specific fields
    items_per_case = Column(Integer)
    item_weight_volume = Column(Float)  # Calculated: purchase_weight_volume / items_per_case
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")
    vendor = relationship("Vendor")
    vendor_unit = relationship("VendorUnit")
    usage_units = relationship("IngredientUsageUnit", back_populates="ingredient")

class IngredientUsageUnit(Base):
    __tablename__ = "ingredient_usage_units"
    
    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    usage_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    conversion_factor = Column(Float)  # How many usage units per purchase unit
    price_per_usage_unit = Column(Float)  # Calculated from ingredient cost and conversion
    
    # Relationships
    ingredient = relationship("Ingredient", back_populates="usage_units")
    usage_unit = relationship("UsageUnit")

class Recipe(Base):
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    instructions = Column(Text)
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")
    ingredients = relationship("RecipeIngredient", back_populates="recipe")

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    usage_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    quantity = Column(Float)
    cost = Column(Float)  # Calculated from quantity * price_per_usage_unit
    
    # Relationships
    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient")
    usage_unit = relationship("UsageUnit")

class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    
    # Yield information - nullable for variable yields
    is_variable = Column(Boolean, default=False)
    yield_amount = Column(Float)  # Nullable for variable yields
    yield_unit_id = Column(Integer, ForeignKey("usage_units.id"))  # Nullable for variable yields
    
    # Labor information
    estimated_labor_minutes = Column(Integer)
    hourly_labor_rate = Column(Float, default=16.75)
    
    # Scaling options
    can_be_scaled = Column(Boolean, default=False)
    scale_double = Column(Boolean, default=False)
    scale_half = Column(Boolean, default=False)
    scale_quarter = Column(Boolean, default=False)
    scale_eighth = Column(Boolean, default=False)
    scale_sixteenth = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    recipe = relationship("Recipe")
    yield_unit = relationship("UsageUnit")
    
    @property
    def estimated_labor_cost(self):
        return (self.estimated_labor_minutes / 60) * self.hourly_labor_rate

class Dish(Base):
    __tablename__ = "dishes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    sale_price = Column(Float)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")
    batch_portions = relationship("DishBatchPortion", back_populates="dish")

class DishBatchPortion(Base):
    __tablename__ = "dish_batch_portions"
    
    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"))
    portion_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    portion_size = Column(Float)
    expected_cost = Column(Float)  # Calculated cost
    actual_cost = Column(Float)  # Based on actual labor data
    
    # Relationships
    dish = relationship("Dish", back_populates="batch_portions")
    batch = relationship("Batch")
    portion_unit = relationship("UsageUnit")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    par_level = Column(Float)
    
    # Par unit equals system
    par_unit_equals_amount = Column(Float, default=1.0)
    par_unit_equals_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    
    # Conversion system
    manual_conversion_factor = Column(Float)  # Override automatic conversion
    conversion_notes = Column(String)  # User notes about conversion
    
    # Batch linking
    batch_id = Column(Integer, ForeignKey("batches.id"))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")
    batch = relationship("Batch")
    par_unit_equals_unit = relationship("UsageUnit")

class InventoryDay(Base):
    __tablename__ = "inventory_days"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True)
    employees_working = Column(String)  # comma-separated employee IDs
    global_notes = Column(Text)
    finalized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    items = relationship("InventoryDayItem", back_populates="day")
    tasks = relationship("Task", back_populates="day")

class InventoryDayItem(Base):
    __tablename__ = "inventory_day_items"
    
    id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float)
    override_create_task = Column(Boolean, default=False)
    override_no_task = Column(Boolean, default=False)
    
    # Relationships
    day = relationship("InventoryDay", back_populates="items")
    inventory_item = relationship("InventoryItem")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    assigned_to_id = Column(Integer, ForeignKey("users.id"))
    description = Column(String)
    status = Column(String, default="not_started")  # not_started, in_progress, paused, completed
    auto_generated = Column(Boolean, default=False)
    
    # Batch and inventory linking
    batch_id = Column(Integer, ForeignKey("batches.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    
    # Task completion data
    requires_manual_made = Column(Boolean, default=False)
    made_amount = Column(Float)  # Manual input for variable yields
    made_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    selected_scale = Column(String)  # For scalable batches: "double", "half", etc.
    final_inventory_amount = Column(Float)  # Calculated final inventory
    
    # Time tracking
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    paused_at = Column(DateTime)
    is_paused = Column(Boolean, default=False)
    total_pause_time = Column(Integer, default=0)  # seconds
    notes = Column(Text)
    
    # Relationships
    day = relationship("InventoryDay", back_populates="tasks")
    assigned_to = relationship("User")
    batch = relationship("Batch")
    inventory_item = relationship("InventoryItem")
    made_unit = relationship("UsageUnit")
    
    @property
    def total_time_minutes(self):
        if not self.started_at:
            return 0
        
        end_time = self.finished_at or datetime.utcnow()
        total_seconds = (end_time - self.started_at).total_seconds()
        total_seconds -= self.total_pause_time
        return max(0, int(total_seconds / 60))
    
    @property
    def labor_cost(self):
        if not self.assigned_to or not self.started_at:
            return 0.0
        return (self.total_time_minutes / 60) * self.assigned_to.hourly_wage
    
    @property
    def can_be_completed(self):
        """Check if task can be completed based on requirements"""
        if self.status == "completed":
            return False
        if self.requires_manual_made and not self.made_amount:
            return False
        return True
    
    def get_made_amount_in_par_units(self):
        """Get the made amount converted to par units"""
        if not self.inventory_item or not self.inventory_item.par_unit_equals_unit_id:
            return None
        
        if self.made_amount and self.made_unit_id:
            # Manual made amount - convert if needed
            if self.made_unit_id == self.inventory_item.par_unit_equals_unit_id:
                return self.made_amount
            # TODO: Add conversion logic here
            return self.made_amount
        
        if self.selected_scale and self.batch and not self.batch.is_variable:
            # Scaled batch - calculate from batch yield
            scale_factors = {
                "double": 2.0,
                "full": 1.0,
                "half": 0.5,
                "quarter": 0.25,
                "eighth": 0.125,
                "sixteenth": 0.0625
            }
            scale_factor = scale_factors.get(self.selected_scale, 1.0)
            batch_yield = self.batch.yield_amount * scale_factor
            
            # TODO: Convert batch yield to par units using conversion system
            return batch_yield
        
        return None

class UtilityCost(Base):
    __tablename__ = "utility_costs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    monthly_cost = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)