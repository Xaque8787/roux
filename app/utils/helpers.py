from datetime import date
from sqlalchemy.orm import Session
from ..models import Category, VendorUnit, Vendor, ParUnitName, JanitorialTask

def create_default_categories(db: Session):
    """Create default categories with icons and colors if they don't exist"""
    default_categories = [
        # Ingredients (green theme - #28a745)
        ("Dairy", "ingredient", "fa-cheese", "#28a745"),
        ("Produce", "ingredient", "fa-carrot", "#28a745"),
        ("Meat & Poultry", "ingredient", "fa-drumstick-bite", "#28a745"),
        ("Seafood", "ingredient", "fa-fish", "#28a745"),
        ("Dry Goods", "ingredient", "fa-wheat-awn", "#28a745"),
        ("Canned Goods", "ingredient", "fa-can-food", "#28a745"),
        ("Frozen", "ingredient", "fa-snowflake", "#28a745"),
        ("Dressings", "ingredient", "fa-bottle-droplet", "#28a745"),
        ("Baking Supplies", "ingredient", "fa-bread-slice", "#28a745"),
        ("Oils & Fats", "ingredient", "fa-oil-can", "#28a745"),
        ("Beverages", "ingredient", "fa-glass", "#28a745"),
        ("Spices & Seasoning", "ingredient", "fa-pepper-hot", "#28a745"),
        ("Cleaning & Non-Food", "ingredient", "fa-soap", "#28a745"),
        ("General", "ingredient", "fa-list-check", "#28a745"),
        
        # Recipes (light blue theme - #17a2b8)
        # No predefined recipe categories as requested
        
        # Batches (yellow theme - #ffc107)
        ("Sauces", "batch", "fa-pot-food", "#ffc107"),
        ("Dressings", "batch", "fa-bottle-droplet", "#ffc107"),
        ("Soups", "batch", "fa-bowl-rice", "#ffc107"),
        ("Stocks & Broths", "batch", "fa-pot-food", "#ffc107"),
        ("Dough", "batch", "fa-bread-slice", "#ffc107"),
        ("Marinades", "batch", "fa-jar", "#ffc107"),
        ("Produce", "batch", "fa-leaf", "#ffc107"),
        ("Dairy", "batch", "fa-cheese", "#ffc107"),
        ("Protein", "batch", "fa-drumstick-bite", "#ffc107"),
        ("Frozen/Thaw", "batch", "fa-snowflake", "#ffc107"),
        ("Spreads & Dips", "batch", "fa-bread-slice", "#ffc107"),
        ("Dessert", "batch", "fa-ice-cream", "#ffc107"),
        ("Restock/Rotate", "batch", "fa-rotate", "#ffc107"),
        ("Manual", "batch", "fa-hand", "#ffc107"),
        ("Specials", "batch", "fa-star", "#ffc107"),
        ("Misc Tasks", "batch", "fa-list-check", "#ffc107"),
        
        # Inventory (grey theme - #6c757d) - same as batches for task types
        ("Sauces", "inventory", "fa-pot-food", "#6c757d"),
        ("Dressings", "inventory", "fa-bottle-droplet", "#6c757d"),
        ("Soups", "inventory", "fa-bowl-rice", "#6c757d"),
        ("Stocks & Broths", "inventory", "fa-pot-food", "#6c757d"),
        ("Dough", "inventory", "fa-bread-slice", "#6c757d"),
        ("Marinades", "inventory", "fa-jar", "#6c757d"),
        ("Produce", "inventory", "fa-leaf", "#6c757d"),
        ("Dairy", "inventory", "fa-cheese", "#6c757d"),
        ("Protein", "inventory", "fa-drumstick-bite", "#6c757d"),
        ("Frozen/Thaw", "inventory", "fa-snowflake", "#6c757d"),
        ("Spreads & Dips", "inventory", "fa-bread-slice", "#6c757d"),
        ("Dessert", "inventory", "fa-ice-cream", "#6c757d"),
        ("Restock/Rotate", "inventory", "fa-rotate", "#6c757d"),
        ("Manual", "inventory", "fa-hand", "#6c757d"),
        ("Specials", "inventory", "fa-star", "#6c757d"),
        ("Misc Tasks", "inventory", "fa-list-check", "#6c757d"),
        
        # Dishes (dark blue theme - #0d6efd)
        ("Appetizers", "dish", "fa-utensils", "#0d6efd"),
        ("Salads", "dish", "fa-seedling", "#0d6efd"),
        ("Sandwiches", "dish", "fa-burger", "#0d6efd"),
        ("Entrées", "dish", "fa-plate-wheat", "#0d6efd"),
        ("Sides", "dish", "fa-bowl-food", "#0d6efd"),
        ("Soups", "dish", "fa-mug-hot", "#0d6efd"),
        ("Desserts", "dish", "fa-ice-cream", "#0d6efd"),
        ("Beverages", "dish", "fa-wine-glass", "#0d6efd"),
        ("Specials", "dish", "fa-star", "#0d6efd"),
    ]
    
    print("Starting category creation...")
    created_count = 0
    
    # Check for existing categories
    existing_categories = {}
    for category in db.query(Category).all():
        key = (category.name, category.type)
        existing_categories[key] = True
    
    for name, cat_type, icon, color in default_categories:
        key = (name, cat_type)
        if key not in existing_categories:
            print(f"Creating category: {name} ({cat_type}) with icon {icon}")
            category = Category(name=name, type=cat_type, icon=icon, color=color)
            db.add(category)
            existing_categories[key] = True
            created_count += 1
        else:
            print(f"Category already exists: {name} ({cat_type})")
    
    try:
        db.commit()
        print(f"Category creation completed. Created {created_count} new categories.")
    except Exception as e:
        print(f"Error creating categories: {e}")
        raise e

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
    
    print("Starting vendor unit creation...")
    created_count = 0
    
    for name, description in default_units:
        existing = db.query(VendorUnit).filter(VendorUnit.name == name).first()
        if not existing:
            print(f"Creating vendor unit: {name}")
            unit = VendorUnit(name=name, description=description)
            db.add(unit)
            created_count += 1
        else:
            print(f"Vendor unit already exists: {name}")
    
    try:
        db.commit()
        print(f"Vendor unit creation completed. Created {created_count} new units.")
    except Exception as e:
        print(f"Error creating vendor units: {e}")
        raise e

