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