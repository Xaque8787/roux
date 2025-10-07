from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship, Session
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
import enum

Base = declarative_base()

# Unit conversion dictionaries
WEIGHT_CONVERSIONS = {
    'lb': 1.0,
    'oz': 16.0,
    'g': 453.592,
    'kg': 0.453592
}

VOLUME_CONVERSIONS = {
    'gal': 1.0,
    'qt': 4.0,
    'pt': 8.0,
    'cup': 16.0,
    'fl_oz': 128.0,
    'l': 3.78541,
    'ml': 3785.41
}

BAKING_MEASUREMENTS = {
    'cup': 1.0,
    '3_4_cup': 1.333,
    '2_3_cup': 1.5,
    '1_2_cup': 2.0,
    '1_3_cup': 3.0,
    '1_4_cup': 4.0,
    '1_8_cup': 8.0,
    'tbsp': 16.0,
    'tsp': 48.0
}

def convert_weight(amount, from_unit, to_unit):
    """Convert weight from one unit to another"""
    if from_unit not in WEIGHT_CONVERSIONS or to_unit not in WEIGHT_CONVERSIONS:
        raise ValueError(f"Unsupported weight units: {from_unit} to {to_unit}")
    
    # Convert to pounds first, then to target unit
    pounds = amount / WEIGHT_CONVERSIONS[from_unit]
    return pounds * WEIGHT_CONVERSIONS[to_unit]

def convert_volume(amount, from_unit, to_unit):
    """Convert volume from one unit to another"""
    if from_unit not in VOLUME_CONVERSIONS or to_unit not in VOLUME_CONVERSIONS:
        raise ValueError(f"Unsupported volume units: {from_unit} to {to_unit}")
    
    # Convert to gallons first, then to target unit
    gallons = amount / VOLUME_CONVERSIONS[from_unit]
    return gallons * VOLUME_CONVERSIONS[to_unit]

def convert_baking_measurement(amount, from_unit, to_unit, weight_per_cup, weight_unit):
    """Convert baking measurements using weight conversion"""
    if from_unit not in BAKING_MEASUREMENTS or to_unit not in BAKING_MEASUREMENTS:
        raise ValueError(f"Unsupported baking units: {from_unit} to {to_unit}")
    
    # Convert to cups first
    cups = amount / BAKING_MEASUREMENTS[from_unit]
    
    # Convert to weight
    weight = cups * weight_per_cup
    
    # Convert back to target baking measurement
    target_cups = weight / weight_per_cup
    return target_cups * BAKING_MEASUREMENTS[to_unit]

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    hourly_wage = Column(Float, default=15.0)
    work_schedule = Column(String)  # Comma-separated days
    role = Column(String, default="user")  # admin, manager, user
    is_admin = Column(Boolean, default=False)
    is_user = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)  # ingredient, recipe, batch, dish, inventory
    icon = Column(String)  # Unicode emoji
    color = Column(String, default="#6c757d")  # Hex color code

class Vendor(Base):
    __tablename__ = "vendors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    contact_info = Column(Text)

class VendorUnit(Base):
    __tablename__ = "vendor_units"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)

class ParUnitName(Base):
    __tablename__ = "par_unit_names"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)

