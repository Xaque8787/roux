from datetime import date
from sqlalchemy.orm import Session
from ..models import Category, VendorUnit, Vendor, ParUnitName

def create_default_categories(db: Session):
    """Create default categories if they don't exist"""
    print("Starting category creation...")
    
    default_categories = [
        # Ingredient categories
        ("Dairy", "ingredient"),
        ("Produce", "ingredient"),
        ("Meat & Poultry", "ingredient"),
        ("Seafood", "ingredient"),
        ("Dry Goods", "ingredient"),
        ("Canned Goods", "ingredient"),
        ("Frozen", "ingredient"),
        ("Dressings", "ingredient"),
        ("Baking Supplies", "ingredient"),
        ("Oils & Fats", "ingredient"),
        ("Beverages", "ingredient"),
        ("Spices & Seasoning", "ingredient"),
        ("Cleaning & Non-Food", "ingredient"),
        ("General", "ingredient"),
        
        # Batch and inventory categories (shared)
        ("Sauces", "batch"),
        ("Dressings", "batch"),
        ("Soups", "batch"),
        ("Stocks & Broths", "batch"),
        ("Dough", "batch"),
        ("Marinades", "batch"),
        ("Produce", "batch"),
        ("Dairy", "batch"),
        ("Protein", "batch"),
        ("Frozen/Thaw", "batch"),
        ("Spreads & Dips", "batch"),
        ("Dessert", "batch"),
        ("Restock/Rotate", "batch"),
        ("Manual", "batch"),
        ("Specials", "batch"),
        ("Misc Tasks", "batch"),
        
        # Inventory categories (same as batch)
        ("Sauces", "inventory"),
        ("Dressings", "inventory"),
        ("Soups", "inventory"),
        ("Stocks & Broths", "inventory"),
        ("Dough", "inventory"),
        ("Marinades", "inventory"),
        ("Produce", "inventory"),
        ("Dairy", "inventory"),
        ("Protein", "inventory"),
        ("Frozen/Thaw", "inventory"),
        ("Spreads & Dips", "inventory"),
        ("Dessert", "inventory"),
        ("Restock/Rotate", "inventory"),
        ("Manual", "inventory"),
        ("Specials", "inventory"),
        ("Misc Tasks", "inventory"),
        
        # Recipe categories (use batch categories)
        ("Sauces", "recipe"),
        ("Dressings", "recipe"),
        ("Soups", "recipe"),
        ("Stocks & Broths", "recipe"),
        ("Dough", "recipe"),
        ("Marinades", "recipe"),
        ("Produce", "recipe"),
        ("Dairy", "recipe"),
        ("Protein", "recipe"),
        ("Frozen/Thaw", "recipe"),
        ("Spreads & Dips", "recipe"),
        ("Dessert", "recipe"),
        ("Specials", "recipe"),
        
        # Dish categories
        ("Appetizers", "dish"),
        ("Salads", "dish"),
        ("Sandwiches", "dish"),
        ("Entrées", "dish"),
        ("Sides", "dish"),
        ("Soups", "dish"),
        ("Desserts", "dish"),
        ("Beverages", "dish"),
        ("Specials", "dish"),
    ]
    
    created_count = 0
    for name, cat_type in default_categories:
        # Check if this specific category already exists
        existing = db.query(Category).filter(
            Category.name == name,
            Category.type == cat_type
        ).first()
        
        if not existing:
            print(f"Creating category: {name} ({cat_type})")
            category = Category(name=name, type=cat_type)
            db.add(category)
            created_count += 1
        else:
            print(f"Category already exists: {name} ({cat_type})")
    

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