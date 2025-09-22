from datetime import date
from sqlalchemy.orm import Session
from ..models import Category, VendorUnit, Vendor, ParUnitName, JanitorialTask
import re

def create_default_categories(db: Session):
    """Create default categories with Unicode emojis if they don't exist"""
    print("Starting category creation process...")
    
    # Define categories with their Unicode emojis and colors
    default_categories = [
        # Ingredients
        ("Cheese", "ingredient", "🧀", "#ffc107"),
        ("Eggs", "ingredient", "🥚", "#ffc107"),
        ("Dairy", "ingredient", "🐄", "#6f42c1"),
        ("Produce", "ingredient", "🌿", "#28a745"),
        ("Meat & Poultry", "ingredient", "🍗", "#dc3545"),
        ("Seafood", "ingredient", "🐟", "#17a2b8"),
        ("Soups", "ingredient", "🥣", "#fd7e14"),
        ("Sauces", "ingredient", "🥘", "#dc3545"),
        ("Dry Goods", "ingredient", "🌾", "#6c757d"),
        ("Canned Goods", "ingredient", "🥫", "#6c757d"),
        ("Frozen", "ingredient", "❄️", "#17a2b8"),
        ("Dressings", "ingredient", "🫗", "#ffc107"),
        ("Baking Supplies", "ingredient", "🍞", "#fd7e14"),
        ("Oils & Fats", "ingredient", "🛢️", "#6c757d"),
        ("Beverages", "ingredient", "🥤", "#17a2b8"),
        ("Spices & Seasoning", "ingredient", "🌶️", "#dc3545"),
        ("Cleaning & Non-Food", "ingredient", "🧼", "#6c757d"),
        ("Paper Goods", "ingredient", "📦", "#6c757d"),
        ("Condiments", "ingredient", "🌭", "#dc3545"),
        ("General", "ingredient", "✅", "#28a745"),
        
        # Batches
        ("Sauces", "batch", "🥘", "#dc3545"),
        ("Dressings", "batch", "🫗", "#ffc107"),
        ("Soups", "batch", "🥣", "#fd7e14"),
        ("Stocks & Broths", "batch", "🥘", "#dc3545"),
        ("Dough & Bread", "batch", "🍞", "#fd7e14"),
        ("Marinades", "batch", "🫙", "#6f42c1"),
        ("Produce", "batch", "🌿", "#28a745"),
        ("Cheese", "batch", "🧀", "#ffc107"),
        ("Eggs", "batch", "🥚", "#ffc107"),
        ("Dairy", "batch", "🐄", "#6f42c1"),
        ("Protein", "batch", "🍗", "#dc3545"),
        ("Thaw/Defrost", "batch", "🧊", "#17a2b8"),
        ("Frozen Prep", "batch", "❄️", "#17a2b8"),
        ("Spreads & Dips", "batch", "🧈", "#ffc107"),
        ("Dessert", "batch", "🍨", "#fd7e14"),
        ("Restock/Rotate", "batch", "🔄", "#6c757d"),
        ("Manual", "batch", "✋", "#6c757d"),
        ("Specials", "batch", "⭐", "#ffc107"),
        ("Misc Tasks", "batch", "✅", "#28a745"),
        
        # Inventory (same as batches)
        ("Sauces", "inventory", "🥘", "#dc3545"),
        ("Dressings", "inventory", "🫗", "#ffc107"),
        ("Soups", "inventory", "🥣", "#fd7e14"),
        ("Stocks & Broths", "inventory", "🥘", "#dc3545"),
        ("Dough & Bread", "inventory", "🍞", "#fd7e14"),
        ("Marinades", "inventory", "🫙", "#6f42c1"),
        ("Produce", "inventory", "🌿", "#28a745"),
        ("Cheese", "inventory", "🧀", "#ffc107"),
        ("Eggs", "inventory", "🥚", "#ffc107"),
        ("Dairy", "inventory", "🐄", "#6f42c1"),
        ("Protein", "inventory", "🍗", "#dc3545"),
        ("Thaw/Defrost", "inventory", "🧊", "#17a2b8"),
        ("Frozen Prep", "inventory", "❄️", "#17a2b8"),
        ("Spreads & Dips", "inventory", "🧈", "#ffc107"),
        ("Dessert", "inventory", "🍨", "#fd7e14"),
        ("Restock/Rotate", "inventory", "🔄", "#6c757d"),
        ("Manual", "inventory", "✋", "#6c757d"),
        ("Specials", "inventory", "⭐", "#ffc107"),
        ("Misc Tasks", "inventory", "✅", "#28a745"),
        
        # Recipes (same as batches and inventory)
        ("Sauces", "recipe", "🥘", "#dc3545"),
        ("Dressings", "recipe", "🫗", "#ffc107"),
        ("Soups", "recipe", "🥣", "#fd7e14"),
        ("Stocks & Broths", "recipe", "🥘", "#dc3545"),
        ("Dough & Bread", "recipe", "🍞", "#fd7e14"),
        ("Marinades", "recipe", "🫙", "#6f42c1"),
        ("Produce", "recipe", "🌿", "#28a745"),
        ("Cheese", "recipe", "🧀", "#ffc107"),
        ("Eggs", "recipe", "🥚", "#ffc107"),
        ("Dairy", "recipe", "🐄", "#6f42c1"),
        ("Protein", "recipe", "🍗", "#dc3545"),
        ("Thaw/Defrost", "recipe", "🧊", "#17a2b8"),
        ("Frozen Prep", "recipe", "❄️", "#17a2b8"),
        ("Spreads & Dips", "recipe", "🧈", "#ffc107"),
        ("Dessert", "recipe", "🍨", "#fd7e14"),
        ("Restock/Rotate", "recipe", "🔄", "#6c757d"),
        ("Manual", "recipe", "✋", "#6c757d"),
        ("Specials", "recipe", "⭐", "#ffc107"),
        ("Misc Tasks", "recipe", "✅", "#28a745"),
        
        # Dishes
        ("Appetizers", "dish", "🍴", "#6f42c1"),
        ("Salads", "dish", "🌱", "#28a745"),
        ("Sandwiches", "dish", "🍔", "#fd7e14"),
        ("Entrées", "dish", "🍽️", "#dc3545"),
        ("Sides", "dish", "🍲", "#ffc107"),
        ("Soups", "dish", "🥣", "#fd7e14"),
        ("Desserts", "dish", "🍨", "#fd7e14"),
        ("Beverages", "dish", "🍷", "#6f42c1"),
        ("Specials", "dish", "⭐", "#ffc107"),
    ]
    
    # Check for existing categories to avoid duplicates
    existing_categories = {}
    for category in db.query(Category).all():
        key = (category.name, category.type)
        existing_categories[key] = True
    
    created_count = 0
    for name, cat_type, icon, color in default_categories:
        key = (name, cat_type)
        if key not in existing_categories:
            print(f"Creating category: {name} ({cat_type}) with icon {icon}")
            category = Category(name=name, type=cat_type, icon=icon, color=color)
            db.add(category)
            existing_categories[key] = True
            created_count += 1
    
    try:
        db.commit()
        print(f"✅ Category creation completed successfully! Created {created_count} new categories.")
        
        # Verify categories were created
        total_categories = db.query(Category).count()
        print(f"📊 Total categories in database: {total_categories}")
        
        # Show breakdown by type
        for cat_type in ['ingredient', 'batch', 'inventory', 'dish']:
            count = db.query(Category).filter(Category.type == cat_type).count()
            print(f"   {cat_type}: {count} categories")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating categories: {e}")
        import traceback
        traceback.print_exc()
        raise