class Ingredient(Base):
    __tablename__ = "ingredients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    usage_type = Column(String)  # weight, volume
    category_id = Column(Integer, ForeignKey("categories.id"))
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    vendor_unit_id = Column(Integer, ForeignKey("vendor_units.id"))
    
    # Purchase level information
    purchase_type = Column(String)  # single, case
    purchase_unit_name = Column(String)  # e.g., "Case", "Bag", "Sack"
    purchase_total_cost = Column(Float)
    purchase_weight_volume = Column(Float)  # Total weight/volume purchased
    breakable_case = Column(Boolean, default=False)
    
    # Item level information
    use_item_count_pricing = Column(Boolean, default=False)
    items_per_case = Column(Integer)  # For case purchases
    item_weight_volume = Column(Float)  # Weight/volume per individual item
    net_weight_volume_item = Column(Float)  # Net weight/volume per item
    net_weight_volume_case = Column(Float)  # Net weight/volume per case
    net_unit = Column(String)  # Unit for net weight/volume
    
    # Price per weight/volume fields
    uses_price_per_weight_volume = Column(Boolean, default=False)
    price_per_weight_volume = Column(Float)
    
    # Baking measurements conversion
    has_baking_conversion = Column(Boolean, default=False)
    baking_measurement_unit = Column(String)  # cup, 1_2_cup, etc.
    baking_weight_amount = Column(Float)  # Amount in weight
    baking_weight_unit = Column(String)  # oz, g, lb
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")
    vendor = relationship("Vendor")
    vendor_unit = relationship("VendorUnit")
    
    @property
    def item_cost(self):
        """Calculate cost per individual item"""
        if self.use_item_count_pricing:
            if self.purchase_type == "case" and self.items_per_case:
                return self.purchase_total_cost / self.items_per_case
            else:
                return self.purchase_total_cost
        else:
            # For weight/volume pricing, calculate based on item weight/volume
            if self.net_weight_volume_item and self.purchase_total_cost:
                if self.purchase_type == "case" and self.net_weight_volume_case:
                    return self.purchase_total_cost * (self.net_weight_volume_item / self.net_weight_volume_case)
                else:
                    return self.purchase_total_cost
            return 0
    
    @property
    def total_item_count(self):
        """Get total number of items purchased"""
        if self.purchase_type == "case" and self.items_per_case:
            return self.items_per_case
        else:
            return 1
    
    @property
    def cost_per_item(self):
        """Get cost per individual item"""
        return self.item_cost
    
    def get_available_units(self):
        """Get list of available units for this ingredient"""
        units = []
        
        # If using item count pricing, add item and case units
        if self.use_item_count_pricing:
            units.append('item')
            if self.purchase_type == 'case' and self.items_per_case:
                units.append('case')
            return units
        
        # Add base units based on usage type
        if self.usage_type == 'weight':
            units.extend(list(WEIGHT_CONVERSIONS.keys()))
        elif self.usage_type == 'volume':
            units.extend(list(VOLUME_CONVERSIONS.keys()))
        
        # Add baking measurements if available
        if self.has_baking_conversion:
            units.extend(list(BAKING_MEASUREMENTS.keys()))
        
        return units
    
    def get_cost_per_unit(self, unit):
        """Calculate cost per unit for a given unit"""
        if self.use_item_count_pricing:
            # For item count pricing, handle item and case units
            if unit == 'item':
                return self.cost_per_item
            elif unit == 'case' and self.purchase_type == 'case':
                return self.purchase_total_cost  # Full case cost
            else:
                # Fallback to cost per item for any other unit
                return self.cost_per_item
        
        # Calculate base cost per net unit
        if not self.net_weight_volume_item or not self.purchase_total_cost:
            return 0
        
        # Get total net amount
        if self.purchase_type == "case" and self.net_weight_volume_case:
            total_net = self.net_weight_volume_case
        else:
            total_net = self.net_weight_volume_item
        
        base_cost_per_net_unit = self.purchase_total_cost / total_net
        
        # If requesting the same unit as net unit, return directly
        if unit == self.net_unit:
            return base_cost_per_net_unit
        
        # Handle baking measurements
        if (unit in BAKING_MEASUREMENTS and self.has_baking_conversion and
            self.baking_weight_amount and self.baking_weight_unit):

            # Convert from baking measurement to weight
            if unit in BAKING_MEASUREMENTS:
                # Convert the defined baking measurement to cups first
                cups_per_defined_unit = 1.0 / BAKING_MEASUREMENTS[self.baking_measurement_unit]
                weight_per_cup = self.baking_weight_amount / cups_per_defined_unit

                # Convert requested unit to cups
                cups_per_requested_unit = 1.0 / BAKING_MEASUREMENTS[unit]
                weight_for_requested_unit = weight_per_cup * cups_per_requested_unit

                # Convert weight to net unit if needed
                if self.baking_weight_unit != self.net_unit:
                    if (self.baking_weight_unit in WEIGHT_CONVERSIONS and
                        self.net_unit in WEIGHT_CONVERSIONS):
                        weight_for_requested_unit = convert_weight(
                            weight_for_requested_unit,
                            self.baking_weight_unit,
                            self.net_unit
                        )

                return base_cost_per_net_unit * weight_for_requested_unit
        
        # Handle weight conversions
        if (self.usage_type == 'weight' and 
            self.net_unit in WEIGHT_CONVERSIONS and 
            unit in WEIGHT_CONVERSIONS):
            conversion_factor = convert_weight(1, self.net_unit, unit)
            return base_cost_per_net_unit / conversion_factor
        
        # Handle volume conversions
        if (self.usage_type == 'volume' and 
            self.net_unit in VOLUME_CONVERSIONS and 
            unit in VOLUME_CONVERSIONS):
            conversion_factor = convert_volume(1, self.net_unit, unit)
            return base_cost_per_net_unit / conversion_factor
        
        # If no conversion possible, return base cost
        return base_cost_per_net_unit

