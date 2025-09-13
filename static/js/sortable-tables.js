/**
 * Sortable Tables JavaScript
 * Makes Bootstrap tables sortable by clicking column headers
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Sortable tables script loaded');
    
    // Find all tables with sortable class
    const sortableTables = document.querySelectorAll('.table-sortable');
    console.log('Found sortable tables:', sortableTables.length);
    
    sortableTables.forEach(table => {
        initializeSortableTable(table);
    });
});

function initializeSortableTable(table) {
    const headers = table.querySelectorAll('thead th[data-sortable]');
    console.log('Found sortable headers:', headers.length);
    
    headers.forEach((header, index) => {
        // Add sorting indicator
        header.style.cursor = 'pointer';
        header.style.userSelect = 'none';
        header.innerHTML += ' <i class="fas fa-sort text-muted sort-icon"></i>';
        
        // Add click event
        header.addEventListener('click', function() {
            console.log('Sorting column:', index);
            sortTable(table, index, header);
        });
    });
}

function sortTable(table, columnIndex, header) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const sortType = header.getAttribute('data-sort-type') || 'text';
    const currentDirection = header.getAttribute('data-sort-direction') || 'asc';
    const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
    
    console.log('Sorting:', sortType, 'direction:', newDirection);
    
    // Clear all other sort indicators
    table.querySelectorAll('thead th .sort-icon').forEach(icon => {
        icon.className = 'fas fa-sort text-muted sort-icon';
    });
    
    // Update current header sort indicator
    const sortIcon = header.querySelector('.sort-icon');
    if (newDirection === 'asc') {
        sortIcon.className = 'fas fa-sort-up text-primary sort-icon';
    } else {
        sortIcon.className = 'fas fa-sort-down text-primary sort-icon';
    }
    
    header.setAttribute('data-sort-direction', newDirection);
    
    // Sort rows
    rows.sort((a, b) => {
        const aCell = a.cells[columnIndex];
        const bCell = b.cells[columnIndex];
        
        let aValue = getCellValue(aCell, sortType);
        let bValue = getCellValue(bCell, sortType);
        
        // Handle different sort types
        if (sortType === 'number') {
            aValue = parseFloat(aValue) || 0;
            bValue = parseFloat(bValue) || 0;
        } else if (sortType === 'currency') {
            aValue = parseCurrency(aValue);
            bValue = parseCurrency(bValue);
        } else if (sortType === 'date') {
            aValue = new Date(aValue);
            bValue = new Date(bValue);
        } else {
            // Text sorting - case insensitive
            aValue = aValue.toLowerCase();
            bValue = bValue.toLowerCase();
        }
        
        if (aValue < bValue) {
            return newDirection === 'asc' ? -1 : 1;
        }
        if (aValue > bValue) {
            return newDirection === 'asc' ? 1 : -1;
        }
        return 0;
    });
    
    // Re-append sorted rows
    rows.forEach(row => tbody.appendChild(row));
}

function getCellValue(cell, sortType) {
    // Get the text content, but handle special cases
    let value = cell.textContent.trim();
    
    // Handle badges and icons - extract just the text
    const strongElement = cell.querySelector('strong');
    if (strongElement && sortType === 'text') {
        value = strongElement.textContent.trim();
    }
    
    // Handle category columns with icons
    if (value.match(/^[\u{1F000}-\u{1F9FF}]/u)) {
        // Remove emoji from the beginning
        value = value.replace(/^[\u{1F000}-\u{1F9FF}\s]+/u, '').trim();
    }
    
    // Handle multi-line content - use first line
    if (value.includes('\n')) {
        value = value.split('\n')[0].trim();
    }
    
    return value;
}

function parseCurrency(value) {
    // Extract numeric value from currency strings like "$1.23"
    const match = value.match(/\$?([0-9,]+\.?[0-9]*)/);
    return match ? parseFloat(match[1].replace(/,/g, '')) : 0;
}

// Add CSS for sortable headers
const style = document.createElement('style');
style.textContent = `
    .table-sortable thead th[data-sortable] {
        position: relative;
        cursor: pointer;
        user-select: none;
    }
    
    .table-sortable thead th[data-sortable]:hover {
        background-color: #f8f9fa;
    }
    
    .sort-icon {
        margin-left: 5px;
        font-size: 0.8em;
    }
`;
document.head.appendChild(style);