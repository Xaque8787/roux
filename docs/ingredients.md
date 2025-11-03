# Managing Ingredients

Ingredients are the foundation of your food cost tracking system. They represent the raw materials you purchase from vendors and use in your recipes.

## Overview

The Ingredients section allows you to:
- Track ingredient costs based on how you purchase them (by case, by weight, by volume, etc.)
- Convert between different units of measurement
- Organize ingredients by category
- View ingredient costs in multiple units for flexible recipe planning

## Accessing Ingredients

Navigate to **Ingredients** from the main navigation menu to view all ingredients in your system.

---

## Creating a New Ingredient

Click the **"Add New Ingredient"** button to create a new ingredient. You'll see a form with several sections:

### Basic Information

#### **Name**
- The name of the ingredient as you want it to appear throughout the system
- Example: "All-Purpose Flour", "Chicken Breast", "Olive Oil"
- **Used in**: Recipe ingredient selection, batch costing, inventory items

#### **Category**
- Organizes ingredients into logical groups
- Categories can have icons and colors for visual organization
- Example categories: Proteins, Produce, Dairy, Dry Goods, Spices
- **Used in**: Filtering ingredients, organizing inventory
- **Note**: Categories are shared across Ingredients, Recipes, Batches, Dishes, and Inventory

#### **Usage Type**
- Determines how the ingredient is measured when used in recipes
- **Options**:
  - **Weight**: For solid ingredients measured by weight (flour, meat, cheese)
  - **Volume**: For liquid ingredients or those measured by volume (milk, oil, sauces)
  - **Count**: For items used by count (eggs, lemons, whole chickens)
- **Impact**: Determines which unit conversion calculations are available

---

### Vendor Information

#### **Vendor**
- The supplier you purchase this ingredient from
- Helps track where ingredients come from
- **Used in**: Vendor reports, purchasing analysis
- **Note**: Vendors are managed in the Administration section

#### **Vendor Unit**
- How the vendor packages this ingredient
- Examples: "50 lb Bag", "Case of 6", "#10 Can", "Each"
- **Used in**: Purchase order communication, receiving verification
- **Note**: Vendor units are managed in the Administration section

---

### Purchase Information

This section defines how you buy the ingredient and determines cost calculations throughout the system.

#### **Purchase Type**
- **Single**: You buy one unit (one bag, one container, one item)
- **Case**: You buy a case containing multiple individual items

#### **Purchase Unit Name**
- A descriptive name for what you're purchasing
- Examples: "Case", "Bag", "Sack", "Box", "Container"
- **Impact**: Displayed in forms and reports to clarify what you're buying

#### **Purchase Total Cost**
- The total price you pay for the purchase (before tax)
- For a case, this is the cost of the entire case
- For a single item, this is the cost of that one item
- **Critical**: This is used to calculate all per-unit costs throughout the system

#### **Breakable Case** (Case purchases only)
- Whether you can open the case and use individual items
- **Checked**: You can break open the case (most common)
- **Unchecked**: The case must be used as a whole unit
- **Impact**: Determines if "item" is available as a unit in recipes

---

### Item-Level Information

This section defines the individual items within your purchase.

#### **Items Per Case** (Case purchases only)
- How many individual items are in one case
- Example: A case of tomato sauce might contain 6 individual cans
- **Used in**: Cost per item calculations, recipe measurements

#### **Item Weight/Volume**
- The total weight or volume of one individual item (including packaging)
- Example: One can weighs 32 oz including the can itself
- **Note**: This is gross weight/volume (with packaging)

#### **Net Weight/Volume (Item)**
- The usable weight or volume of ONE individual item
- This is what you actually use in recipes
- Example: One can contains 28 oz of usable sauce (after accounting for can weight)
- **Critical**: Used for recipe costing and unit conversions

#### **Net Weight/Volume (Case)** (Case purchases only)
- The total usable weight or volume of the ENTIRE case
- Can be calculated automatically (Net Item × Items Per Case)
- Or entered manually if the actual yield differs
- **Used in**: Bulk recipe calculations, cost per unit determination

