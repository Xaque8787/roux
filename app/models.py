from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, date
from .database import Base

class JanitorialTask(Base):
    __tablename__ = "janitorial_tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    instructions = Column(Text)
    task_type = Column(String, nullable=False)  # 'daily' or 'manual'
    created_at = Column(DateTime, default=datetime.utcnow)

class JanitorialTaskDay(Base):
    __tablename__ = "janitorial_task_days"
    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    janitorial_task_id = Column(Integer, ForeignKey("janitorial_tasks.id"))
    include_task = Column(Boolean, default=True)  # For manual tasks
    
    janitorial_task = relationship("JanitorialTask")
    day = relationship("InventoryDay")

# Standard conversion tables
WEIGHT_CONVERSIONS = {
    'lb': 1.0,      # Base unit: pounds
    'oz': 16.0,     # 16 oz per lb
    'g': 453.592,   # 453.592 g per lb
    'kg': 0.453592, # 0.453592 kg per lb
}

VOLUME_CONVERSIONS = {
    'gal': 1.0,     # Base unit: gallons
    'qt': 4.0,      # 4 qt per gal
    'pt': 8.0,      # 8 pt per gal
    'cup': 16.0,    # 16 cups per gal
    'fl_oz': 128.0, # 128 fl oz per gal
    'l': 3.78541,   # 3.78541 L per gal
    'ml': 3785.41,  # 3785.41 ml per gal
}

BAKING_MEASUREMENTS = {
    'cup': 1.0,      # Base unit: cups
    '3_4_cup': 0.75,
    '2_3_cup': 0.667,
    '1_2_cup': 0.5,
    '1_3_cup': 0.333,
    '1_4_cup': 0.25,
    '1_8_cup': 0.125,
    'tbsp': 16.0,    # 16 tbsp per cup
    'tsp': 48.0,     # 48 tsp per cup
}

def convert_weight(amount, from_unit, to_unit):
    """Convert between weight units"""
    if from_unit not in WEIGHT_CONVERSIONS or to_unit not in WEIGHT_CONVERSIONS:
        raise ValueError(f"Invalid weight units: {from_unit} or {to_unit}")
    
    # Convert to base unit (pounds) then to target unit
    base_amount = amount / WEIGHT_CONVERSIONS[from_unit]
    return round(base_amount * WEIGHT_CONVERSIONS[to_unit], 2)

def convert_volume(amount, from_unit, to_unit):
    """Convert between volume units"""
    if from_unit not in VOLUME_CONVERSIONS or to_unit not in VOLUME_CONVERSIONS:
        raise ValueError(f"Invalid volume units: {from_unit} or {to_unit}")
    
    # Convert to base unit (gallons) then to target unit
    base_amount = amount / VOLUME_CONVERSIONS[from_unit]
    return round(base_amount * VOLUME_CONVERSIONS[to_unit], 2)

def convert_baking_measurement(amount, from_unit, to_unit, ingredient_density_oz_per_cup):
    """Convert between baking measurements using ingredient density"""
    if from_unit not in BAKING_MEASUREMENTS or to_unit not in BAKING_MEASUREMENTS:
        raise ValueError(f"Invalid baking units: {from_unit} or {to_unit}")
    
    # Convert to base unit (cups)
    cups = amount / BAKING_MEASUREMENTS[from_unit]
    
    # Convert to target unit
    target_amount = cups * BAKING_MEASUREMENTS[to_unit]
    
    return round(target_amount, 2)

def get_baking_weight(amount, baking_unit, ingredient_density_oz_per_cup):
    """Convert baking measurement to weight using ingredient density"""
    if baking_unit not in BAKING_MEASUREMENTS:
        raise ValueError(f"Invalid baking unit: {baking_unit}")
    
    # Convert to cups first
    cups = amount / BAKING_MEASUREMENTS[baking_unit]
    
    # Convert to weight using density
    weight_oz = cups * ingredient_density_oz_per_cup
    
    return round(weight_oz, 2)

