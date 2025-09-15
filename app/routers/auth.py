{% extends "base.html" %}

{% block title %}Inventory Day {{ inventory_day.date }} - Food Cost Management{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <h1><i class="fas fa-calendar-day"></i> Inventory Day: {{ inventory_day.date }}</h1>
        <a href="/inventory" class="btn btn-secondary mb-3">
            <i class="fas fa-arrow-left"></i> Back to Inventory
        </a>
        
        {% if inventory_day.finalized %}
        <span class="badge bg-success ms-2">Finalized</span>
        {% else %}
        <span class="badge bg-warning ms-2">In Progress</span>
        {% endif %}
    </div>
</div>

<!-- Real-time Updates Status -->
<div class="row mb-2">
    <div class="col-12">
        <div class="alert alert-info d-flex justify-content-between align-items-center" id="realtimeStatus">
            <div>
                <i class="fas fa-wifi" id="connectionIcon"></i>
                <span id="connectionStatus">Connecting to real-time updates...</span>
            </div>
            <div>
                <small id="activeUsers">Users online: <span id="userCount">0</span></small>
            </div>
        </div>
    </div>
</div>

{% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
<div class="row mb-3">
    <div class="col-12">
        <form method="post" action="/inventory/day/{{ inventory_day.id }}/update" class="d-inline">
            <input type="hidden" name="global_notes" value="{{ inventory_day.global_notes or '' }}">
            <button type="submit" name="force_regenerate" value="true" class="btn btn-warning me-2" 
                    onclick="return confirm('This will regenerate all auto-generated tasks. Continue?')">
                <i class="fas fa-sync"></i> Regenerate Tasks
            </button>
        </form>
        
        <form method="post" action="/inventory/day/{{ inventory_day.id }}/finalize" class="d-inline">
            <button type="submit" class="btn btn-success" 
                    onclick="return confirm('Finalize this day? This cannot be undone.')">
                <i class="fas fa-lock"></i> Finalize Day
            </button>
        </form>
    </div>
</div>
{% endif %}

<div class="row">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-boxes"></i> Daily Inventory</h5>
            </div>
            <div class="card-body">
                {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                <form method="post" action="/inventory/day/{{ inventory_day.id }}/update">
                    <div class="mb-3">
                        <label for="global_notes" class="form-label">Day Notes</label>
                        <textarea class="form-control" id="global_notes" name="global_notes" rows="2">{{ inventory_day.global_notes or '' }}</textarea>
                    </div>
                {% endif %}
                
                <div class="table-responsive">
                    <table class="table table-striped table-sm table-sortable">
                        <thead>
                            <tr>
                                <th data-sortable data-sort-type="text">Item</th>
                                <th data-sortable data-sort-type="number">Quantity</th>
                                <th data-sortable data-sort-type="number">Par Level</th>
                                <th data-sortable data-sort-type="text">Status</th>
                                {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                                <th>Override</th>
                                {% endif %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for day_item in inventory_day_items %}
                            {% set is_below_par = day_item.quantity < day_item.inventory_item.par_level %}
                            {% set is_on_par = day_item.quantity == day_item.inventory_item.par_level %}
                            {% set is_near_par = day_item.quantity == day_item.inventory_item.par_level + 1 %}
                            {% set is_good = day_item.quantity >= day_item.inventory_item.par_level + 2 %}
                            <tr class="{% if is_below_par %}table-danger{% elif is_on_par %}table-info{% elif is_near_par %}table-warning{% endif %}">
                                <td>
                                    <strong>{{ day_item.inventory_item.name }}</strong>
                                    {% if day_item.inventory_item.batch %}
                                    <br><small class="text-info">
                                        <i class="fas fa-link"></i> {{ day_item.inventory_item.batch.recipe.name }}
                                    </small>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                                    <input type="number" class="form-control form-control-sm" 
                                           name="item_{{ day_item.inventory_item_id }}" 
                                           value="{{ day_item.quantity }}" step="0.1" style="width: 80px;">
                                    {% else %}
                                    {{ day_item.quantity }}
                                    {% endif %}
                                </td>
                                <td>
                                    {{ day_item.inventory_item.par_level }}
                                    {% if day_item.inventory_item.par_unit_name %}
                                    <br><small class="text-muted">{{ day_item.inventory_item.par_unit_name.name }}</small>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if is_below_par %}
                                        <span class="badge bg-danger">Below Par</span>
                                    {% elif is_on_par %}
                                        <span class="badge bg-info">On Par</span>
                                    {% elif is_near_par %}
                                        <span class="badge bg-warning">Near Par</span>
                                    {% else %}
                                        <span class="badge bg-success">Good</span>
                                    {% endif %}
                                </td>
                                {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                                <td>
                                    <div class="form-check form-check-inline">
                                        <input class="form-check-input" type="checkbox" 
                                               name="override_create_{{ day_item.inventory_item_id }}" 
                                               {% if day_item.override_create_task %}checked{% endif %}>
                                        <label class="form-check-label">
                                            <small>Force Task</small>
                                        </label>
                                    </div>
                                    <div class="form-check form-check-inline">
                                        <input class="form-check-input" type="checkbox" 
                                               name="override_no_task_{{ day_item.inventory_item_id }}" 
                                               {% if day_item.override_no_task %}checked{% endif %}>
                                        <label class="form-check-label">
                                            <small>No Task</small>
                                        </label>
                                    </div>
                                </td>
                                {% endif %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                
                {% if janitorial_day_items %}
                <h6 class="mt-4">Janitorial Tasks</h6>
                <div class="table-responsive">
                    <table class="table table-striped table-sm table-sortable">
                        <thead>
                            <tr>
                                <th data-sortable data-sort-type="text">Task</th>
                                <th data-sortable data-sort-type="text">Type</th>
                                {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                                <th>Include</th>
                                {% endif %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for janitorial_day_item in janitorial_day_items %}
                            <tr>
                                <td>
                                    <strong>{{ janitorial_day_item.janitorial_task.title }}</strong>
                                    {% if janitorial_day_item.janitorial_task.instructions %}
                                    <br><small class="text-muted">{{ janitorial_day_item.janitorial_task.instructions[:30] }}{% if janitorial_day_item.janitorial_task.instructions|length > 30 %}...{% endif %}</small>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if janitorial_day_item.janitorial_task.task_type == 'daily' %}
                                        <span class="badge bg-primary">Daily</span>
                                    {% else %}
                                        <span class="badge bg-secondary">Manual</span>
                                    {% endif %}
                                </td>
                                {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                                <td>
                                    {% if janitorial_day_item.janitorial_task.task_type == 'daily' %}
                                        <span class="text-muted">Auto-included</span>
                                    {% else %}
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" 
                                                   name="janitorial_{{ janitorial_day_item.janitorial_task_id }}" 
                                                   {% if janitorial_day_item.include_task %}checked{% endif %}>
                                            <label class="form-check-label">Include</label>
                                        </div>
                                    {% endif %}
                                </td>
                                {% endif %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% endif %}
                
                {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                    <button type="submit" class="btn btn-primary mt-3">
                        <i class="fas fa-save"></i> Update Inventory & Generate Tasks
                    </button>
                </form>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-tasks"></i> Tasks</h5>
            </div>
            <div class="card-body">
                {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                <div class="mb-3">
                    <button type="button" class="btn btn-success btn-sm" data-bs-toggle="modal" data-bs-target="#addTaskModal">
                        <i class="fas fa-plus"></i> Add Manual Task
                    </button>
                </div>
                {% endif %}
                
                <div class="table-responsive">
                    <table class="table table-striped table-sm table-sortable">
                        <thead>
                            <tr>
                                <th data-sortable data-sort-type="text">Task</th>
                                <th data-sortable data-sort-type="text">Assigned To</th>
                                <th data-sortable data-sort-type="text">Status</th>
                                <th data-sortable data-sort-type="number">Time</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for task in tasks %}
                            <tr>
                                <td>
                                    <small>{{ task.description }}</small>
                                   {% if task.inventory_item and task.inventory_item.category %}
                                       {{ task.inventory_item.category.icon or '🔘' }}
                                   {% elif task.inventory_item and task.inventory_item.batch and task.inventory_item.batch.category %}
                                       {{ task.inventory_item.batch.category.icon or '🔘' }}
                                   {% elif task.janitorial_task_id %}
                                       🧹
                                   {% elif task.batch and task.batch.category %}
                                       {{ task.batch.category.icon or '🔘' }}
                                   {% elif task.category %}
                                       {{ task.category.icon or '🔘' }}
                                   {% else %}
                                       🔘
                                   {% endif %}
                                    {% if task.batch %}
                                        <br><small class="text-info">{{ task.batch.recipe.name }}
                                            {% if task.selected_scale and task.selected_scale != 'full' %}
                                            ({{ task.selected_scale }})
                                            {% endif %}
                                        </small>
                                    {% endif %}
                                    {% if task.made_amount %}
                                    <br><small class="text-success">
                                        <i class="fas fa-check"></i> Made: {{ task.made_amount }} {{ task.made_unit }}
                                    </small>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if task.assigned_employee_ids %}
                                        {% set employee_ids = task.assigned_employee_ids.split(',') %}
                                        {% if employee_ids|length > 1 %}
                                            <small class="text-info">Team of {{ employee_ids|length }}</small>
                                            <br>
                                            {% for emp_id in employee_ids %}
                                                {% for emp in employees %}
                                                    {% if emp.id|string == emp_id %}
                                                        <small class="badge bg-secondary me-1">{{ emp.full_name or emp.username }}</small>
                                                    {% endif %}
                                                {% endfor %}
                                            {% endfor %}
                                        {% else %}
                                            {% for emp_id in employee_ids %}
                                                {% for emp in employees %}
                                                    {% if emp.id|string == emp_id %}
                                                        <small>{{ emp.full_name or emp.username }}</small>
                                                    {% endif %}
                                                {% endfor %}
                                            {% endfor %}
                                        {% endif %}
                                    {% elif task.assigned_to %}
                                        <small>{{ task.assigned_to.full_name or task.assigned_to.username }}</small>
                                    {% else %}
                                        <small class="text-warning">Unassigned</small>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if task.status == "not_started" %}
                                        {% if task.requires_scale_selection %}
                                        <button type="button" class="btn btn-primary btn-sm" onclick="showScaleSelection({{ task.id }}, '{{ task.batch.recipe.name if task.batch else task.description }}')">
                                            <i class="fas fa-play"></i> Select Scale & Start
                                        </button>
                                        {% elif not inventory_day.finalized and current_user.role in ["admin", "manager", "user"] %}
                                        <form method="post" action="/inventory/day/{{ inventory_day.id }}/tasks/{{ task.id }}/start" style="display: inline;">
                                            <button type="submit" class="btn btn-primary btn-sm">
                                                <i class="fas fa-play"></i> Start
                                            </button>
                                        </form>
                                        {% else %}
                                        <span class="badge bg-secondary">Not Started</span>
                                        {% endif %}
                                    {% elif task.status == "in_progress" %}
                                        {% if not inventory_day.finalized and current_user.role in ["admin", "manager", "user"] %}
                                        <form method="post" action="/inventory/day/{{ inventory_day.id }}/tasks/{{ task.id }}/pause" style="display: inline;">
                                            <button type="submit" class="btn btn-warning btn-sm">
                                                <i class="fas fa-pause"></i> Pause
                                            </button>
                                        </form>
                                        {% if task.requires_made_amount %}
                                        <button type="button" class="btn btn-success btn-sm" onclick="showMadeAmountInput({{ task.id }}, '{{ task.batch.recipe.name if task.batch else task.description }}')">
                                            <i class="fas fa-check"></i> Finish & Enter Amount
                                        </button>
                                        {% else %}
                                        <form method="post" action="/inventory/day/{{ inventory_day.id }}/tasks/{{ task.id }}/finish" style="display: inline;">
                                            <button type="submit" class="btn btn-success btn-sm">
                                                <i class="fas fa-check"></i> Finish
                                            </button>
                                        </form>
                                        {% endif %}
                                        {% else %}
                                        <span class="badge bg-primary">In Progress</span>
                                        {% endif %}
                                    {% elif task.status == "paused" %}
                                        {% if task.requires_made_amount %}
                                        <button type="button" class="btn btn-success btn-sm" onclick="showMadeAmountInput({{ task.id }}, '{{ task.batch.recipe.name if task.batch else task.description }}')">
                                            <i class="fas fa-check"></i> Finish & Enter Amount
                                        </button>
                                        {% elif not inventory_day.finalized and current_user.role in ["admin", "manager", "user"] %}
                                        <form method="post" action="/inventory/day/{{ inventory_day.id }}/tasks/{{ task.id }}/resume" style="display: inline;">
                                            <button type="submit" class="btn btn-info btn-sm">
                                                <i class="fas fa-play"></i> Resume
                                            </button>
                                        </form>
                                        {% else %}
                                        <span class="badge bg-warning">Paused</span>
                                        {% endif %}
                                    {% elif task.status == "completed" %}
                                        <span class="badge bg-success">Completed</span>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if task.started_at %}
                                        <small>{{ task.total_time_minutes }} min</small>
                                        {% if task.finished_at and task.assigned_employees|length > 0 %}
                                        <br><small class="text-success">${{ "%.2f"|format(task.labor_cost) }}</small>
                                        {% endif %}
                                    {% else %}
                                        <small class="text-muted">-</small>
                                    {% endif %}
                                </td>
                                <td>
                                    <a href="/inventory/day/{{ inventory_day.id }}/tasks/{{ task.id }}" class="btn btn-sm btn-outline-info">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    {% if not inventory_day.finalized and current_user.role in ["admin", "manager"] %}
                                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="showAssignModal({{ task.id }})">
                                        <i class="fas fa-users"></i> Assign
                                    </button>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-info-circle"></i> Day Summary</h5>
            </div>
            <div class="card-body">
                {% if inventory_day.employees_working %}
                <p><strong>Employees Working:</strong></p>
                {% set employee_ids = inventory_day.employees_working.split(',') %}
                <div class="d-flex flex-wrap gap-1 mb-3">
                    {% for emp_id in employee_ids %}
                        {% for emp in employees %}
                            {% if emp.id|string == emp_id %}
                            <span class="badge bg-secondary">{{ emp.full_name or emp.username }}</span>
                            {% endif %}
                        {% endfor %}
                    {% endfor %}
                </div>
                {% endif %}
                
                {% set total_tasks = tasks|length %}
                {% set completed_tasks = 0 %}
                {% set in_progress_tasks = 0 %}
                {% set below_par_count = 0 %}
                
                {% for task in tasks %}
                    {% if task.status == 'completed' %}
                        {% set completed_tasks = completed_tasks + 1 %}
                    {% elif task.status == 'in_progress' %}
                        {% set in_progress_tasks = in_progress_tasks + 1 %}
                    {% endif %}
                {% endfor %}
                
                {% for day_item in inventory_day_items %}
                    {% if day_item.quantity < day_item.inventory_item.par_level %}
                        {% set below_par_count = below_par_count + 1 %}
                    {% endif %}
                {% endfor %}
                
                <div class="row text-center">
                    <div class="col-6">
                        <div class="card bg-primary text-white">
                            <div class="card-body p-2">
                                <h5>{{ total_tasks }}</h5>
                                <small>Total Tasks</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="card bg-success text-white">
                            <div class="card-body p-2">
                                <h5>{{ completed_tasks }}</h5>
                                <small>Completed</small>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row text-center mt-2">
                    <div class="col-6">
                        <div class="card bg-warning text-white">
                            <div class="card-body p-2">
                                <h5>{{ in_progress_tasks }}</h5>
                                <small>In Progress</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-6">
                        <div class="card bg-danger text-white">
                            <div class="card-body p-2">
                                <h5>{{ below_par_count }}</h5>
                                <small>Below Par</small>
                            </div>
                        </div>
                    </div>
                </div>
                
                {% set total_time = 0 %}
                {% set total_cost = 0 %}
                {% for task in tasks %}
                    {% if task.finished_at %}
                        {% set total_time = total_time + task.total_time_minutes %}
                        {% set total_cost = total_cost + task.labor_cost %}
                    {% endif %}
                {% endfor %}
                
                {% if completed_tasks > 0 %}
                <div class="mt-3">
                    <p><strong>Total Time:</strong> {{ total_time }} minutes ({{ "%.1f"|format(total_time / 60) }} hours)</p>
                    <p><strong>Total Labor Cost:</strong> ${{ "%.2f"|format(total_cost) }}</p>
                </div>
                {% endif %}
            </div>
        </div>
        
        {% if task_summaries %}
        <div class="card mt-3">
            <div class="card-header">
                <h5><i class="fas fa-clipboard-check"></i> Completed Task Summaries</h5>
            </div>
            <div class="card-body">
                {% for task_id, summary in task_summaries.items() %}
                {% set task = tasks|selectattr('id', 'equalto', task_id)|first %}
                {% if task %}
                <div class="card mb-2">
                    <div class="card-body p-2">
                        <h6 class="mb-1">{{ task.description }}</h6>
                        <div class="row">
                            <div class="col-6">
                                <small><strong>Par Level:</strong> {{ "%.1f"|format(summary.par_level) }} {{ summary.par_unit_name }}</small>
                                <br><small><strong>Initial:</strong> {{ "%.1f"|format(summary.initial_inventory) }} {{ summary.par_unit_name }}</small>
                                {% if summary.made_amount %}
                                <br><small><strong>Made:</strong> {{ summary.made_amount }} {{ summary.made_unit }}</small>
                                {% endif %}
                            </div>
                            <div class="col-6">
                                <small><strong>Final:</strong> {{ "%.1f"|format(summary.final_inventory) }} {{ summary.par_unit_name }}</small>
                                {% if summary.par_unit_equals %}
                                <br><small><strong>Equals:</strong> {{ "%.2f"|format(summary.par_unit_equals) }} {{ summary.par_unit_equals_unit or '' }}</small>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
                {% endif %}
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
</div>

<!-- Add Manual Task Modal -->
<div class="modal fade" id="addTaskModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Add Manual Task</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="post" action="/inventory/day/{{ inventory_day.id }}/tasks/new">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="taskDescription" class="form-label">Task Description</label>
                        <input type="text" class="form-control" id="taskDescription" name="description" required>
                    </div>
                    <div class="mb-3">
                        <label for="taskAssignedTo" class="form-label">Assign To (Multiple Selection)</label>
                        <select class="form-select" id="taskAssignedTo" name="assigned_to_ids" multiple>
                            {% for emp in employees %}
                            <option value="{{ emp.id }}">{{ emp.full_name or emp.username }}</option>
                            {% endfor %}
                        </select>
                        <small class="text-muted">Hold Ctrl/Cmd to select multiple employees</small>
                    </div>
                    <div class="mb-3">
                        <label for="taskInventoryItem" class="form-label">Link to Inventory Item (Optional)</label>
                        <select class="form-select" id="taskInventoryItem" name="inventory_item_id">
                            <option value="">No inventory item</option>
                            {% for day_item in inventory_day_items %}
                            <option value="{{ day_item.inventory_item.id }}">{{ day_item.inventory_item.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="taskBatch" class="form-label">Link to Batch (Optional)</label>
                        <select class="form-select" id="taskBatch" name="batch_id">
                            <option value="">No batch</option>
                            {% for batch in batches %}
                            <option value="{{ batch.id }}">{{ batch.recipe.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="taskCategory" class="form-label">Category (Optional)</label>
                        <select class="form-select" id="taskCategory" name="category_id">
                            <option value="">No category</option>
                            {% for cat in categories %}
                            <option value="{{ cat.id }}">{{ cat.icon or '🔘' }} {{ cat.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="submit" class="btn btn-primary">Add Task</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- Assign Task Modal -->
<div class="modal fade" id="assignTaskModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Assign Task</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form id="assignTaskForm" method="post">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="assignTaskTo" class="form-label">Assign To (Multiple Selection)</label>
                        <select class="form-select" id="assignTaskTo" name="assigned_to_ids" multiple required>
                            {% for emp in employees %}
                            <option value="{{ emp.id }}">{{ emp.full_name or emp.username }}</option>
                            {% endfor %}
                        </select>
                        <small class="text-muted">Hold Ctrl/Cmd to select multiple employees</small>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="submit" class="btn btn-primary">Assign Task</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
function showNotification(message, type = 'info') {
    console.log('Showing notification:', message, type);
    
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}
</script>

<script>
// WebSocket Real-time Updates
let ws = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
let reconnectTimeout = null;

function getCookieValue(name) {
    console.log('Getting cookie value for:', name);
    console.log('All cookies:', document.cookie);
    console.log('All cookies:', document.cookie);
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        const cookieValue = parts.pop().split(';').shift();
        console.log('Found cookie value:', cookieValue ? 'token exists' : 'no token');
        return cookieValue;
    }
    console.log('Cookie not found');
        "cookie_count": len(cookies),
        "raw_cookie_header": request.headers.get('cookie', 'No cookie header'),
        "user_agent": request.headers.get('user-agent', 'No user agent')
}

function connectWebSocket() {
    console.log('Starting WebSocket connection...');
    
    const token = getCookieValue('access_token');
    if (!token) {
        console.error('No access token found in cookies');
        updateConnectionStatus('error', 'No authentication token found');
        return;
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/inventory/{{ inventory_day.id }}?token=${encodeURIComponent(token)}`;
    
    console.log('Connecting to WebSocket:', wsUrl);
    updateConnectionStatus('connecting', 'Connecting to real-time updates...');
    
    try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function(event) {
            console.log('WebSocket connection opened');
            reconnectAttempts = 0;
            updateConnectionStatus('connected', 'Connected to real-time updates');
            
            // Send initial ping
            ws.send(JSON.stringify({type: 'ping'}));
        };
        
        ws.onmessage = function(event) {
            console.log('WebSocket message received:', event.data);
            
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        ws.onclose = function(event) {
            console.log('WebSocket connection closed:', event.code, event.reason);
            updateConnectionStatus('disconnected', 'Connection lost');
            
            // Attempt to reconnect if not intentionally closed
            if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttempts})`);
                
                reconnectTimeout = setTimeout(() => {
                    connectWebSocket();
                }, delay);
            }
        };
        
        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
            updateConnectionStatus('error', 'Connection error');
        };
        
    } catch (error) {
        console.error('Error creating WebSocket:', error);
        updateConnectionStatus('error', 'Failed to create connection');
    }
}

function handleWebSocketMessage(data) {
    console.log('Handling message:', data);
    
    switch (data.type) {
        case 'connection_success':
            console.log('Connection successful:', data.user);
            updateConnectionStatus('connected', 'Connected to real-time updates');
            showNotification(`Connected as ${data.user.username}`, 'success');
            break;
            
        case 'user_count_update':
            console.log('User count update:', data.user_count, data.users);
            updateUserCount(data.user_count, data.users);
            break;
            
        case 'task_update':
            console.log('Task update:', data.task);
            handleTaskUpdate(data.task);
            break;
            
        case 'inventory_update':
            console.log('Inventory update:', data.inventory);
            handleInventoryUpdate(data.inventory);
            break;
            
        case 'heartbeat':
            console.log('Heartbeat received');
            break;
            
        case 'error':
            console.error('WebSocket error message:', data.message);
            updateConnectionStatus('error', data.message);
            showNotification(data.message, 'error');
            break;
            
        default:
            console.log('Unknown message type:', data.type);
    }
}

function updateConnectionStatus(status, message) {
    console.log('Updating connection status:', status, message);
    
    const statusElement = document.getElementById('connectionStatus');
    const iconElement = document.getElementById('connectionIcon');
    
    if (statusElement) {
        statusElement.textContent = message;
    }
    
    if (iconElement) {
        iconElement.className = status === 'connected' ? 'fas fa-wifi text-success' :
                               status === 'connecting' ? 'fas fa-wifi text-warning' :
                               status === 'disconnected' ? 'fas fa-wifi text-warning' :
                               'fas fa-wifi text-danger';
    }
}

function updateUserCount(count, users) {
    console.log('Updating user count:', count, users);
    
    const userCountElement = document.getElementById('userCount');
    if (userCountElement) {
        userCountElement.textContent = count;
    }
    
    // Show user names if available
    if (users && users.length > 0) {
        const userNames = users.map(u => u.username).join(', ');
        console.log('Active users:', userNames);
    }
}

function handleTaskUpdate(taskData) {
    console.log('Handling task update:', taskData);
    
    let message = '';
    switch (taskData.action) {
        case 'started':
            message = `Task started by ${taskData.started_by}`;
            break;
        case 'started_with_scale':
            message = `Task started (${taskData.selected_scale}) by ${taskData.started_by}`;
            break;
        case 'paused':
            message = `Task paused by ${taskData.paused_by}`;
            break;
        case 'resumed':
            message = `Task resumed by ${taskData.resumed_by}`;
            break;
        case 'finished':
            message = `Task completed by ${taskData.finished_by}`;
            if (taskData.made_amount) {
                message += ` (Made: ${taskData.made_amount} ${taskData.made_unit})`;
            }
            break;
        case 'assigned':
            message = `Task assigned by ${taskData.assigned_by}`;
            break;
        case 'created':
            message = `New task created by ${taskData.created_by}`;
            break;
        default:
            message = `Task updated: ${taskData.action}`;
    }
    
    showNotification(message, 'info');
    
    // Refresh page after a short delay to show updated state
    setTimeout(() => {
        console.log('Refreshing page to show updated task state...');
        window.location.reload();
    }, 2000);
}

function handleInventoryUpdate(inventoryData) {
    console.log('Handling inventory update:', inventoryData);
    
    showNotification(`Inventory updated by ${inventoryData.updated_by}`, 'info');
    
    // Refresh page after a short delay
    setTimeout(() => {
        console.log('Refreshing page to show updated inventory...');
        window.location.reload();
    }, 2000);
}

function showNotification(message, type = 'info') {
    console.log('Showing notification:', message, type);
    
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}

// Connect when page loads (only for non-finalized days)
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, checking if should connect to WebSocket...');
    
    {% if not inventory_day.finalized %}
    console.log('Day is not finalized, connecting to WebSocket...');
    connectWebSocket();
    {% else %}
    console.log('Day is finalized, skipping WebSocket connection');
    updateConnectionStatus('info', 'Day is finalized - real-time updates disabled');
    {% endif %}
});

// Clean up WebSocket on page unload
window.addEventListener('beforeunload', function() {
    if (ws) {
        console.log('Closing WebSocket connection...');
        ws.close(1000, 'Page unload');
    }
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
    }
});
</script>

{% endblock %}