class Recipe(Base):
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    instructions = Column(Text)
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    unit = Column(String)
    quantity = Column(Float)

    # Relationships
    recipe = relationship("Recipe")
    ingredient = relationship("Ingredient")

    @property
    def cost(self):
        """Calculate cost for this recipe ingredient"""
        if self.ingredient:
            return self.ingredient.get_cost_per_unit(self.unit) * self.quantity
        return 0

class RecipeBatchPortion(Base):
    __tablename__ = "recipe_batch_portions"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"))
    portion_size = Column(Float)
    portion_unit = Column(String)
    use_recipe_portion = Column(Boolean, default=False)
    recipe_portion_percent = Column(Float)

    # Relationships
    recipe = relationship("Recipe")
    batch = relationship("Batch")

    def get_recipe_cost(self, db: Session):
        """Get recipe cost for this portion"""
        # Calculate total recipe cost including ingredients and batch portions
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == self.batch.recipe_id).all()
        ingredients_cost = sum(ri.cost for ri in recipe_ingredients)

        # Also include batch portions from the recipe
        recipe_batch_portions = db.query(RecipeBatchPortion).filter(RecipeBatchPortion.recipe_id == self.batch.recipe_id).all()
        batch_portions_cost = sum(rbp.get_total_cost(db) for rbp in recipe_batch_portions)

        total_recipe_cost = ingredients_cost + batch_portions_cost

        if self.use_recipe_portion and self.recipe_portion_percent:
            return total_recipe_cost * self.recipe_portion_percent
        else:
            # Calculate based on portion size
            if self.batch.variable_yield:
                return 0

            if self.batch.yield_amount and self.portion_size and self.portion_unit:
                # Check if unit conversion is needed
                if self.portion_unit == self.batch.yield_unit:
                    # Same unit, simple ratio
                    portion_ratio = self.portion_size / self.batch.yield_amount
                    return total_recipe_cost * portion_ratio
                else:
                    # Different units, need to convert
                    # Try to convert portion_size to batch yield_unit
                    try:
                        if self.portion_unit in WEIGHT_CONVERSIONS and self.batch.yield_unit in WEIGHT_CONVERSIONS:
                            converted_portion = convert_weight(self.portion_size, self.portion_unit, self.batch.yield_unit)
                            portion_ratio = converted_portion / self.batch.yield_amount
                            return total_recipe_cost * portion_ratio
                        elif self.portion_unit in VOLUME_CONVERSIONS and self.batch.yield_unit in VOLUME_CONVERSIONS:
                            converted_portion = convert_volume(self.portion_size, self.portion_unit, self.batch.yield_unit)
                            portion_ratio = converted_portion / self.batch.yield_amount
                            return total_recipe_cost * portion_ratio
                    except (ValueError, KeyError):
                        # Conversion failed, fall back to simple ratio
                        portion_ratio = self.portion_size / self.batch.yield_amount
                        return total_recipe_cost * portion_ratio

        return 0

    def get_labor_cost(self, db: Session):
        """Get estimated labor cost for this portion"""
        labor_cost = self.batch.estimated_labor_cost

        if self.use_recipe_portion and self.recipe_portion_percent:
            return labor_cost * self.recipe_portion_percent
        else:
            # Calculate based on portion size
            if self.batch.variable_yield:
                return 0

            if self.batch.yield_amount and self.portion_size and self.portion_unit:
                # Check if unit conversion is needed
                if self.portion_unit == self.batch.yield_unit:
                    # Same unit, simple ratio
                    portion_ratio = self.portion_size / self.batch.yield_amount
                    return labor_cost * portion_ratio
                else:
                    # Different units, need to convert
                    try:
                        if self.portion_unit in WEIGHT_CONVERSIONS and self.batch.yield_unit in WEIGHT_CONVERSIONS:
                            converted_portion = convert_weight(self.portion_size, self.portion_unit, self.batch.yield_unit)
                            portion_ratio = converted_portion / self.batch.yield_amount
                            return labor_cost * portion_ratio
                        elif self.portion_unit in VOLUME_CONVERSIONS and self.batch.yield_unit in VOLUME_CONVERSIONS:
                            converted_portion = convert_volume(self.portion_size, self.portion_unit, self.batch.yield_unit)
                            portion_ratio = converted_portion / self.batch.yield_amount
                            return labor_cost * portion_ratio
                    except (ValueError, KeyError):
                        # Conversion failed, fall back to simple ratio
                        portion_ratio = self.portion_size / self.batch.yield_amount
                        return labor_cost * portion_ratio

        return 0

    def get_total_cost(self, db: Session):
        """Get total cost (recipe + labor)"""
        return self.get_recipe_cost(db) + self.get_labor_cost(db)

