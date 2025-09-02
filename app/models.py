{% extends "base.html" %}

{% block title %}Edit {{ item.name }} - Food Cost Management{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <h1><i class="fas fa-edit"></i> Edit Inventory Item: {{ item.name }}</h1>
        <a href="/inventory" class="btn btn-secondary mb-3">
            <i class="fas fa-arrow-left"></i> Back to Inventory
        </a>
    </div>
</div>

<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-edit"></i> Item Information</h5>
            </div>
            <div class="card-body">
                <form method="post" action="/inventory/items/{{ item.id }}/edit">
                    <div class="mb-3">
                        <label for="name" class="form-label">Item Name</label>
                        <input type="text" class="form-control" id="name" name="name" value="{{ item.name }}" required>
                    </div>
                    <div class="mb-3">
                        <label for="par_level" class="form-label">Par Level</label>
                        <input type="number" class="form-control" id="par_level" name="par_level" 
                               step="0.01" min="0" value="{{ item.par_level }}" required>
                    </div>
                    <div class="mb-3">
                        <label for="par_unit_equals_amount" class="form-label">Par Unit Equals</label>
                        <div class="row">
                            <div class="col-8">
                                <input type="number" class="form-control" id="par_unit_equals_amount" name="par_unit_equals_amount" 
                                       step="0.01" min="0.01" value="{{ item.par_unit_equals_amount or 1.0 }}" required>
                            </div>
                            <div class="col-4">
                                <select class="form-select" id="par_unit_equals_unit_id" name="par_unit_equals_unit_id" required>
                                    <option value="">Select Unit</option>
                                    {% for unit in usage_units %}
                                    <option value="{{ unit.id }}" {% if item.par_unit_equals_unit_id == unit.id %}selected{% endif %}>
                                        {{ unit.name }}
                                    </option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>
                        <small class="text-muted">1 par level count equals how many units?</small>
                        <div id="conversionPreview" class="mt-2" style="display: none;">
                            <small id="conversionText" class=""></small>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="manual_conversion_factor" class="form-label">Manual Conversion Override (Optional)</label>
                        <input type="number" class="form-control" id="manual_conversion_factor" name="manual_conversion_factor" 
                               step="0.0001" value="{{ item.manual_conversion_factor or '' }}" 
                               placeholder="Leave blank for automatic conversion">
                        <small class="text-muted">Override automatic conversion between batch yield and par units</small>
                    </div>
                    <div class="mb-3">
                        <label for="conversion_notes" class="form-label">Conversion Notes (Optional)</label>
                        <input type="text" class="form-control" id="conversion_notes" name="conversion_notes" 
                               value="{{ item.conversion_notes or '' }}" placeholder="Notes about the conversion method">
                    </div>
                    <div class="mb-3">
                        <label for="batch_id" class="form-label">Linked Batch (Optional)</label>
                        <select class="form-select" id="batch_id" name="batch_id">
                            <option value="">No batch linked</option>
                            {% for batch in batches %}
                            <option value="{{ batch.id }}" {% if item.batch_id == batch.id %}selected{% endif %}>
                                {{ batch.recipe.name }} ({{ batch.yield_amount }} {{ batch.yield_unit.name if batch.yield_unit else '' }})
                            </option>
                            {% endfor %}
                        </select>
                        <small class="text-muted">Link to a batch for labor cost tracking</small>
                    </div>
                    <div class="mb-3">
                        <label for="category_id" class="form-label">Category</label>
                        <select class="form-select" id="category_id" name="category_id">
                            <option value="">Select Category</option>
                            {% for cat in categories %}
                            <option value="{{ cat.id }}" {% if item.category_id == cat.id %}selected{% endif %}>
                                {{ cat.name }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="d-flex justify-content-between">
                        <a href="/inventory" class="btn btn-secondary">Cancel</a>
                        <button type="submit" class="btn btn-success">
                            <i class="fas fa-save"></i> Save Changes
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Load units when batch selection changes
    document.getElementById('batch_id').addEventListener('change', loadUnitsForBatch);
    
    // Load units on page load
    loadUnitsForBatch();
    
    // Update conversion preview when values change
    document.getElementById('batch_id').addEventListener('change', updateConversionPreview);
    document.getElementById('par_unit_equals_unit_id').addEventListener('change', updateConversionPreview);
    document.getElementById('manual_conversion_factor').addEventListener('input', updateConversionPreview);
});

