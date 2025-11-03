# Creating Recipes

Recipes are collections of ingredients with specific quantities and preparation instructions. They serve as the foundation for production batches and help you understand the true cost of what you're making.

## Overview

The Recipes section allows you to:
- Build recipes using your tracked ingredients
- Calculate accurate recipe costs based on current ingredient prices
- Organize recipes by category
- Create complex recipes that include portions of other batches
- View recipe details including total cost and cost per unit

## Accessing Recipes

Navigate to **Recipes** from the main navigation menu to view all recipes in your system.

---

## Creating a New Recipe

Click the **"Add New Recipe"** button to create a new recipe.

### Basic Information

#### **Name**
- The name of the recipe as you want it to appear throughout the system
- Be descriptive and specific
- Examples: "House Marinara Sauce", "Chocolate Chip Cookie Dough", "Roasted Chicken Stock"
- **Used in**: Batch creation, reports, task assignments

#### **Category**
- Organizes recipes into logical groups
- Example categories: Sauces, Baked Goods, Stocks, Prep Items, Desserts
- **Used in**: Filtering recipes, organizing production schedules
- **Note**: Categories are shared across Ingredients, Recipes, Batches, Dishes, and Inventory

#### **Instructions**
- Step-by-step preparation instructions
- Write as you would for a cook to follow
- Include important details: temperatures, times, techniques
- Can include mixing order, resting times, finishing steps
- **Used in**: Production tasks, training, quality control
- **Tip**: Format with line breaks for readability

---

## Adding Ingredients to a Recipe

After creating the basic recipe information, you'll add the ingredients that make up the recipe.

Click **"Add Ingredient"** to add each ingredient:

#### **Ingredient Selection**
- Choose from your list of tracked ingredients
- Only shows ingredients you've already created
- Searchable dropdown for easy finding
- **Note**: You must create the ingredient first in the Ingredients section

#### **Quantity**
- How much of this ingredient the recipe uses
- Enter as a decimal number (1.5, 0.25, 2.0, etc.)
- **Important**: This is the NET quantity you actually use in the recipe

#### **Unit**
- Select the unit that matches your quantity
- Available units depend on the ingredient's configuration:
  - **Weight ingredients**: oz, lb, g, kg
  - **Volume ingredients**: fl_oz, cup, qt, gal, ml, l
  - **Count ingredients**: item, case (if breakable)
  - **Baking ingredients**: Also includes cup, tbsp, tsp, and fractions
- **Tip**: Choose units that make sense for your kitchen workflow

### Cost Calculation
- The cost for each ingredient line is calculated automatically
- Formula: `Quantity × Ingredient Cost Per Unit`
- Costs update automatically when ingredient prices change
- **Total Recipe Cost**: Sum of all ingredient costs

---

## Adding Batch Portions to a Recipe

Recipes can include portions of other batches as ingredients. This is useful for complex, multi-stage preparations.

### When to Use Batch Portions

**Example Scenarios**:
- A soup recipe that uses a batch of pre-made stock
- A finished dish that uses a batch of sauce
- A dessert that uses a batch of pastry cream
- A sandwich that uses a batch of roasted vegetables

### Adding a Batch Portion

Click **"Add Batch Portion"** to include part of a batch in your recipe:

#### **Batch Selection**
- Choose from your existing batches
- The batch's recipe name is shown for clarity
- **Note**: The batch must be created first in the Batches section

#### **Portion Method**

Choose how you want to specify how much of the batch to use:

##### **Option 1: Portion Size (Amount-Based)**
Use this when you want to specify an exact amount from the batch.

- **Portion Size**: Enter the amount (e.g., 16)
- **Portion Unit**: Select the unit (e.g., oz, cup, lb)
- **How it works**: System calculates what percentage of the batch you're using based on the batch's yield
- **Example**: Your batch makes 128 oz. Your recipe uses 16 oz. That's 1/8 of the batch (12.5%)

##### **Option 2: Recipe Portion Percent**
Use this when you want to use a specific fraction of the entire batch.

- Check **"Use Recipe Portion"**
- **Recipe Portion Percent**: Enter as decimal (0.5 = 50%, 0.25 = 25%, 0.125 = 12.5%)
- **How it works**: System uses exactly this percentage regardless of yield amount
- **When to use**: Variable yield batches or when you always want to use the same proportion