def create_default_vendor_units(db: Session):
    """Create default vendor units if they don't exist"""
    default_units = [
        ("lb", "Pounds"),
        ("oz", "Ounces"),
        ("g", "Grams"),
        ("kg", "Kilograms"),
        ("gal", "Gallons"),
        ("qt", "Quarts"),
        ("pt", "Pints"),
        ("cup", "Cups"),
        ("fl_oz", "Fluid Ounces"),
        ("l", "Liters"),
        ("ml", "Milliliters"),
        ("each", "Each/Individual"),
        ("dozen", "Dozen"),
        ("case", "Case"),
    ]
    
    for name, description in default_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        pass

def create_default_vendors(db: Session):
    """Create default vendors if they don't exist"""
    default_vendors = [
        ("Local Supplier", "Local food supplier"),
        ("Wholesale Market", "Wholesale food market"),
        ("Specialty Vendor", "Specialty ingredient vendor"),
    ]
    
    for name, contact_info in default_vendors:
        existing = db.query(Vendor).filter(Vendor.name == name).first()
        if not existing:
            vendor = Vendor(name=name, contact_info=contact_info)
            db.add(vendor)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        pass

def create_default_par_unit_names(db: Session):
    """Create default par unit names if they don't exist"""
    default_par_units = [
        "Tub",
        "Container",
        "Case",
        "Bag",
        "Box",
        "Pan",
        "Sheet",
        "Batch",
        "Portion",
        "Unit"
    ]
    
    for name in default_par_units:
        existing = db.query(ParUnitName).filter(ParUnitName.name == name).first()
        if not existing:
            par_unit = ParUnitName(name=name)
            db.add(par_unit)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        pass