async function loadUnitsForBatch() {
    const batchSelect = document.getElementById('batch_id');
    const unitSelect = document.getElementById('par_unit_equals_unit_id');
    const currentUnitId = {{ item.par_unit_equals_unit_id or 'null' }};
    const batchId = batchSelect.value;
    
    // Store current selection
    const currentValue = unitSelect.value;
    
    // Clear current options
    unitSelect.innerHTML = '<option value="">Select Unit</option>';
    
    if (!batchId) {
        // No batch selected - load all usage units
        try {
            const response = await fetch('/api/usage_units/all');
            const units = await response.json();
            
            units.forEach(unit => {
                const option = document.createElement('option');
                option.value = unit.id;
                option.textContent = unit.name;
                if (unit.id === currentUnitId) {
                    option.selected = true;
                }
                unitSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading all units:', error);
        }
        return;
    }
    
    try {
        const response = await fetch(`/api/inventory/batch/${batchId}/available_units`);
        const units = await response.json();
        
        // Group units by priority
        const recipeUnits = units.filter(u => u.source === 'recipe');
        const batchUnits = units.filter(u => u.source === 'batch');
        const generalUnits = units.filter(u => u.source === 'general');
        
        // Add recipe units first
        if (recipeUnits.length > 0) {
            const recipeGroup = document.createElement('optgroup');
            recipeGroup.label = 'Recipe Units (Recommended)';
            recipeUnits.forEach(unit => {
                const option = document.createElement('option');
                option.value = unit.id;
                option.textContent = unit.name;
                if (unit.id === currentUnitId) {
                    option.selected = true;
                }
                recipeGroup.appendChild(option);
            });
            unitSelect.appendChild(recipeGroup);
        }
        
        // Add batch units
        if (batchUnits.length > 0) {
            const batchGroup = document.createElement('optgroup');
            batchGroup.label = 'Batch Units';
            batchUnits.forEach(unit => {
                const option = document.createElement('option');
                option.value = unit.id;
                option.textContent = unit.name;
                if (unit.id === currentUnitId) {
                    option.selected = true;
                }
                batchGroup.appendChild(option);
            });
            unitSelect.appendChild(batchGroup);
        }
        
        // Add general units
        if (generalUnits.length > 0) {
            const generalGroup = document.createElement('optgroup');
            generalGroup.label = 'Other Units';
            generalUnits.forEach(unit => {
                const option = document.createElement('option');
                option.value = unit.id;
                option.textContent = unit.name;
                if (unit.id === currentUnitId) {
                    option.selected = true;
                }
                generalGroup.appendChild(option);
            });
            unitSelect.appendChild(generalGroup);
        }
        
        updateConversionPreview();
    } catch (error) {
        console.error('Error loading units for batch:', error);
    }
}

async function updateConversionPreview() {
    const batchSelect = document.getElementById('batch_id');
    const unitSelect = document.getElementById('par_unit_equals_unit_id');
    const manualFactorInput = document.getElementById('manual_conversion_factor');
    const previewDiv = document.getElementById('conversionPreview');
    const previewText = document.getElementById('conversionText');
    
    const batchId = batchSelect.value;
    const unitId = unitSelect.value;
    const manualFactor = manualFactorInput.value;
    
    if (!batchId || !unitId) {
        previewDiv.style.display = 'none';
        return;
    }
    
    try {
{% endblock %}