### Cost Calculation for Batch Portions

The cost of a batch portion includes:
1. **Recipe Cost**: The proportional cost of all ingredients in the batch's recipe
2. **Labor Cost**: The proportional estimated labor cost from the batch

Formula depends on method:
- **Portion Size**: `(Portion Size ÷ Batch Yield) × Total Batch Cost`
- **Recipe Portion**: `Recipe Portion Percent × Total Batch Cost`

---

## Viewing Recipe Details

Click on any recipe name to view its full details:

### Information Displayed

#### **Recipe Cost Summary**
- **Total Ingredient Cost**: Sum of all ingredient costs
- **Total Batch Portion Cost**: Sum of all batch portion costs (if any)
- **Total Recipe Cost**: Combined total
- **Cost per Unit**: If the recipe has a linked batch with a defined yield

#### **Ingredients List**
- Each ingredient with quantity, unit, and cost
- Click ingredient name to view ingredient details
- Shows current cost (updates when ingredient prices change)

#### **Batch Portions List** (if any)
- Each batch portion with size/percentage and cost
- Click batch name to view batch details
- Shows current cost (updates when batch costs change)

#### **Instructions**
- Full preparation instructions
- Formatted for easy reading

#### **Used In**
- **Batches**: Lists all batches based on this recipe
- **Impact**: Helps understand how recipe changes affect production

---

## Editing Recipes

Click the **"Edit"** button on a recipe detail page to modify:
- Basic information (name, category, instructions)
- Add, remove, or modify ingredients
- Add, remove, or modify batch portions
- Adjust quantities or units

**Important Notes**:
- Changes to ingredient quantities will affect recipe cost
- Changes will affect all batches using this recipe
- Existing completed tasks are not affected, but future cost calculations will use new values

---

## Deleting Recipes

Click the **"Delete"** button on a recipe detail page.

**Warning**:
- You cannot delete a recipe that has batches attached to it
- You must delete all batches using this recipe first
- This protects against accidentally breaking batch calculations

---

## How Recipes Connect to Other Parts

### Ingredients
- Recipes specify exactly which ingredients are needed and in what quantities
- Recipe costs are calculated from ingredient costs
- When ingredient prices change, recipe costs automatically update

### Batches
- Every batch is based on one recipe
- The batch defines how much the recipe yields and how long it takes to make
- Batches make recipes "producible" with yields and labor costs

### Dishes
- Dishes use portions of batches (which are based on recipes)
- This creates the cost flow: Recipe → Batch → Dish → Menu Price
- Allows accurate profit margin calculations

### Tasks
- When production tasks are created for batches, the recipe instructions guide the work
- Workers can reference recipe instructions while completing tasks
- Recipe costs are used in task completion calculations

### Batch Portions in Recipes
- Creates multi-level recipe structures
- Allows component-based cooking (make stock, then use in soup)
- Each level calculates costs accurately including labor

---

## Best Practices

### Recipe Organization

#### Naming
- Use descriptive, searchable names
- Include key characteristics: "Marinara Sauce (House Blend)"
- Be consistent with naming conventions
- Avoid abbreviations unless universally understood

#### Categories
- Group similar recipes together
- Consider your production flow when creating categories
- Examples: "Stocks & Bases", "Sauces - Hot", "Sauces - Cold", "Bread & Dough"

### Ingredient Quantities