def create_default_vendors(db: Session):
    """Create default vendors if they don't exist"""
    default_vendors = [
        ("Local Supplier", "Local food supplier"),
        ("Wholesale Market", "Wholesale food market"),
        ("Specialty Vendor", "Specialty ingredient vendor"),
    ]
    
    print("Starting vendor creation...")
    created_count = 0
    
    for name, contact_info in default_vendors:
        existing = db.query(Vendor).filter(Vendor.name == name).first()
        if not existing:
            print(f"Creating vendor: {name}")
            vendor = Vendor(name=name, contact_info=contact_info)
            db.add(vendor)
            created_count += 1
        else:
            print(f"Vendor already exists: {name}")
    
    try:
        db.commit()
        print(f"Vendor creation completed. Created {created_count} new vendors.")
    except Exception as e:
        print(f"Error creating vendors: {e}")
        raise e

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
    
    print("Starting par unit name creation...")
    created_count = 0
    
    for name in default_par_units:
        existing = db.query(ParUnitName).filter(ParUnitName.name == name).first()
        if not existing:
            print(f"Creating par unit name: {name}")
            par_unit = ParUnitName(name=name)
            db.add(par_unit)
            created_count += 1
        else:
            print(f"Par unit name already exists: {name}")
    
    try:
        db.commit()
        print(f"Par unit name creation completed. Created {created_count} new units.")
    except Exception as e:
        print(f"Error creating par unit names: {e}")
        raise e

def create_default_janitorial_tasks(db: Session):
    """Create default janitorial tasks if they don't exist"""
    default_tasks = [
        ("Clean Kitchen Floors", "Sweep and mop all kitchen floor areas", "daily"),
        ("Empty Trash Bins", "Empty all trash bins and replace liners", "daily"),
        ("Sanitize Work Surfaces", "Clean and sanitize all prep surfaces", "daily"),
        ("Deep Clean Equipment", "Thorough cleaning of kitchen equipment", "manual"),
        ("Clean Storage Areas", "Organize and clean storage rooms", "manual"),
    ]
    
    print("Starting janitorial task creation...")
    created_count = 0
    
    for title, instructions, task_type in default_tasks:
        existing = db.query(JanitorialTask).filter(JanitorialTask.title == title).first()
        if not existing:
            print(f"Creating janitorial task: {title}")
            task = JanitorialTask(title=title, instructions=instructions, task_type=task_type)
            db.add(task)
            created_count += 1
        else:
            print(f"Janitorial task already exists: {title}")
    
    try:
        db.commit()
        print(f"Janitorial task creation completed. Created {created_count} new tasks.")
    except Exception as e:
        db.rollback()
        print(f"Error creating janitorial tasks: {e}")

def get_today_date():
    return date.today().isoformat()