class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    variable_yield = Column(Boolean, default=False)
    yield_amount = Column(Float)
    yield_unit = Column(String)
    estimated_labor_minutes = Column(Integer)
    hourly_labor_rate = Column(Float, default=16.75)
    can_be_scaled = Column(Boolean, default=False)
    scale_double = Column(Boolean, default=False)
    scale_half = Column(Boolean, default=False)
    scale_quarter = Column(Boolean, default=False)
    scale_eighth = Column(Boolean, default=False)
    scale_sixteenth = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    recipe = relationship("Recipe")
    category = relationship("Category")
    
    @property
    def estimated_labor_cost(self):
        """Calculate estimated labor cost"""
        return (self.estimated_labor_minutes / 60) * self.hourly_labor_rate
    
    def get_available_scales(self):
        """Get available scaling options for this batch"""
        scales = [('full', 1.0, 'Full Batch')]
        
        if self.can_be_scaled:
            if self.scale_double:
                scales.append(('double', 2.0, 'Double Batch (2x)'))
            if self.scale_half:
                scales.append(('half', 0.5, 'Half Batch (1/2)'))
            if self.scale_quarter:
                scales.append(('quarter', 0.25, 'Quarter Batch (1/4)'))
            if self.scale_eighth:
                scales.append(('eighth', 0.125, 'Eighth Batch (1/8)'))
            if self.scale_sixteenth:
                scales.append(('sixteenth', 0.0625, 'Sixteenth Batch (1/16)'))
        
        return scales
    
    def get_scaled_yield(self, scale_factor):
        """Get yield amount for a given scale factor"""
        if self.variable_yield:
            return "Variable"
        return self.yield_amount * scale_factor if self.yield_amount else 0
    
    def get_actual_labor_cost(self, db: Session):
        """Get most recent actual labor cost from completed tasks"""
        from sqlalchemy import or_, and_
        
        # Find most recent completed task for this batch
        completed_task = db.query(Task).filter(
            or_(
                Task.batch_id == self.id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.id)
                )
            ),
            Task.finished_at.isnot(None)
        ).order_by(Task.finished_at.desc()).first()
        
        if completed_task:
            return completed_task.labor_cost
        
        return self.estimated_labor_cost

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

