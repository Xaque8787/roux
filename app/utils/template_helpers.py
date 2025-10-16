def format_unit_display(unit):
    """Format unit for display, converting underscores to slashes for fractions"""
    if not unit:
        return unit

    # Convert internal unit format to display format
    unit_display_map = {
        '3_4_cup': '3/4 cup',
        '2_3_cup': '2/3 cup',
        '1_2_cup': '1/2 cup',
        '1_3_cup': '1/3 cup',
        '1_4_cup': '1/4 cup',
        '1_8_cup': '1/8 cup'
    }

    return unit_display_map.get(unit, unit)

def setup_template_filters(templates_instance):
    """Setup custom filters for a Jinja2Templates instance"""
    templates_instance.env.filters['format_unit'] = format_unit_display
    return templates_instance

def get_category_emoji(category):
    """Get emoji for a category, with fallback"""
    if category and hasattr(category, 'icon') and category.icon:
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