#### **Net Unit**
- The unit of measurement for the net amounts
- Examples: oz, lb, g, kg (for weight) or fl_oz, cup, gal, ml, l (for volume)
- **Critical**: All recipe calculations are based on this unit
- **Must match**: Should align with your Usage Type (weight vs volume)

---

### Pricing Method

Choose how you want to calculate costs for this ingredient:

#### **Use Item Count Pricing**
- Check this if you want recipes to use whole items or fractions of items
- **Example Use Cases**:
  - Eggs (you use 2 eggs, not 4 oz of egg)
  - Cans of tomato sauce (you use 1 can, not 28 oz)
  - Lemons (you use 3 lemons, not 12 oz)
- **Available Units**: "item" and "case" (if breakable)
- **Cost Calculation**: Based on purchase total cost divided by item count

#### **Use Weight/Volume Pricing** (Default)
- Standard method where costs are calculated per unit of weight or volume
- **Example**: Cost per ounce, cost per pound, cost per gallon
- **Available Units**: All standard weight or volume units, plus baking measurements if configured
- **Cost Calculation**: Based on net weight/volume and purchase total cost

#### **Price Per Weight/Volume**
- An alternative input method where you enter the cost per unit directly
- Example: "$2.50 per pound" instead of calculating from total purchase cost
- **When to use**: If your vendor quotes prices by the unit rather than total cost
- **Note**: If left blank, costs are calculated from Purchase Total Cost

---

### Baking Measurements (Optional)

For dry ingredients commonly measured with measuring cups in baking.

#### **Has Baking Conversion**
- Enable this for ingredients like flour, sugar, cocoa powder
- Allows recipes to use measuring cups, tablespoons, teaspoons
- **Impact**: Adds baking units to available recipe units

#### **Baking Measurement Unit**
- The standard baking measurement for this ingredient
- Examples: cup, 1/2 cup, tbsp, tsp
- This is your "reference measurement"

#### **Baking Weight Amount** & **Baking Weight Unit**
- How much the ingredient weighs when measured in the baking measurement unit
- Example: 1 cup of all-purpose flour = 4.5 oz
- Example: 1 cup of granulated sugar = 7 oz
- **Used in**: Converting between volume measurements (cups) and weight (ounces)
- **Why needed**: Baking ingredients have different densities, so 1 cup of flour doesn't weigh the same as 1 cup of sugar

**Tip**: Look up standard baking weights online or use a kitchen scale to measure.

---

## Viewing Ingredient Details

Click on any ingredient name to view its full details including:

### Calculated Information
- **Cost per Item**: Automatically calculated based on purchase information
- **Total Item Count**: How many items you get per purchase
- **Cost per Unit**: Shows cost in all available units (per oz, per lb, per cup, etc.)

### Unit Conversions
- See costs in any compatible unit
- Weight ingredients show all weight units (oz, lb, g, kg)
- Volume ingredients show all volume units (fl_oz, cup, qt, gal, ml, l)
- Baking conversions shown if configured (cup, tbsp, tsp, and fractions)

### Usage Information
- **Used in Recipes**: Lists all recipes that use this ingredient
- **Used in Dishes**: Shows which menu items include this ingredient (via recipes)
- **Inventory Items**: If this ingredient is tracked in daily inventory

---

## Editing Ingredients

Click the **"Edit"** button on an ingredient detail page to modify its information.

**Important Notes**:
- Changing costs will affect all recipes and dishes using this ingredient
- Historical task labor data is not affected, but future cost calculations will use new values
- Consider the impact on existing menu pricing before making significant cost changes

---

## Deleting Ingredients

Click the **"Delete"** button on an ingredient detail page.

**Warning**:
- You cannot delete an ingredient that is currently used in any recipes
- Remove the ingredient from all recipes first, then delete
- This protects against accidentally breaking recipe calculations

---

## How Ingredients Connect to Other Parts

### Recipes
- Recipes use ingredients with specific quantities and units
- Recipe costs are calculated by multiplying ingredient quantities by their cost per unit
- When ingredient costs change, recipe costs automatically update

