from datetime import date
from sqlalchemy.orm import Session
from ..models import Category, VendorUnit, Vendor, ParUnitName, JanitorialTask

def create_default_categories(db: Session):
    """Create default categories if they don't exist"""
    default_categories = [
        ("Proteins", "ingredient"),
        ("Vegetables", "ingredient"),
        ("Dairy", "ingredient"),
        ("Grains", "ingredient"),
        ("Spices", "ingredient"),
        ("Appetizers", "recipe"),
        ("Main Courses", "recipe"),
        ("Desserts", "recipe"),
        ("Beverages", "recipe"),
        ("Production", "batch"),
        ("Prep", "batch"),
        ("Hot Food", "dish"),
        ("Cold Food", "dish"),
        ("Beverages", "dish"),
        ("Proteins", "inventory"),
        ("Vegetables", "inventory"),
        ("Prepared Items", "inventory"),
    ]
    
    # Check for duplicate category names across different types
    existing_categories = {}
    for category in db.query(Category).all():
        key = (category.name, category.type)
        existing_categories[key] = True
    
    for name, cat_type in default_categories:
        key = (name, cat_type)
        if key not in existing_categories:
            category = Category(name=name, type=cat_type)
            db.add(category)
            existing_categories[key] = True
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # If there's still an integrity error, it means categories were created concurrently
        # This is acceptable for setup, so we can continue
        pass

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