def get_today_date():
    """Get today's date as string"""
    return date.today().isoformat()

def get_category_emoji(category):
    """Get emoji for a category, with fallback"""
    if category and category.icon:
        return category.icon
    return "🔘"  # Fallback emoji

def get_task_emoji(task):
    """Get emoji for a task based on priority rules"""
    # Janitorial tasks always use broom emoji
    if hasattr(task, 'janitorial_task_id') and task.janitorial_task_id:
        return "🧹"
    
    # For inventory tasks, use inventory item category first
    if hasattr(task, 'inventory_item') and task.inventory_item and task.inventory_item.category:
        return get_category_emoji(task.inventory_item.category)
    
    # Fallback to batch category if inventory item has no category but has batch
    if (hasattr(task, 'inventory_item') and task.inventory_item and 
        task.inventory_item.batch and task.inventory_item.batch.category):
        return get_category_emoji(task.inventory_item.batch.category)
    
    # For direct batch tasks, use batch category
    if hasattr(task, 'batch') and task.batch and task.batch.category:
        return get_category_emoji(task.batch.category)
    
    # For manual tasks with category
    if hasattr(task, 'category') and task.category:
        return get_category_emoji(task.category)
    
    # Final fallback
    return "🔘"

def generate_task_identifier(task_type: str, name: str, is_manual: bool = False) -> str:
    """Generate a clean, URL-safe task identifier"""
    # Clean the name: lowercase, replace spaces with underscores, strip special chars
    clean_name = name.lower()
    clean_name = clean_name.replace(' ', '_')
    clean_name = clean_name.replace('-', '_')
    clean_name = re.sub(r'[^a-z0-9_]', '', clean_name)
    
    # Remove multiple consecutive underscores
    clean_name = re.sub(r'_+', '_', clean_name)
    
    # Remove leading/trailing underscores
    clean_name = clean_name.strip('_')
    
    # Ensure we have something
    if not clean_name:
        clean_name = 'unnamed_task'
    
    # Add suffix based on type
    if task_type == "inventory":
        return f"{clean_name}_manual" if is_manual else clean_name
    elif task_type == "janitorial":
        return clean_name
    else:
        return f"{clean_name}_manual"

def get_task_by_identifier(db: Session, day_date: str, task_identifier: str):
    """Get a task by its identifier within a specific day"""
    from datetime import datetime
    from ..models import InventoryDay, Task, InventoryItem, JanitorialTask
    
    # Convert date string to date object
    try:
        date_obj = datetime.strptime(day_date, '%Y-%m-%d').date()
    except ValueError:
        return None
    
    # Get the inventory day
    inventory_day = db.query(InventoryDay).filter(InventoryDay.date == date_obj).first()
    if not inventory_day:
        return None
    
    # Try to find task by identifier
    if task_identifier.endswith('_manual'):
        # Manual task - could be inventory-based or standalone
        base_name = task_identifier[:-7]  # Remove '_manual' suffix
        
        # First try to find by inventory item name
        inventory_item = db.query(InventoryItem).filter(
            InventoryItem.name.ilike(base_name.replace('_', ' '))
        ).first()
        
        if inventory_item:
            task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.inventory_item_id == inventory_item.id,
                Task.auto_generated == False
            ).first()
            if task:
                return task
        
        # If not found by inventory item, try by description pattern
        task = db.query(Task).filter(
            Task.day_id == inventory_day.id,
            Task.auto_generated == False,
            Task.description.ilike(f"%{base_name.replace('_', ' ')}%")
        ).first()
        
        return task
    
    else:
        # Regular inventory task or janitorial task
        # First try inventory item
        inventory_item = db.query(InventoryItem).filter(
            InventoryItem.name.ilike(task_identifier.replace('_', ' '))
        ).first()
        
        if inventory_item:
            task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.inventory_item_id == inventory_item.id,
                Task.auto_generated == True
            ).first()
            if task:
                return task
        
        # Try janitorial task
        janitorial_task = db.query(JanitorialTask).filter(
            JanitorialTask.title.ilike(task_identifier.replace('_', ' '))
        ).first()
        
        if janitorial_task:
            task = db.query(Task).filter(
                Task.day_id == inventory_day.id,
                Task.janitorial_task_id == janitorial_task.id
            ).first()
            return task
    
    return None

def get_inventory_day_by_date(db: Session, day_date: str):
    """Get inventory day by date string"""
    from datetime import datetime
    from ..models import InventoryDay
    
    try:
        date_obj = datetime.strptime(day_date, '%Y-%m-%d').date()
        return db.query(InventoryDay).filter(InventoryDay.date == date_obj).first()
    except ValueError:
        return None