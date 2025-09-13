from datetime import date
from sqlalchemy.orm import Session
from ..models import Category, VendorUnit, Vendor, ParUnitName, JanitorialTask

def create_default_categories(db: Session):
    """Create default categories with Unicode emojis if they don't exist"""
    print("Starting category creation process...")
    
    # Define categories with their Unicode emojis and colors
    default_categories = [
        # Ingredients
        ("Cheese", "ingredient", "🧀", "#ffc107"),
        ("Eggs", "ingredient", "🥚", "#ffc107"),
        ("Dairy", "ingredient", "🐄", "#6f42c1"),
        ("Produce", "ingredient", "🥕", "#28a745"),
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
        ("General", "ingredient", "✅", "#28a745"),
        
        # Batches
        ("Sauces", "batch", "🥘", "#dc3545"),
        ("Dressings", "batch", "🫗", "#ffc107"),
        ("Soups", "batch", "🥣", "#fd7e14"),
        ("Stocks & Broths", "batch", "🥘", "#dc3545"),
        ("Dough", "batch", "🍞", "#fd7e14"),
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
        ("Dough", "inventory", "🍞", "#fd7e14"),
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

def create_default_janitorial_tasks(db: Session):
    """Create default janitorial tasks if they don't exist"""
    default_tasks = [
        ("Clean Kitchen Floors", "Sweep and mop all kitchen floor areas", "daily"),
        ("Empty Trash Bins", "Empty all trash bins and replace liners", "daily"),
        ("Sanitize Work Surfaces", "Clean and sanitize all prep surfaces", "daily"),
        ("Deep Clean Equipment", "Thorough cleaning of kitchen equipment", "manual"),
        ("Clean Storage Areas", "Organize and clean storage rooms", "manual"),
    ]
    
    for title, instructions, task_type in default_tasks:
        existing = db.query(JanitorialTask).filter(JanitorialTask.title == title).first()
        if not existing:
            task = JanitorialTask(title=title, instructions=instructions, task_type=task_type)
            db.add(task)
    
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