class DishBatchPortion(Base):
    __tablename__ = "dish_batch_portions"
    
    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"))
    portion_size = Column(Float)
    portion_unit = Column(String)
    use_recipe_portion = Column(Boolean, default=False)
    recipe_portion_percent = Column(Float)  # Decimal (0.25 = 25%)
    
    # Relationships
    dish = relationship("Dish")
    batch = relationship("Batch")
    
    def get_recipe_cost(self, db: Session):
        """Get recipe cost for this portion"""
        recipe_ingredients = db.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == self.batch.recipe_id).all()
        total_recipe_cost = sum(ri.cost for ri in recipe_ingredients)
        
        if self.use_recipe_portion and self.recipe_portion_percent:
            return total_recipe_cost * self.recipe_portion_percent
        else:
            # Calculate based on portion size
            if self.batch.variable_yield:
                return 0  # Cannot calculate for variable yield without recipe portion
            
            if self.batch.yield_amount and self.portion_size:
                portion_ratio = self.portion_size / self.batch.yield_amount
                return total_recipe_cost * portion_ratio
        
        return 0
    
    def get_labor_cost(self, db: Session, cost_type='estimated'):
        """Get labor cost for this portion"""
        if cost_type == 'estimated':
            labor_cost = self.batch.estimated_labor_cost
        elif cost_type == 'actual':
            labor_cost = self.batch.get_actual_labor_cost(db)
        elif cost_type == 'week_avg':
            labor_cost = self.get_week_avg_labor_cost(db)
        elif cost_type == 'month_avg':
            labor_cost = self.get_month_avg_labor_cost(db)
        elif cost_type == 'all_time_avg':
            labor_cost = self.get_all_time_avg_labor_cost(db)
        else:
            labor_cost = self.batch.estimated_labor_cost
        
        if self.use_recipe_portion and self.recipe_portion_percent:
            return labor_cost * self.recipe_portion_percent
        else:
            # Calculate based on portion size
            if self.batch.variable_yield:
                return 0  # Cannot calculate for variable yield without recipe portion
            
            if self.batch.yield_amount and self.portion_size:
                portion_ratio = self.portion_size / self.batch.yield_amount
                return labor_cost * portion_ratio
        
        return 0
    
    def get_expected_cost(self, db: Session):
        """Get expected total cost (recipe + estimated labor)"""
        return self.get_recipe_cost(db) + self.get_labor_cost(db, 'estimated')
    
    def get_actual_cost(self, db: Session):
        """Get actual total cost (recipe + actual labor)"""
        return self.get_recipe_cost(db) + self.get_labor_cost(db, 'actual')
    
    def get_actual_cost_week_avg(self, db: Session):
        """Get actual total cost with week average labor"""
        return self.get_recipe_cost(db) + self.get_labor_cost(db, 'week_avg')
    
    def get_actual_cost_month_avg(self, db: Session):
        """Get actual total cost with month average labor"""
        return self.get_recipe_cost(db) + self.get_labor_cost(db, 'month_avg')
    
    def get_week_avg_labor_cost(self, db: Session):
        """Get week average labor cost"""
        from datetime import timedelta
        from sqlalchemy import or_, and_
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        week_tasks = db.query(Task).filter(
            or_(
                Task.batch_id == self.batch_id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.batch_id)
                )
            ),
            Task.finished_at.isnot(None),
            Task.finished_at >= week_ago
        ).all()
        
        if week_tasks:
            return sum(t.labor_cost for t in week_tasks) / len(week_tasks)
        
        return self.batch.estimated_labor_cost
    
    def get_month_avg_labor_cost(self, db: Session):
        """Get month average labor cost"""
        from datetime import timedelta
        from sqlalchemy import or_, and_
        
        month_ago = datetime.utcnow() - timedelta(days=30)
        
        month_tasks = db.query(Task).filter(
            or_(
                Task.batch_id == self.batch_id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.batch_id)
                )
            ),
            Task.finished_at.isnot(None),
            Task.finished_at >= month_ago
        ).all()
        
        if month_tasks:
            return sum(t.labor_cost for t in month_tasks) / len(month_tasks)
        
        return self.batch.estimated_labor_cost
    
    def get_all_time_avg_labor_cost(self, db: Session):
        """Get all time average labor cost"""
        from sqlalchemy import or_, and_
        
        all_tasks = db.query(Task).filter(
            or_(
                Task.batch_id == self.batch_id,
                and_(
                    Task.inventory_item_id.isnot(None),
                    Task.inventory_item.has(InventoryItem.batch_id == self.batch_id)
                )
            ),
            Task.finished_at.isnot(None)
        ).all()
        
        if all_tasks:
            return sum(t.labor_cost for t in all_tasks) / len(all_tasks)
        
        return self.batch.estimated_labor_cost