#### Accuracy
- Weigh ingredients during recipe development
- Use consistent units across similar recipes
- Round to practical measurements (0.25, 0.5, 0.75 instead of 0.33)
- Consider kitchen equipment (if your measure only goes to 0.5 oz, don't specify 0.3 oz)

#### Unit Selection
- Use units that make sense for the kitchen
- Volume for liquids in small amounts (cups, fl_oz)
- Weight for solids and large amounts (lb, oz)
- Count for whole items (eggs, cans)

### Instructions

#### Clarity
- Write instructions as if training a new cook
- Include critical details: temperatures, times, visual cues
- Break into clear steps
- Mention special equipment needed

#### Format
- Use line breaks between major steps
- Number complex procedures
- Include holding instructions if applicable
- Note critical control points (food safety temperatures)

### Recipe Development

#### Testing
- Test recipes before adding to the system
- Verify quantities and yields
- Confirm instructions are complete and accurate
- Check that the ingredient units work in your kitchen

#### Costing
- Review total recipe cost after creation
- Compare to expected cost if you were already making this
- Investigate if costs seem too high or low
- Verify ingredient units are correct if costs are unexpected

---

## Common Scenarios

### Scenario 1: Simple Recipe with Only Ingredients
**Example**: House Vinaigrette
- 2 cups Olive Oil (Extra Virgin)
- 0.5 cup Red Wine Vinegar
- 1 tbsp Dijon Mustard
- 1 tbsp Honey
- 0.25 oz Salt
- 0.125 oz Black Pepper

**Result**: Simple ingredient-only recipe with automatic cost calculation

### Scenario 2: Recipe Using Batch Portions
**Example**: French Onion Soup
- **Ingredients**:
  - 3 lb Yellow Onions
  - 2 oz Butter
  - 0.25 oz Salt
  - 0.125 oz Black Pepper
- **Batch Portions**:
  - 64 fl_oz of "Beef Stock" batch
  - 8 oz of "Gruyere Cheese Mix" batch

**Result**: Recipe that combines fresh ingredients with pre-made components

### Scenario 3: Variable Ratio Recipe Component
**Example**: Sauce Reduction (used in multiple dishes)
- You always want to use 25% of the batch
- Use Recipe Portion: 0.25
- Doesn't matter if batch yields 32 oz or 48 oz
- Always uses exactly 1/4 of whatever is made

**Result**: Flexible component that works with variable yields

### Scenario 4: Multi-Stage Production
**Example**: Layered Dessert
- **Step 1**: Create "Chocolate Cake Layers" recipe → batch
- **Step 2**: Create "Chocolate Buttercream" recipe → batch
- **Step 3**: Create "Chocolate Ganache" recipe → batch
- **Step 4**: Create "Assembled Chocolate Cake" recipe using portions of all three batches

**Result**: Complex multi-component product with accurate total costing

---

## Troubleshooting

### "Recipe cost seems wrong"
- Check each ingredient's cost per unit (click to view ingredient details)
- Verify ingredient quantities are correct
- Ensure units are appropriate (using oz when you meant lb?)
- For batch portions, check that the batch's recipe costs are correct
- Trace costs backward: Recipe → Batch → Recipe → Ingredients

### "Can't find an ingredient in the dropdown"
- The ingredient must be created first in the Ingredients section
- Check spelling (search is case-insensitive)
- Verify the ingredient exists and hasn't been deleted

### "Unit not available for ingredient"
- Check the ingredient's Usage Type (weight, volume, or count)
- For baking units, verify "Has Baking Conversion" is enabled on the ingredient
- For count-based, verify "Use Item Count Pricing" is enabled on the ingredient
- Weight and volume units cannot be mixed

### "Can't delete recipe"
- Check if any batches use this recipe
- View recipe details to see "Used In Batches" section
- Delete or reassign batches first, then delete the recipe

### "Batch not showing in batch portion dropdown"
- The batch must be created first in the Batches section
- Check that the batch still exists and hasn't been deleted
- Refresh the page if you just created the batch

### "Batch portion cost seems off"
- Verify the batch has a defined yield (amount and unit)
- Check that your portion size uses compatible units
- For percentage-based portions, confirm the percentage is entered as a decimal (0.25 not 25)
- Review the batch's recipe to ensure its ingredient costs are correct

---

## Advanced Topics

### Circular Dependencies
**Important**: The system prevents circular dependencies.
- You cannot add a batch portion that would create a loop
- Example: Recipe A → Batch A → Recipe B → Batch B → Recipe A ❌
- The system will prevent adding the final batch portion that would complete the circle

### Recipe Scaling
- Recipes themselves don't have scaling factors
- Scaling is handled at the Batch level
- This allows one recipe to be made at different scales for different purposes

### Historical Costs vs Current Costs
- Recipe costs always use CURRENT ingredient prices
- This means recipe costs can change over time as ingredient prices change
- Completed tasks store historical labor and batch costs, but recipe costs are always live
- Use this information to identify when menu prices need adjustment

### Recipe Versioning
- The system doesn't have built-in recipe versioning
- If you need to change a recipe significantly, consider:
  - Creating a new recipe with a version in the name: "Marinara Sauce v2"
  - Updating the instructions to note the change date
  - Keeping notes in the instructions about what changed and why
