from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, date
from .database import Base

class VendorUnit(Base):
    __tablename__ = "vendor_units"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # lb, oz, gal, qt, etc.
    description = Column(String)  # Optional description
    created_at = Column(DateTime, default=datetime.utcnow)

class VendorUnitConversion(Base):
    __tablename__ = "vendor_unit_conversions"
    id = Column(Integer, primary_key=True)
    vendor_unit_id = Column(Integer, ForeignKey("vendor_units.id"))
    usage_unit_id = Column(Integer, ForeignKey("usage_units.id"))
    conversion_factor = Column(Float)  # how many usage units per vendor unit
    
    vendor_unit = relationship("VendorUnit")
    usage_unit = relationship("UsageUnit")

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
    vendor_unit_id = Column(Integer, ForeignKey("vendor_units.id"))
    
    # Purchase Level
    purchase_type = Column(String)  # 'case' or 'single'
    purchase_unit_name = Column(String)  # Case, Bag, Sack, Box (container type)
    purchase_weight_volume = Column(Float)  # Total weight/volume in vendor units
    purchase_total_cost = Column(Float)
    breakable_case = Column(Boolean, default=False)
    
    # Item Level (for cases)
    items_per_case = Column(Integer)
    
    category = relationship("Category")
    vendor = relationship("Vendor")
    vendor_unit = relationship("VendorUnit")
    usage_units = relationship("IngredientUsageUnit", back_populates="ingredient")
    
    @property
    def item_cost(self):
        if self.purchase_type == 'case' and self.items_per_case:
            return self.purchase_total_cost / self.items_per_case
        return self.purchase_total_cost
    
    @property
    def item_weight_volume(self):
        """Weight/volume per individual item"""
        if self.purchase_type == 'case' and self.items_per_case and self.purchase_weight_volume:
            return self.purchase_weight_volume / self.items_per_case
        return self.purchase_weight_volume
    
    @property
    def item_description(self):
        """Generate description for individual items in cases"""
        if self.purchase_type == 'case' and self.vendor_unit and self.item_weight_volume:
            return f"{self.item_weight_volume} {self.vendor_unit.name}"
        return ""

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
        # Get the base cost per vendor unit
        if self.ingredient.purchase_type == 'case':
            # For cases, use individual item cost and weight
            base_cost = self.ingredient.item_cost
            base_weight_volume = self.ingredient.item_weight_volume
        else:
            # For single items, use total cost and weight
            base_cost = self.ingredient.purchase_total_cost
            base_weight_volume = self.ingredient.purchase_weight_volume
        
        if not base_weight_volume or not self.conversion_factor:
            return 0
            
        # Calculate cost per vendor unit, then convert to usage unit
        cost_per_vendor_unit = base_cost / base_weight_volume
        return cost_per_vendor_unit / self.conversion_factor

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
    estimated_labor_minutes = Column(Integer)  # Average estimated time
    hourly_labor_rate = Column(Float, default=16.75)  # Configurable labor rate
    can_be_scaled = Column(Boolean, default=False)
    scale_double = Column(Boolean, default=False)
    scale_half = Column(Boolean, default=False)
    scale_quarter = Column(Boolean, default=False)
    scale_eighth = Column(Boolean, default=False)
    scale_sixteenth = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    recipe = relationship("Recipe")
    yield_unit = relationship("UsageUnit")
    
    @property
    def estimated_labor_cost(self):
        """Calculate estimated labor cost based on average time and hourly rate"""
        return (self.estimated_labor_minutes / 60) * self.hourly_labor_rate
    
    @property
    def actual_labor_cost(self):
        """Calculate actual labor cost from most recent completed task"""
        # This will be calculated from the most recent completed inventory task
        # Implementation will be in the route handlers
        return 0
    
    @property
    def average_labor_cost_week(self):
        """Average labor cost from past week's completed tasks"""
        return 0
    
    @property
    def average_labor_cost_month(self):
        """Average labor cost from past month's completed tasks"""
        return 0

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
    portion_unit_id = Column(Integer, ForeignKey("usage_units.id"), nullable=True)
    
    batch = relationship("Batch")
    portion_unit = relationship("UsageUnit")
    
    @property
    def cost(self):
        """Calculate the cost of this dish batch portion"""
        if not self.batch or not self.portion_size:
            return 0
        

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)  # Link to batch
    category = relationship("Category")
    batch = relationship("Batch")
    par_level = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class InventoryDay(Base):
    __tablename__ = "inventory_days"
    id = Column(Integer, primary_key=True)
    date = Column(Date, default=date.today)
    finalized = Column(Boolean, default=False)
    employees_working = Column(String)
    global_notes = Column(Text)  # Global notes for the day
    created_at = Column(DateTime, default=datetime.utcnow)

class InventoryDayItem(Base):
    __tablename__ = "inventory_day_items"
    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float, default=0)
    override_create_task = Column(Boolean, default=False)  # Override to create task for above par items
    override_no_task = Column(Boolean, default=False)  # Override to NOT create task for below par items
    
    inventory_item = relationship("InventoryItem")
    day = relationship("InventoryDay")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    assigned_to_id = Column(Integer, ForeignKey("users.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=True)  # Link to inventory item
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)  # Inherited from inventory item
    description = Column(String)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    total_pause_time = Column(Integer, default=0)  # in seconds
    notes = Column(Text)
    auto_generated = Column(Boolean, default=False)  # True if generated from below-par items
    is_paused = Column(Boolean, default=False)
    
    assigned_to = relationship("User")
    day = relationship("InventoryDay")
    inventory_item = relationship("InventoryItem")
    batch = relationship("Batch")
    
    @property
    def total_time_minutes(self):
        if not self.started_at or not self.finished_at:
            if self.started_at and not self.finished_at:
                # Task is in progress
                current_time = datetime.utcnow()
                if self.is_paused and self.paused_at:
                    total_seconds = (self.paused_at - self.started_at).total_seconds()
                else:
                    total_seconds = (current_time - self.started_at).total_seconds()
                return int(total_seconds / 60) - int(self.total_pause_time / 60)
            return 0
        total_seconds = (self.finished_at - self.started_at).total_seconds()
        return int(total_seconds / 60) - int(self.total_pause_time / 60)
    
    @property
    def labor_cost(self):
        """Calculate labor cost for this task"""
        if self.assigned_to and self.total_time_minutes > 0:
            return (self.total_time_minutes / 60) * self.assigned_to.hourly_wage
        return 0
    
    @property
    def status(self):
        if not self.started_at:
            return "not_started"
        elif self.finished_at:
            return "completed"
        elif self.is_paused:
            return "paused"
        else:
            return "in_progress"

class UtilityCost(Base):
    __tablename__ = "utility_costs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    monthly_cost = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)