class DishIngredientPortion(Base):
    __tablename__ = "dish_ingredient_portions"
    
    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    quantity = Column(Float)
    unit = Column(String)
    
    # Relationships
    dish = relationship("Dish")
    ingredient = relationship("Ingredient")
    
    @property
    def cost(self):
        """Calculate cost for this ingredient portion"""
        if self.ingredient:
            return self.ingredient.get_cost_per_unit(self.unit) * self.quantity
        return 0

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    par_unit_name_id = Column(Integer, ForeignKey("par_unit_names.id"))
    par_level = Column(Float, default=0.0)
    batch_id = Column(Integer, ForeignKey("batches.id"))
    par_unit_equals_type = Column(String)  # auto, par_unit_itself, custom
    par_unit_equals_amount = Column(Float)
    par_unit_equals_unit = Column(String)
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    par_unit_name = relationship("ParUnitName")
    batch = relationship("Batch")
    category = relationship("Category")
    
    @property
    def par_unit_equals_calculated(self):
        """Calculate the par unit equals value based on type"""
        if self.par_unit_equals_type == "par_unit_itself":
            return 1.0
        elif self.par_unit_equals_type == "custom" and self.par_unit_equals_amount:
            return self.par_unit_equals_amount
        elif self.par_unit_equals_type == "auto" and self.batch and not self.batch.variable_yield:
            if self.batch.yield_amount and self.par_level > 0:
                return self.batch.yield_amount / self.par_level
        return None
    
    def convert_to_par_units(self, amount, unit):
        """Convert an amount in a given unit to par units"""
        if not self.par_unit_name:
            return amount
        
        par_unit_equals = self.par_unit_equals_calculated
        if not par_unit_equals:
            return amount
        
        # If the unit is already the par unit name, return as-is
        if unit == self.par_unit_name.name:
            return amount
        
        # If we have a custom conversion, use it
        if (self.par_unit_equals_type == "custom" and 
            self.par_unit_equals_unit and 
            unit == self.par_unit_equals_unit):
            return amount / par_unit_equals
        
        # For auto conversion with batch yield unit
        if (self.par_unit_equals_type == "auto" and 
            self.batch and 
            unit == self.batch.yield_unit):
            return amount / par_unit_equals
        
        # Default: assume 1:1 conversion
        return amount

class InventoryDay(Base):
    __tablename__ = "inventory_days"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True)
    employees_working = Column(String)  # Comma-separated employee IDs
    global_notes = Column(Text)
    finalized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class InventoryDayItem(Base):
    __tablename__ = "inventory_day_items"
    
    id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    quantity = Column(Float, default=0.0)
    override_create_task = Column(Boolean, default=False)
    override_no_task = Column(Boolean, default=False)
    
    # Relationships
    day = relationship("InventoryDay")
    inventory_item = relationship("InventoryItem")