### Batches
- Batch costs are derived from the recipes they're based on
- Since recipes use ingredients, batch costs ultimately trace back to ingredient costs

### Dishes
- Dishes use portions of batches
- The ingredient costs flow through: Ingredient → Recipe → Batch → Dish
- This provides accurate menu item food costs

### Inventory Items
- Some ingredients may also be inventory items if you track them daily
- Inventory items can be linked to batches (for prepared items) or standalone
- Helps track usage and par levels for ingredients

---

## Best Practices

### Naming Conventions
- Use clear, descriptive names
- Include important details: "Chicken Breast (Boneless, Skinless)"
- Be consistent: "Olive Oil (Extra Virgin)" not sometimes "EVOO"

### Accurate Measurements
- Weigh your ingredients when setting up baking conversions
- Different brands may have slightly different densities
- Update costs regularly as prices change

### Categories
- Create logical categories that match your operation
- Use categories that will help with inventory organization
- Consider creating subcategories (e.g., "Dairy - Cheese", "Dairy - Milk")

### Vendor Information
- Keep vendor information current
- Track vendor units to match purchase orders
- Consider creating separate ingredient entries for the same product from different vendors if costs differ significantly

### Regular Updates
- Review ingredient costs monthly or when you receive invoices
- Update costs after price changes from vendors
- Check recipe costs after updating ingredients to assess menu price impacts

---

## Common Scenarios

### Scenario 1: Simple Weight-Based Ingredient
**Example**: All-Purpose Flour
- Purchase Type: Single
- Purchase Unit Name: Bag
- Purchase Total Cost: $18.50
- Net Weight: 50 lb
- Net Unit: lb
- Usage Type: Weight
- Enable Baking Conversions: Yes (1 cup = 4.5 oz)

**Result**: Can use in recipes as pounds, ounces, or cups

### Scenario 2: Case Purchase with Breakable Items
**Example**: Canned Tomatoes (#10 Can)
- Purchase Type: Case
- Items Per Case: 6
- Purchase Total Cost: $28.50
- Breakable Case: Yes
- Net Weight (Item): 102 oz
- Net Weight (Case): 612 oz (6 × 102)
- Net Unit: oz
- Usage Type: Weight

**Result**: Can use in recipes as whole cans or by ounces

### Scenario 3: Count-Based Ingredient
**Example**: Eggs
- Purchase Type: Case
- Items Per Case: 30
- Purchase Total Cost: $6.50
- Use Item Count Pricing: Yes
- Breakable Case: Yes

**Result**: Recipes can call for eggs by count (2 eggs, 3 eggs, etc.)

### Scenario 4: Liquid/Volume Ingredient
**Example**: Whole Milk
- Purchase Type: Single
- Purchase Unit Name: Gallon
- Purchase Total Cost: $4.25
- Net Volume: 1 gal
- Net Unit: gal
- Usage Type: Volume

**Result**: Can use in recipes as gallons, quarts, cups, fluid ounces, etc.

---

## Troubleshooting

### "Cost per unit seems wrong"
- Verify Purchase Total Cost is correct
- Check that Net Weight/Volume matches actual usable product
- Ensure Net Unit is appropriate for the Usage Type
- For cases, verify Items Per Case and that Net Weight (Case) is correct

### "Can't find the right unit in recipes"
- Check Usage Type (weight vs volume) matches how you want to use it
- For baking units, ensure "Has Baking Conversion" is enabled
- For count-based items, enable "Use Item Count Pricing"

### "Ingredient won't delete"
- Check if it's used in any recipes (view ingredient details to see list)
- Remove from all recipes first, then delete
- If still having issues, check if it's linked to inventory items

### "Baking conversions not working"
- Verify "Has Baking Conversion" is checked
- Ensure Baking Weight Amount and Unit are filled in
- Check that the Baking Weight Unit matches your Net Unit system (both weight-based)
- Example: Can't mix oz (weight) with fl_oz (volume)
