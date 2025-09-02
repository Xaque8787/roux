"""
Utility functions for unit conversions in the food cost management system.
"""

from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session
from .models import UsageUnit, IngredientUsageUnit, Batch, InventoryItem

class ConversionResult:
    def __init__(self, factor: Optional[float], method: str, confidence: str, notes: str = ""):
        self.factor = factor
        self.method = method  # "direct", "standard", "ingredient", "manual", "none"
        self.confidence = confidence  # "high", "medium", "low"
        self.notes = notes
    
    @property
    def is_available(self):
        return self.factor is not None
    
    @property
    def ui_indicator_class(self):
        """Return CSS class for UI indicator"""
        if self.confidence == "high":
            return "text-success"  # Green
        elif self.confidence == "medium":
            return "text-warning"  # Yellow
        else:
            return "text-danger"  # Red

def get_batch_to_par_conversion(db: Session, batch: Batch, inventory_item: InventoryItem) -> ConversionResult:
    """
    Get conversion factor from batch yield units to inventory par units.
    Returns ConversionResult with factor, method, and confidence level.
    """
    
    if not batch.yield_unit_id or not inventory_item.par_unit_equals_unit_id:
        return ConversionResult(None, "none", "low", "Missing unit information")
    
    # 1. Check for manual override
    if inventory_item.manual_conversion_factor:
        return ConversionResult(
            inventory_item.manual_conversion_factor, 
            "manual", 
            "high",
            inventory_item.conversion_notes or "Manual override"
        )
    
    # 2. Check for direct unit match
    if batch.yield_unit_id == inventory_item.par_unit_equals_unit_id:
        return ConversionResult(1.0, "direct", "high", "Same unit")
    
    # 3. Check standard unit conversions
    standard_factor = get_standard_unit_conversion(db, batch.yield_unit_id, inventory_item.par_unit_equals_unit_id)
    if standard_factor:
        from_unit = db.query(UsageUnit).get(batch.yield_unit_id)
        to_unit = db.query(UsageUnit).get(inventory_item.par_unit_equals_unit_id)
        return ConversionResult(
            standard_factor, 
            "standard", 
            "high",
            f"Standard conversion: {from_unit.name} → {to_unit.name}"
        )
    
    # 4. Check ingredient-based conversions
    ingredient_factor = get_ingredient_based_conversion(db, batch, inventory_item)
    if ingredient_factor:
        return ConversionResult(
            ingredient_factor, 
            "ingredient", 
            "medium",
            "Based on recipe ingredient ratios"
        )
    
    # 5. No conversion available
    from_unit = db.query(UsageUnit).get(batch.yield_unit_id)
    to_unit = db.query(UsageUnit).get(inventory_item.par_unit_equals_unit_id)
    return ConversionResult(
        None, 
        "none", 
        "low",
        f"No conversion available: {from_unit.name if from_unit else 'Unknown'} → {to_unit.name if to_unit else 'Unknown'}"
    )

def get_standard_unit_conversion(db: Session, from_unit_id: int, to_unit_id: int) -> Optional[float]:
    """Get standard conversion factor between common units"""
    
    from_unit = db.query(UsageUnit).get(from_unit_id)
    to_unit = db.query(UsageUnit).get(to_unit_id)
    
    if not from_unit or not to_unit:
        return None
    
    # Standard weight conversions
    weight_conversions = {
        ('lb', 'oz'): 16.0,
        ('oz', 'lb'): 1/16.0,
        ('pound', 'oz'): 16.0,
        ('oz', 'pound'): 1/16.0,
        ('kg', 'g'): 1000.0,
        ('g', 'kg'): 1/1000.0,
        ('lb', 'g'): 453.592,
        ('g', 'lb'): 1/453.592,
        ('pound', 'g'): 453.592,
        ('g', 'pound'): 1/453.592,
    }
    
    # Standard volume conversions
    volume_conversions = {
        ('gal', 'qt'): 4.0,
        ('qt', 'gal'): 1/4.0,
        ('gallon', 'qt'): 4.0,
        ('qt', 'gallon'): 1/4.0,
        ('gal', 'cup'): 16.0,
        ('cup', 'gal'): 1/16.0,
        ('gallon', 'cup'): 16.0,
        ('cup', 'gallon'): 1/16.0,
        ('qt', 'cup'): 4.0,
        ('cup', 'qt'): 1/4.0,
        ('l', 'ml'): 1000.0,
        ('ml', 'l'): 1/1000.0,
        ('liter', 'ml'): 1000.0,
        ('ml', 'liter'): 1/1000.0,
    }
    
    all_conversions = {**weight_conversions, **volume_conversions}
    
    # Try direct conversion
    key = (from_unit.name.lower(), to_unit.name.lower())
    if key in all_conversions:
        return all_conversions[key]
    
    # Try reverse conversion
    reverse_key = (to_unit.name.lower(), from_unit.name.lower())
    if reverse_key in all_conversions:
        return 1.0 / all_conversions[reverse_key]
    
    return None