class JanitorialTask(Base):
    __tablename__ = "janitorial_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    instructions = Column(Text)
    task_type = Column(String)  # daily, manual
    category_id = Column(Integer, ForeignKey("categories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category")

class JanitorialTaskDay(Base):
    __tablename__ = "janitorial_task_days"
    
    id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    janitorial_task_id = Column(Integer, ForeignKey("janitorial_tasks.id"))
    include_task = Column(Boolean, default=False)
    
    # Relationships
    day = relationship("InventoryDay")
    janitorial_task = relationship("JanitorialTask")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("inventory_days.id"))
    assigned_to_id = Column(Integer, ForeignKey("users.id"))
    assigned_employee_ids = Column(String)  # Comma-separated employee IDs for multi-assignment
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    batch_id = Column(Integer, ForeignKey("batches.id"))
    janitorial_task_id = Column(Integer, ForeignKey("janitorial_tasks.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    description = Column(String)
    auto_generated = Column(Boolean, default=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    paused_at = Column(DateTime)
    is_paused = Column(Boolean, default=False)
    total_pause_time = Column(Integer, default=0)  # Total pause time in seconds
    notes = Column(Text)
    selected_scale = Column(String)  # full, double, half, quarter, eighth, sixteenth
    scale_factor = Column(Float, default=1.0)
    made_amount = Column(Float)
    made_unit = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    day = relationship("InventoryDay")
    assigned_to = relationship("User")
    inventory_item = relationship("InventoryItem")
    batch = relationship("Batch")
    janitorial_task = relationship("JanitorialTask")
    category = relationship("Category")
    
    @property
    def status(self):
        """Get current task status"""
        if self.finished_at:
            return "completed"
        elif self.is_paused:
            return "paused"
        elif self.started_at:
            return "in_progress"
        else:
            return "not_started"
    
    @property
    def total_time_minutes(self):
        """Calculate total time in minutes"""
        if not self.started_at:
            return 0
        
        end_time = self.finished_at or datetime.utcnow()
        if self.is_paused and self.paused_at:
            end_time = self.paused_at
        
        total_seconds = (end_time - self.started_at).total_seconds()
        total_seconds -= self.total_pause_time
        
        return max(0, int(total_seconds / 60))
    
    @property
    def labor_cost(self):
        """Calculate labor cost based on time and highest wage of assigned employees"""
        if not self.finished_at or not self.assigned_to:
            return 0
        
        # Get highest wage among assigned employees
        highest_wage = self.assigned_to.hourly_wage
        
        if self.assigned_employee_ids:
            # Parse employee IDs and get highest wage
            try:
                employee_ids = [int(id.strip()) for id in self.assigned_employee_ids.split(',') if id.strip()]
                # We need to get a database session to query employees
                # This will be handled by passing the session from the calling code
                # For now, use the assigned_to wage as fallback
                pass
            except (ValueError, AttributeError):
                pass
        
        return (self.total_time_minutes / 60) * highest_wage
    
    @property
    def requires_made_amount(self):
        """Check if this task requires entering a made amount"""
        # Variable yield batches always require made amount
        if self.batch and self.batch.variable_yield:
            return True
        
        # Inventory items with par unit settings require made amount ONLY if:
        # 1. They don't have a linked batch (manual restocking), OR
        # 2. They have a linked batch with variable yield
        if (self.inventory_item and 
            self.inventory_item.par_unit_name and 
            self.inventory_item.par_unit_equals_type):
            
            # If inventory item has a linked batch
            if self.inventory_item.batch:
                # Only require input if the batch has variable yield
                return self.inventory_item.batch.variable_yield
            else:
                # No linked batch = manual restocking, require input
                return True
        
        return False

class UtilityCost(Base):
    __tablename__ = "utility_costs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    monthly_cost = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    @property
    def daily_cost(self):
        """Calculate daily cost (monthly / 30)"""
        return self.monthly_cost / 30