class VendorUnit(Base):
    __tablename__ = "vendor_units"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # lb, oz, gal, qt, etc.
    description = Column(String)  # Optional description
    created_at = Column(DateTime, default=datetime.utcnow)

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
    name = Column(String, nullable=False)
    type = Column(String)  # 'ingredient', 'recipe', 'batch', 'dish', 'inventory'
    icon = Column(String)  # Unicode emoji
    color = Column(String)  # Hex color code

class ParUnitName(Base):
    __tablename__ = "par_unit_names"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # Tub, Case, Container, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    vendor_unit_id = Column(Integer, ForeignKey("vendor_units.id"))
    
    # New usage type system
    usage_type = Column(String, nullable=False)  # 'weight' or 'volume'
    
    # Purchase Level
    purchase_type = Column(String)  # 'case' or 'single'
    purchase_unit_name = Column(String)  # Case, Bag, Sack, Box (container type)
    purchase_total_cost = Column(Float)
    breakable_case = Column(Boolean, default=False)
    
    # Item count pricing option
    use_item_count_pricing = Column(Boolean, default=False)
    
    # Net Weight/Volume (replaces purchase_weight_volume)
    net_weight_volume_item = Column(Float)  # Net weight/volume per item
    net_weight_volume_case = Column(Float)  # Net weight/volume per case (auto-calculated)
    net_unit = Column(String)  # The unit for net weight/volume (lb, oz, gal, etc.)
    
    # Item Level (for cases)
    items_per_case = Column(Integer)
    
    # Baking Measurements Conversion
    has_baking_conversion = Column(Boolean, default=False)
    baking_measurement_unit = Column(String)  # cup, tbsp, etc.
    baking_measurement_amount = Column(Float)  # user entered amount
    baking_weight_unit = Column(String)  # oz, g, etc.
    baking_weight_amount = Column(Float)  # user entered weight
    
    category = relationship("Category")
    vendor = relationship("Vendor")
    vendor_unit = relationship("VendorUnit")
    
    @property
    def item_cost(self):
        if self.purchase_type == 'case' and self.items_per_case:
            return self.purchase_total_cost / self.items_per_case
        return self.purchase_total_cost
    
    @property
    def total_item_count(self):
        """Total item count for the entire purchase"""
        if self.purchase_type == 'case' and self.items_per_case:
            return self.items_per_case
        return 1
    
    @property
    def total_net_weight_volume(self):
        """Total net weight/volume for the entire purchase"""
        if self.use_item_count_pricing:
            return None
        if self.purchase_type == 'case':
            return self.net_weight_volume_case
        return self.net_weight_volume_item
    
    @property
    def cost_per_net_unit(self):
        """Cost per net unit (lb, oz, gal, etc.)"""
        if self.use_item_count_pricing:
            return self.purchase_total_cost / self.total_item_count
        if self.total_net_weight_volume and self.total_net_weight_volume > 0:
            return round(self.purchase_total_cost / self.total_net_weight_volume, 4)
        return 0
    
    @property
    def cost_per_item(self):
        """Cost per individual item"""
        if self.use_item_count_pricing:
            return self.purchase_total_cost / self.total_item_count
        return self.cost_per_net_unit
    
    def get_available_units(self):
        """Get available units for this ingredient based on usage type"""
        if self.use_item_count_pricing:
            return ['item', 'each']
        
        if self.usage_type == 'weight':
            units = list(WEIGHT_CONVERSIONS.keys())
        else:  # volume
            units = list(VOLUME_CONVERSIONS.keys())
        
        # Add baking measurements if available
        if self.has_baking_conversion:
            units.extend(list(BAKING_MEASUREMENTS.keys()))
        
        return units
    
    def get_cost_per_unit(self, unit):
        """Get cost per specified unit"""
        if self.use_item_count_pricing:
            if unit in ['item', 'each']:
                return self.cost_per_item
            return 0
        
        if not self.total_net_weight_volume or self.total_net_weight_volume <= 0:
            return 0
        
        # Handle baking measurements
        if unit in BAKING_MEASUREMENTS and self.has_baking_conversion:
            # Check if baking conversion data is complete
            if (self.baking_measurement_unit and self.baking_weight_amount and 
                self.baking_weight_unit and self.baking_weight_amount > 0):
                
                # Step 1: Get cost per baking weight unit (e.g., cost per ounce)
                try:
                    cost_per_baking_weight_unit = self.get_cost_per_unit(self.baking_weight_unit)
                except ValueError:
                    return 0
                
                # Step 2: Calculate how much weight the requested unit represents
                # Example 1: Defined "1 cup = 5 oz", want "1/2 cup"
                #   - 1 cup = 5 oz, so 1/2 cup = 2.5 oz
                # Example 2: Defined "1 tbsp = 6 oz", want "1 cup" 
                #   - 1 tbsp = 6 oz, 1 cup = 16 tbsp, so 1 cup = 16 * 6 = 96 oz
                
                if self.baking_measurement_unit in BAKING_MEASUREMENTS and unit in BAKING_MEASUREMENTS:
                    # BAKING_MEASUREMENTS values represent "how many of this unit per cup"
                    # Example: 'cup': 1.0, '1_2_cup': 2.0, 'tbsp': 16.0
                    defined_ratio = BAKING_MEASUREMENTS[self.baking_measurement_unit]
                    requested_ratio = BAKING_MEASUREMENTS[unit]
                    
                    # Calculate how much of the requested unit we need relative to the defined unit
                    # Example 1: Defined 1 cup (1.0 per cup), want 1/2 cup (2.0 per cup)
                    #   - We want 1/2 the amount, so multiplier = 1.0 / 2.0 = 0.5
                    # Example 2: Defined 1 tbsp (16.0 per cup), want 1 cup (1.0 per cup)  
                    #   - We want 16 times the amount, so multiplier = 16.0 / 1.0 = 16.0
                    measurement_multiplier = defined_ratio / requested_ratio
                    
                    # Calculate weight for the requested measurement
                    weight_for_requested_unit = self.baking_weight_amount * measurement_multiplier
                    
                    # Calculate cost based on that weight
                    cost_for_requested_unit = weight_for_requested_unit * cost_per_baking_weight_unit
                    
                    return round(cost_for_requested_unit, 4)
                else:
                    return 0
            else:
                return 0
        
        # Handle standard weight/volume conversions
        try:
            if self.usage_type == 'weight':
                conversion_factor = convert_weight(1, self.net_unit, unit)
            else:  # volume
                conversion_factor = convert_volume(1, self.net_unit, unit)
            
            return round(self.cost_per_net_unit / conversion_factor, 4)
        except ValueError:
            return 0

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category")
    instructions = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Add relationship to recipe ingredients
    ingredients = relationship("RecipeIngredient", back_populates="recipe")

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    unit = Column(String, nullable=False)  # Standard unit (lb, oz, cup, etc.)
    quantity = Column(Float)
    
    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient")
    
    @property
    def cost(self):
        """Calculate the cost of this recipe ingredient"""
        if self.ingredient and self.unit and self.quantity:
            cost_per_unit = self.ingredient.get_cost_per_unit(self.unit)
            return round(self.quantity * cost_per_unit, 2)
        return 0

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    # Variable yield option
    variable_yield = Column(Boolean, default=False)
    yield_amount = Column(Float)
    yield_unit = Column(String)  # Standard unit (lb, oz, gal, etc.)
    
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
    category = relationship("Category")
    
    @property
    def estimated_labor_cost(self):
        """Calculate estimated labor cost based on average time and hourly rate"""
        return (self.estimated_labor_minutes / 60) * self.hourly_labor_rate
    
    def get_scaled_yield(self, scale_factor):
        """Get yield amount for a specific scale factor"""
        if self.variable_yield:
            return None  # Variable yield batches don't have predetermined amounts
        return round(self.yield_amount * scale_factor, 2)
    
    def get_available_scales(self):
        """Get available scale options for this batch"""
        scales = [('full', 1.0, 'Full Batch')]
        
        if self.can_be_scaled:
            if self.scale_double:
                scales.append(('double', 2.0, 'Double Batch'))
            if self.scale_half:
                scales.append(('half', 0.5, 'Half Batch'))
            if self.scale_quarter:
                scales.append(('quarter', 0.25, 'Quarter Batch'))
            if self.scale_eighth:
                scales.append(('eighth', 0.125, 'Eighth Batch'))
            if self.scale_sixteenth:
                scales.append(('sixteenth', 0.0625, 'Sixteenth Batch'))
        
        return scales
    
    @property
    def actual_labor_cost(self):
        """Fallback to estimated labor cost - use get_actual_labor_cost(db) for real data"""
        return self.estimated_labor_cost
    
    @property
    def average_labor_cost_week(self):
        """Fallback to estimated labor cost - use get_average_labor_cost_week(db) for real data"""
        return self.estimated_labor_cost
    
    @property
    def average_labor_cost_month(self):
        """Fallback to estimated labor cost - use get_average_labor_cost_month(db) for real data"""
        return self.estimated_labor_cost

    @property
    def average_labor_cost_all_time(self):
        """Fallback to estimated labor cost - use get_average_labor_cost_all_time(db) for real data"""
        return self.estimated_labor_cost
    
    def get_actual_labor_cost(self, db):
        """Calculate actual labor cost from most recent completed task"""
        from sqlalchemy import or_, and_
        recent_task = db.query(Task).filter(
            or_(
                Task.batch_id == self.id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.id)
                )
            ),
            Task.finished_at.isnot(None)
        ).order_by(Task.finished_at.desc()).first()
        
        if recent_task:
            return recent_task.labor_cost
        return self.estimated_labor_cost
    
    def get_average_labor_cost_week(self, db):
        """Average labor cost from past week's completed tasks"""
        from datetime import datetime, timedelta
        from sqlalchemy import or_, and_
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        tasks = db.query(Task).filter(
            or_(
                Task.batch_id == self.id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.id)
                )
            ),
            Task.finished_at.isnot(None),
            Task.finished_at >= week_ago
        ).all()
        
        if tasks:
            return sum(task.labor_cost for task in tasks) / len(tasks)
        return self.estimated_labor_cost
    
    def get_average_labor_cost_month(self, db):
        """Average labor cost from past month's completed tasks"""
        from datetime import datetime, timedelta
        from sqlalchemy import or_, and_
        month_ago = datetime.utcnow() - timedelta(days=30)
        
        tasks = db.query(Task).filter(
            or_(
                Task.batch_id == self.id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.id)
                )
            ),
            Task.finished_at.isnot(None),
            Task.finished_at >= month_ago
        ).all()
        
        if tasks:
            return sum(task.labor_cost for task in tasks) / len(tasks)
        return self.estimated_labor_cost
    
    def get_average_labor_cost_all_time(self, db):
        """Average labor cost from all completed tasks"""
        from sqlalchemy import or_, and_
        tasks = db.query(Task).filter(
            or_(
                Task.batch_id == self.id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.id)
                )
            ),
            Task.finished_at.isnot(None)
        ).all()
        
        if tasks:
            return sum(task.labor_cost for task in tasks) / len(tasks)
        return self.estimated_labor_cost

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
    portion_unit = Column(String)  # Standard unit
    
    # Recipe portion fields
    use_recipe_portion = Column(Boolean, default=False)
    recipe_portion_percent = Column(Float)  # Percentage of recipe (0.0 to 1.0)
    
    batch = relationship("Batch")

