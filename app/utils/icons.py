"""
Icon mapping system for categories across different sections
"""

# Ingredient category icons
INGREDIENT_CATEGORY_ICONS = {
    'dairy': 'fa-cheese',
    'produce': 'fa-carrot',
    'meat & poultry': 'fa-drumstick-bite',
    'seafood': 'fa-fish',
    'dry goods': 'fa-wheat-awn',
    'canned goods': 'fa-can-food',
    'frozen': 'fa-snowflake',
    'dressings': 'fa-bottle-droplet',
    'baking supplies': 'fa-bread-slice',
    'oils & fats': 'fa-oil-can',
    'beverages': 'fa-glass',
    'spices & seasoning': 'fa-pepper-hot',
    'cleaning & non-food': 'fa-soap',
    'general': 'fa-list-check'
}

# Batch and inventory category icons (shared)
BATCH_INVENTORY_CATEGORY_ICONS = {
    'sauces': 'fa-pot-food',
    'dressings': 'fa-bottle-droplet',
    'soups': 'fa-bowl-rice',
    'stocks & broths': 'fa-pot-food',
    'dough': 'fa-bread-slice',
    'marinades': 'fa-jar',
    'produce': 'fa-leaf',
    'dairy': 'fa-cheese',
    'protein': 'fa-drumstick-bite',
    'frozen/thaw': 'fa-snowflake',
    'spreads & dips': 'fa-bread-slice',
    'dessert': 'fa-ice-cream',
    'restock/rotate': 'fa-rotate',
    'manual': 'fa-hand',
    'specials': 'fa-star',
    'misc tasks': 'fa-list-check'
}

# Dish category icons
DISH_CATEGORY_ICONS = {
    'appetizers': 'fa-utensils',
    'salads': 'fa-seedling',
    'sandwiches': 'fa-burger',
    'entrées': 'fa-plate-wheat',
    'sides': 'fa-bowl-food',
    'soups': 'fa-mug-hot',
    'desserts': 'fa-ice-cream',
    'beverages': 'fa-wine-glass',
    'specials': 'fa-star'
}

def get_category_icon(category_name, category_type):
    """
    Get Font Awesome icon class for a category
    
    Args:
        category_name: Name of the category
        category_type: Type of category ('ingredient', 'batch', 'inventory', 'dish', 'recipe')
    
    Returns:
        tuple: (icon_class, color_class)
    """
    if not category_name:
        return 'fa-square', 'text-success'  # Green square fallback
    
    normalized_name = category_name.lower().strip()
    
    # Map category types to their icon dictionaries
    if category_type == 'ingredient':
        icon_dict = INGREDIENT_CATEGORY_ICONS
    elif category_type in ['batch', 'inventory']:
        icon_dict = BATCH_INVENTORY_CATEGORY_ICONS
    elif category_type == 'dish':
        icon_dict = DISH_CATEGORY_ICONS
    elif category_type == 'recipe':
        # Recipes use batch category icons since they become batches
        icon_dict = BATCH_INVENTORY_CATEGORY_ICONS
    else:
        return 'fa-circle', 'text-purple'  # User-created fallback
    
    # Get icon from dictionary or use user-created fallback
    icon = icon_dict.get(normalized_name, 'fa-circle')
    color = 'text-purple' if icon == 'fa-circle' else ''
    
    return icon, color

def get_task_icon(task):
    """
    Get icon for task based on source and category priority
    
    Priority:
    1. Janitorial tasks -> broom icon
    2. Inventory item category -> category icon
    3. Manual tasks -> hand icon
    """
    if hasattr(task, 'janitorial_task') and task.janitorial_task:
        return 'fa-broom', 'text-warning'
    elif hasattr(task, 'inventory_item') and task.inventory_item and task.inventory_item.category:
        # Use inventory item category (highest priority for inventory tasks)
        return get_category_icon(task.inventory_item.category.name, 'inventory')
    elif hasattr(task, 'batch') and task.batch and task.batch.recipe and task.batch.recipe.category:
        # Use batch category if no inventory item category
        return get_category_icon(task.batch.recipe.category.name, 'batch')
    else:
        # Manual task fallback
        return 'fa-hand', 'text-secondary'