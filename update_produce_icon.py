#!/usr/bin/env python3
"""
Script to update the Produce category icon from carrot to herb emoji
Run this once to update your existing database
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models import Category
from app.database import DATABASE_URL

def update_produce_icon():
    """Update the Produce category icon from 🥕 to 🌿"""
    
    # Create database connection
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Find the Produce category for ingredients
        produce_category = db.query(Category).filter(
            Category.name == "Produce",
            Category.type == "ingredient"
        ).first()
        
        if produce_category:
            old_icon = produce_category.icon
            produce_category.icon = "🌿"
            db.commit()
            print(f"✅ Updated Produce category icon from {old_icon} to 🌿")
        else:
            print("❌ Produce category not found in ingredients")
            
        # List all ingredient categories for verification
        print("\n📋 Current ingredient categories:")
        ingredient_categories = db.query(Category).filter(Category.type == "ingredient").all()
        for cat in ingredient_categories:
            print(f"   {cat.icon} {cat.name}")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating category: {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    update_produce_icon()