class DishIngredientPortion(Base):
    __tablename__ = "dish_ingredient_portions"
    id = Column(Integer, primary_key=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)  # Standard unit
    
    ingredient = relationship("Ingredient")
    
    @property
    def cost(self):
        """Calculate the cost of this dish ingredient portion"""
        if self.ingredient and self.unit and self.quantity:
            cost_per_unit = self.ingredient.get_cost_per_unit(self.unit)
            return round(self.quantity * cost_per_unit, 2)
        return 0
    
    def get_recipe_cost(self, db):
        """Get just the recipe/food cost portion"""
        if not self.batch:
            return 0
        
        # Handle recipe portion for variable yield batches
        if self.use_recipe_portion and self.recipe_portion_percent:
            recipe_ingredients = db.query(RecipeIngredient).filter(
                RecipeIngredient.recipe_id == self.batch.recipe_id
            ).all()
            
            total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
            return round(total_recipe_cost * self.recipe_portion_percent, 2)
        
        # For regular portion mode, check if we have portion size
        if not self.portion_size:
            return 0
        
        # For non-recipe portion mode, check if we have portion size
        if not self.portion_size:
            return 0
        
        if self.batch.variable_yield:
            return 0  # Can't calculate for variable yield without recipe portion
        
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == self.batch.recipe_id
        ).all()
        
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        recipe_cost_per_yield_unit = total_recipe_cost / self.batch.yield_amount
        
        # Handle unit conversion for portion
        if self.portion_unit == self.batch.yield_unit:
            return self.portion_size * recipe_cost_per_yield_unit
        else:
            # Convert between units (simplified for now)
            try:
                if self.batch.yield_unit in WEIGHT_CONVERSIONS and self.portion_unit in WEIGHT_CONVERSIONS:
                    converted_portion = convert_weight(self.portion_size, self.portion_unit, self.batch.yield_unit)
                elif self.batch.yield_unit in VOLUME_CONVERSIONS and self.portion_unit in VOLUME_CONVERSIONS:
                    converted_portion = convert_volume(self.portion_size, self.portion_unit, self.batch.yield_unit)
                else:
                    converted_portion = self.portion_size
                
                return converted_portion * recipe_cost_per_yield_unit
            except ValueError:
                return self.portion_size * recipe_cost_per_yield_unit
    
    def get_labor_cost(self, db, labor_type='actual'):
        """Get just the labor cost portion"""
        if not self.batch:
            return 0
        
        # Handle recipe portion for variable yield batches
        if self.use_recipe_portion and self.recipe_portion_percent:
            # Get labor cost based on type
            if labor_type == 'estimated':
                labor_cost = self.batch.estimated_labor_cost
            elif labor_type == 'actual':
                labor_cost = self.batch.get_actual_labor_cost(db)
            elif labor_type == 'week_avg':
                labor_cost = self.batch.get_average_labor_cost_week(db)
            elif labor_type == 'month_avg':
                labor_cost = self.batch.get_average_labor_cost_month(db)
            elif labor_type == 'all_time_avg':
                labor_cost = self.batch.get_average_labor_cost_all_time(db)
            else:
                labor_cost = self.batch.estimated_labor_cost
            
            return round(labor_cost * self.recipe_portion_percent, 2)
        
        # For non-recipe portion mode, check if we have portion size
        if not self.portion_size:
            return 0
        
        if self.batch.variable_yield:
            return 0  # Can't calculate for variable yield without recipe portion
        
        # Get labor cost based on type
        if labor_type == 'estimated':
            labor_cost = self.batch.estimated_labor_cost
        elif labor_type == 'actual':
            labor_cost = self.batch.get_actual_labor_cost(db)
        elif labor_type == 'week_avg':
            labor_cost = self.batch.get_average_labor_cost_week(db)
        elif labor_type == 'month_avg':
            labor_cost = self.batch.get_average_labor_cost_month(db)
        elif labor_type == 'all_time_avg':
            labor_cost = self.batch.get_average_labor_cost_all_time(db)
        else:
            labor_cost = self.batch.estimated_labor_cost
        
        labor_cost_per_yield_unit = labor_cost / self.batch.yield_amount
        
        # Handle unit conversion for portion
        if self.portion_unit == self.batch.yield_unit:
            return self.portion_size * labor_cost_per_yield_unit
        else:
            # Convert between units (simplified for now)
            try:
                if self.batch.yield_unit in WEIGHT_CONVERSIONS and self.portion_unit in WEIGHT_CONVERSIONS:
                    converted_portion = convert_weight(self.portion_size, self.portion_unit, self.batch.yield_unit)
                elif self.batch.yield_unit in VOLUME_CONVERSIONS and self.portion_unit in VOLUME_CONVERSIONS:
                    converted_portion = convert_volume(self.portion_size, self.portion_unit, self.batch.yield_unit)
                else:
                    converted_portion = self.portion_size
                
                return converted_portion * labor_cost_per_yield_unit
            except ValueError:
                return self.portion_size * labor_cost_per_yield_unit
    
    @property
    def expected_cost(self):
        """Calculate expected cost using estimated labor"""
        # This property is deprecated - use get_expected_cost(db) instead
        return 0
    
    @property
    def actual_cost(self):
        """Calculate actual cost using most recent actual labor"""
        # This property is deprecated - use get_actual_cost(db) instead
        return 0
    
    @property
    def actual_cost_week_avg(self):
        """Calculate actual cost using week average labor"""
        # This property is deprecated - use get_actual_cost_week_avg(db) instead
        return 0
    
    @property
    def actual_cost_month_avg(self):
        """Calculate actual cost using month average labor"""
        # This property is deprecated - use get_actual_cost_month_avg(db) instead
        return 0
    
    @property
    def actual_cost_all_time_avg(self):
        """Calculate actual cost using all-time average labor"""
        # This property is deprecated - use get_actual_cost_all_time_avg(db) instead
        return 0
    
    def get_expected_cost(self, db):
        """Calculate expected cost using estimated labor"""
        return self._calculate_cost_with_labor_type(db, 'estimated')
    
    def get_actual_cost(self, db):
        """Calculate actual cost using most recent actual labor"""
        return self._calculate_cost_with_labor_type(db, 'actual')
    
    def get_actual_cost_week_avg(self, db):
        """Calculate actual cost using week average labor"""
        return self._calculate_cost_with_labor_type(db, 'week_avg')
    
    def get_actual_cost_month_avg(self, db):
        """Calculate actual cost using month average labor"""
        return self._calculate_cost_with_labor_type(db, 'month_avg')
    
    def get_actual_cost_all_time_avg(self, db):
        """Calculate actual cost using all-time average labor"""
        return self._calculate_cost_with_labor_type(db, 'all_time_avg')
    
    def _calculate_cost_with_labor_type(self, db, labor_type):
        """Calculate the cost of this dish batch portion"""
        if not self.batch:
            return 0
        
        # Handle recipe portion for variable yield batches
        if self.use_recipe_portion and self.recipe_portion_percent:
            recipe_cost = self.get_recipe_cost(db)
            labor_cost = self.get_labor_cost(db, labor_type)
            return round(recipe_cost + labor_cost, 2)
        
        # For non-recipe portion mode, check if we have portion size
        if not self.portion_size:
            return 0
        
        if self.batch.variable_yield:
            return 0
        
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == self.batch.recipe_id
        ).all()
        
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        
        # Get labor cost based on type
        if labor_type == 'estimated':
            labor_cost = self.batch.estimated_labor_cost
        elif labor_type == 'actual':
            labor_cost = self.batch.get_actual_labor_cost(db)
        elif labor_type == 'week_avg':
            labor_cost = self.batch.get_average_labor_cost_week(db)
        elif labor_type == 'month_avg':
            labor_cost = self.batch.get_average_labor_cost_month(db)
        elif labor_type == 'all_time_avg':
            labor_cost = self.batch.get_average_labor_cost_all_time(db)
        else:
            labor_cost = self.batch.estimated_labor_cost
        
        total_batch_cost = total_recipe_cost + labor_cost
        cost_per_yield_unit = total_batch_cost / self.batch.yield_amount
        
        # Handle unit conversion
        if self.portion_unit == self.batch.yield_unit:
            return self.portion_size * cost_per_yield_unit
        else:
            # Convert between units
            usage_type = None
            for ri in recipe_ingredients:
                ingredient = db.query(Ingredient).filter(Ingredient.id == ri.ingredient_id).first()
                if ingredient and ingredient.usage_type:
                    usage_type = ingredient.usage_type
                    break
            
            try:
                if usage_type == 'weight' and self.batch.yield_unit in WEIGHT_CONVERSIONS and self.portion_unit in WEIGHT_CONVERSIONS:
                    converted_portion = convert_weight(self.portion_size, self.portion_unit, self.batch.yield_unit)
                elif usage_type == 'volume' and self.batch.yield_unit in VOLUME_CONVERSIONS and self.portion_unit in VOLUME_CONVERSIONS:
                    converted_portion = convert_volume(self.portion_size, self.portion_unit, self.batch.yield_unit)
                elif self.batch.yield_unit in WEIGHT_CONVERSIONS and self.portion_unit in WEIGHT_CONVERSIONS:
                    converted_portion = convert_weight(self.portion_size, self.portion_unit, self.batch.yield_unit)
                elif self.batch.yield_unit in VOLUME_CONVERSIONS and self.portion_unit in VOLUME_CONVERSIONS:
                    converted_portion = convert_volume(self.portion_size, self.portion_unit, self.batch.yield_unit)
                else:
                    converted_portion = self.portion_size
                
                return converted_portion * cost_per_yield_unit
            except ValueError:
                return self.portion_size * cost_per_yield_unit
    
    # Keep the old cost property for backward compatibility
    @property
    def cost(self):
        """Backward compatibility - returns actual cost"""
        # This property is deprecated - use get_actual_cost(db) instead
        return 0
    

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)  # Link to batch
    
    # New par unit system
    par_unit_name_id = Column(Integer, ForeignKey("par_unit_names.id"), nullable=True)
    par_unit_equals_type = Column(String)  # 'auto', 'par_unit_itself', 'custom'
    par_unit_equals_amount = Column(Float)  # For custom type
    par_unit_equals_unit = Column(String)  # For custom type
    
    category = relationship("Category")
    batch = relationship("Batch")
    par_unit_name = relationship("ParUnitName")
    par_level = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @property
    def par_unit_equals_calculated(self):
        """Calculate par unit equals based on type and batch"""
        if not self.batch:
            return None
        
        if self.par_unit_equals_type == 'auto' and not self.batch.variable_yield:
            # Auto: batch yield divided by par level
            if self.par_level > 0:
                return round(self.batch.yield_amount / self.par_level, 2)
        elif self.par_unit_equals_type == 'par_unit_itself':
            # Par unit itself is the amount
            return 1.0
        elif self.par_unit_equals_type == 'custom':
            # Custom amount entered by user
            return self.par_unit_equals_amount
        
        return None
    
    def convert_to_par_units(self, amount, unit):
        """Convert an amount in given unit to par units"""
        par_unit_equals = self.par_unit_equals_calculated
        if not par_unit_equals:
            return amount  # Can't convert, return as-is
        
        if self.par_unit_equals_type == 'par_unit_itself':
            # Direct conversion - amount is already in par units
            return amount
        elif self.par_unit_equals_type == 'custom':
            # Convert using custom conversion
            if unit == self.par_unit_equals_unit:
                return round(amount / par_unit_equals, 2)
            else:
                # Need to convert units first
                try:
                    if unit in WEIGHT_CONVERSIONS and self.par_unit_equals_unit in WEIGHT_CONVERSIONS:
                        converted_amount = convert_weight(amount, unit, self.par_unit_equals_unit)
                    elif unit in VOLUME_CONVERSIONS and self.par_unit_equals_unit in VOLUME_CONVERSIONS:
                        converted_amount = convert_volume(amount, unit, self.par_unit_equals_unit)
                    else:
                        converted_amount = amount  # Can't convert
                    
                    return round(converted_amount / par_unit_equals, 2)
                except ValueError:
                    return amount
        elif self.par_unit_equals_type == 'auto' and self.batch:
            # Convert using batch yield unit
            if unit == self.batch.yield_unit:
                return round(amount / par_unit_equals, 2)
            else:
                try:
                    if unit in WEIGHT_CONVERSIONS and self.batch.yield_unit in WEIGHT_CONVERSIONS:
                        converted_amount = convert_weight(amount, unit, self.batch.yield_unit)
                    elif unit in VOLUME_CONVERSIONS and self.batch.yield_unit in VOLUME_CONVERSIONS:
                        converted_amount = convert_volume(amount, unit, self.batch.yield_unit)
                    else:
                        converted_amount = amount
                    
                    return round(converted_amount / par_unit_equals, 2)
                except ValueError:
                    return amount
        
        return amount

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
    assigned_employee_ids = Column(String)  # Comma-separated list of employee IDs
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=True)  # Link to inventory item
    janitorial_task_id = Column(Integer, ForeignKey("janitorial_tasks.id"), nullable=True)  # Link to janitorial task
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)  # Inherited from inventory item
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # For manual tasks
    description = Column(String)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    total_pause_time = Column(Integer, default=0)  # in seconds
    notes = Column(Text)
    auto_generated = Column(Boolean, default=False)  # True if generated from below-par items
    is_paused = Column(Boolean, default=False)
    
    # New fields for variable yield and scaling
    selected_scale = Column(String)  # 'full', 'half', 'double', etc.
    scale_factor = Column(Float, default=1.0)  # Numeric scale factor
    made_amount = Column(Float)  # Amount made (for variable yield)
    made_unit = Column(String)  # Unit for made amount
    assigned_to = relationship("User")
    day = relationship("InventoryDay")
    inventory_item = relationship("InventoryItem")
    janitorial_task = relationship("JanitorialTask")
    batch = relationship("Batch")
    category = relationship("Category")
    
    @property
    def task_source(self):
        """Identify the source type of this task"""
        if self.inventory_item_id:
            return "inventory"
        elif self.janitorial_task_id:
            return "janitorial"
        else:
            return "manual"
    
    @property
    def food_cost(self):
        """Calculate food cost - janitorial tasks have zero food cost"""
        if self.janitorial_task_id:
            return 0.0
        # For inventory tasks, would need to calculate from batch/recipe
        # This is a placeholder for future food cost calculation
        return 0.0
    
    @property
    def assigned_employees(self):
        """Get list of assigned employee objects"""
        if not self.assigned_employee_ids:
            return [self.assigned_to] if self.assigned_to else []
        
        from sqlalchemy.orm import sessionmaker
        from .database import engine
        Session = sessionmaker(bind=engine)
        db = Session()
        
        try:
            employee_ids = [int(id_str) for id_str in self.assigned_employee_ids.split(',') if id_str.strip()]
            employees = db.query(User).filter(User.id.in_(employee_ids)).all()
            return employees
        except (ValueError, AttributeError):
            return [self.assigned_to] if self.assigned_to else []
        finally:
            db.close()
    
    @property
    def highest_hourly_wage(self):
        """Get the highest hourly wage among assigned employees"""
        employees = self.assigned_employees
        if not employees:
            return 0
        return max(emp.hourly_wage for emp in employees)
    
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
        if self.total_time_minutes > 0:
            # Use highest wage from assigned employees, or batch estimated wage if unassigned
            wage = self.highest_hourly_wage
            if wage == 0 and self.batch:
                # No assigned employee, use batch's estimated hourly rate
                wage = self.batch.hourly_labor_rate
            
            if wage > 0:
                return (self.total_time_minutes / 60) * wage
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
    
    @property
    def requires_scale_selection(self):
        """Check if task requires scale selection before starting"""
        return (self.batch and self.batch.can_be_scaled and 
                not self.selected_scale and self.status == "not_started")
    
    @property
    def requires_made_amount(self):
        """Check if task requires made amount input before completion"""
        return (self.batch and self.batch.variable_yield and 
                not self.made_amount and self.status in ["in_progress", "paused"])
    
    def get_actual_yield(self):
        """Get the actual yield for this task"""
        if self.batch:
            if self.batch.variable_yield and self.made_amount:
                return self.made_amount, self.made_unit
            elif not self.batch.variable_yield and self.scale_factor:
                scaled_yield = self.batch.get_scaled_yield(self.scale_factor)
                return scaled_yield, self.batch.yield_unit
        return None, None

class UtilityCost(Base):
    __tablename__ = "utility_costs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    monthly_cost = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)