def get_ingredient_based_conversion(db: Session, batch: Batch, inventory_item: InventoryItem) -> Optional[float]:
    """
    Attempt to calculate conversion based on recipe ingredient usage units.
    This is a medium-confidence conversion.
    """
    
    if not batch.recipe_id:
        return None
    
    # Get recipe ingredients that might provide conversion clues
    from .models import RecipeIngredient
    recipe_ingredients = db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == batch.recipe_id
    ).all()
    
    # Look for ingredients that have both the batch yield unit and par unit in their usage units
    for ri in recipe_ingredients:
        ingredient_usage_units = ri.ingredient.usage_units
        
        batch_unit_conversion = None
        par_unit_conversion = None
        
        for iu in ingredient_usage_units:
            if iu.usage_unit_id == batch.yield_unit_id:
                batch_unit_conversion = iu.conversion_factor
            if iu.usage_unit_id == inventory_item.par_unit_equals_unit_id:
                par_unit_conversion = iu.conversion_factor
        
        # If we found both conversions, we can calculate the ratio
        if batch_unit_conversion and par_unit_conversion:
            # This gives us how many par units per batch unit
            return par_unit_conversion / batch_unit_conversion
    
    return None

def get_available_units_for_inventory_item(db: Session, inventory_item: InventoryItem) -> list:
    """
    Get available units for inventory item par unit selection.
    Priority: recipe units, batch units, then all units.
    """
    
    units = []
    unit_ids_seen = set()
    
    # Priority 1: Recipe units (if batch is attached)
    if inventory_item.batch and inventory_item.batch.recipe_id:
        from .models import RecipeIngredient
        recipe_ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == inventory_item.batch.recipe_id
        ).all()
        
        for ri in recipe_ingredients:
            for iu in ri.ingredient.usage_units:
                if iu.usage_unit_id not in unit_ids_seen:
                    units.append({
                        'id': iu.usage_unit.id,
                        'name': iu.usage_unit.name,
                        'source': 'recipe',
                        'priority': 1
                    })
                    unit_ids_seen.add(iu.usage_unit_id)
    
    # Priority 2: Batch yield unit (if batch is attached and not variable)
    if inventory_item.batch and inventory_item.batch.yield_unit_id and not inventory_item.batch.is_variable:
        if inventory_item.batch.yield_unit_id not in unit_ids_seen:
            units.append({
                'id': inventory_item.batch.yield_unit.id,
                'name': inventory_item.batch.yield_unit.name,
                'source': 'batch',
                'priority': 2
            })
            unit_ids_seen.add(inventory_item.batch.yield_unit_id)
    
    # Priority 3: All other usage units
    all_units = db.query(UsageUnit).all()
    for unit in all_units:
        if unit.id not in unit_ids_seen:
            units.append({
                'id': unit.id,
                'name': unit.name,
                'source': 'general',
                'priority': 3
            })
            unit_ids_seen.add(unit.id)
    
    # Sort by priority, then by name
    units.sort(key=lambda x: (x['priority'], x['name']))
    return units

def get_scale_options_for_batch(batch: Batch) -> list:
    """Get available scale options for a scalable batch"""
    if not batch.can_be_scaled:
        return []
    
    options = []
    
    if batch.scale_double:
        options.append({
            'key': 'double',
            'label': 'Double Batch (2x)',
            'factor': 2.0,
            'yield_amount': batch.yield_amount * 2
        })
    
    # Always include full batch as option
    options.append({
        'key': 'full',
        'label': 'Full Batch (1x)',
        'factor': 1.0,
        'yield_amount': batch.yield_amount
    })
    
    if batch.scale_half:
        options.append({
            'key': 'half',
            'label': 'Half Batch (1/2)',
            'factor': 0.5,
            'yield_amount': batch.yield_amount * 0.5
        })
    
    if batch.scale_quarter:
        options.append({
            'key': 'quarter',
            'label': 'Quarter Batch (1/4)',
            'factor': 0.25,
            'yield_amount': batch.yield_amount * 0.25
        })
    
    if batch.scale_eighth:
        options.append({
            'key': 'eighth',
            'label': 'Eighth Batch (1/8)',
            'factor': 0.125,
            'yield_amount': batch.yield_amount * 0.125
        })
    
    if batch.scale_sixteenth:
        options.append({
            'key': 'sixteenth',
            'label': 'Sixteenth Batch (1/16)',
            'factor': 0.0625,
            'yield_amount': batch.yield_amount * 0.0625
        })
    
    return options

def preview_conversion(db: Session, batch: Batch, inventory_item: InventoryItem, amount: float = 1.0) -> dict:
    """
    Preview what the conversion would look like for UI display.
    Returns dict with conversion info for display.
    """
    
    conversion_result = get_batch_to_par_conversion(db, batch, inventory_item)
    
    if not conversion_result.is_available:
        return {
            'available': False,
            'message': conversion_result.notes,
            'indicator_class': conversion_result.ui_indicator_class
        }
    
    batch_unit = db.query(UsageUnit).get(batch.yield_unit_id) if batch.yield_unit_id else None
    par_unit = db.query(UsageUnit).get(inventory_item.par_unit_equals_unit_id) if inventory_item.par_unit_equals_unit_id else None
    
    converted_amount = amount * conversion_result.factor
    
    return {
        'available': True,
        'factor': conversion_result.factor,
        'method': conversion_result.method,
        'confidence': conversion_result.confidence,
        'indicator_class': conversion_result.ui_indicator_class,
        'preview_text': f"{amount} {batch_unit.name if batch_unit else 'units'} = {converted_amount:.2f} {par_unit.name if par_unit else 'units'}",
        'notes': conversion_result.notes
    }