# Menu Items (Dishes)

Dishes represent the items you sell to customers. They combine portions of batches and direct ingredients to calculate accurate food costs and profit margins.

## Overview

The Dishes section allows you to:
- Build menu items using batch portions and direct ingredients
- Calculate accurate food costs including labor
- Set sale prices and view profit margins
- Compare estimated vs. actual costs
- Organize menu items by category

## Accessing Dishes

Navigate to **Dishes** from the main navigation menu to view all dishes in your system.

---

## Creating a New Dish

Click the **"Add New Dish"** button to create a new menu item.

### Basic Information

#### **Name**
- The name of the dish as it appears on your menu
- Be clear and descriptive
- Examples: "Classic Burger with Fries", "Margherita Pizza", "Caesar Salad"
- **Used in**: Menu planning, sales reports, profit analysis

#### **Category**
- Organizes dishes into logical menu groups
- Example categories: Appetizers, Entrees, Sides, Desserts, Beverages
- **Used in**: Menu organization, sales analysis, filtering
- **Note**: Categories are shared across Ingredients, Recipes, Batches, Dishes, and Inventory

#### **Sale Price**
- What you charge customers for this dish
- Enter as decimal (15.99, not $15.99)
- **Critical**: Used to calculate profit margins and food cost percentages
- **Tip**: Consider cost + desired margin, competitor pricing, perceived value

#### **Description**
- Optional description for internal use or menu printing
- Include special notes: allergens, preparation method, serving size
- Can be used for training or menu descriptions

---

## Adding Batch Portions to a Dish

Batch portions are the primary way to build dishes. They represent components you've prepared using batches.

Click **"Add Batch Portion"** to include part of a batch:

### Batch Selection

#### **Batch**
- Choose from your existing batches
- Shows batch name and recipe for clarity
- **Note**: The batch must exist first in the Batches section

### Portion Method

Choose how you want to specify how much of the batch to use:

#### **Option 1: Portion Size (Amount-Based)**
Use this when you want to specify an exact amount from the batch.

##### **Portion Size**
- Enter the amount (e.g., 6, 8, 12)
- Numeric value representing quantity
- Example: 6 oz, 8 fl_oz, 1 item

##### **Portion Unit**
- Select the unit that matches your portion size
- Must be compatible with the batch's yield unit
- Example: If batch yields in oz, use oz, lb, or g
- **Available units**: Depend on batch yield unit and usage type

##### **How it calculates cost**:
Formula: `(Portion Size ÷ Batch Yield) × Total Batch Cost`

**Example**:
- Batch yields: 128 oz
- Batch total cost: $45.00
- Your portion: 6 oz
- Calculation: (6 ÷ 128) × $45.00 = $2.11

#### **Option 2: Recipe Portion Percent**
Use this when you want to use a specific fraction of the entire batch.

##### **Use Recipe Portion** (checkbox)
- Check this to enable percentage-based portioning
- Useful for items where you always use a fixed percentage

##### **Recipe Portion Percent**
- Enter as decimal (0.125 = 12.5%, 0.25 = 25%, 0.5 = 50%)
- Represents what fraction of the entire batch this dish uses
- **When to use**:
  - Variable yield batches
  - When the actual amount varies but ratio stays constant
  - Pizza slices (1/8 of a pizza = 0.125)

##### **How it calculates cost**:
Formula: `Recipe Portion Percent × Total Batch Cost`

**Example**:
- Batch total cost: $45.00
- Your portion: 0.25 (25%)
- Calculation: 0.25 × $45.00 = $11.25

### Cost Breakdown for Batch Portions

Each batch portion contributes two types of costs:

#### **Recipe Cost**
- The proportional cost of all ingredients in the batch
- Includes any sub-batches used in the batch's recipe
- Updates automatically when ingredient prices change

#### **Labor Cost**
- The proportional labor cost from the batch
- Can be calculated using different methods (see Cost Analysis below)
- Default uses estimated labor cost

**Total Batch Portion Cost** = Recipe Cost + Labor Cost

---

## Adding Direct Ingredient Portions

You can also add ingredients directly to dishes (not through batches). Use this for:
- Simple garnishes
- Fresh components not pre-batched
- Items used in small quantities
- Finishing touches

Click **"Add Ingredient Portion"** to add a direct ingredient:

### Ingredient Selection

#### **Ingredient**
- Choose from your tracked ingredients
- Only ingredients you've created in the Ingredients section
- **Note**: Most dishes primarily use batch portions; direct ingredients are supplementary

#### **Quantity**
- How much of this ingredient the dish uses
- Enter as decimal (0.5, 1.0, 2.5, etc.)

#### **Unit**
- Select unit compatible with the ingredient's usage type
- Available units depend on ingredient configuration
- Weight ingredients: oz, lb, g, kg
- Volume ingredients: fl_oz, cup, qt, gal, ml, l
- Count ingredients: item, case

### Cost Calculation
Formula: `Quantity × Ingredient Cost Per Unit`

**Example**:
- Ingredient: Fresh Parsley
- Cost per oz: $0.45
- Quantity: 0.25 oz
- Calculation: 0.25 × $0.45 = $0.11

---

## Viewing Dish Details

Click on any dish name to view full details and cost analysis:

### Cost Analysis

The system provides multiple cost calculation methods:

#### **Expected Cost (Estimated Labor)**
- Uses batch estimated labor costs
- Based on labor time and rate defined in batches
- **Best for**: Planning, initial pricing, budgeting
- **Formula**: Recipe costs + Estimated labor costs

#### **Actual Cost (Most Recent Labor)**
- Uses actual labor cost from most recent completed task for each batch
- Real production data from latest run
- **Best for**: Current cost tracking, immediate cost control
- **Formula**: Recipe costs + Most recent actual labor costs

#### **Actual Cost (Week Average Labor)**
- Uses average labor cost from tasks completed in last 7 days
- Smooths out daily variations
- **Best for**: Short-term cost trends, weekly specials pricing
- **Formula**: Recipe costs + Week average labor costs

#### **Actual Cost (Month Average Labor)**
- Uses average labor cost from tasks completed in last 30 days
- Broader view of cost trends
- **Best for**: Menu pricing reviews, monthly cost analysis
- **Formula**: Recipe costs + Month average labor costs

#### **Actual Cost (All-Time Average Labor)**
- Uses average of all completed tasks ever
- Long-term historical average
- **Best for**: Established items, long-term pricing strategy
- **Formula**: Recipe costs + All-time average labor costs

### Profitability Metrics

For each cost calculation method, the system shows:

#### **Food Cost Percentage**
Formula: `(Total Food Cost ÷ Sale Price) × 100`

**Example**:
- Sale Price: $15.99
- Total Food Cost: $4.25
- Food Cost %: (4.25 ÷ 15.99) × 100 = 26.6%

**Target Ranges** (industry guidelines):
- Fine Dining: 25-35%
- Casual Dining: 28-35%
- Fast Casual: 25-30%
- QSR/Fast Food: 25-30%
- High Volume: 30-40%

#### **Profit Margin**
Formula: `Sale Price - Total Food Cost`

**Example**:
- Sale Price: $15.99
- Total Food Cost: $4.25
- Profit Margin: $15.99 - $4.25 = $11.74

**Note**: This is gross profit before other costs (labor for service, overhead, etc.)

#### **Markup**
Formula: `(Sale Price ÷ Total Food Cost) × 100`

**Example**:
- Sale Price: $15.99
- Total Food Cost: $4.25
- Markup: (15.99 ÷ 4.25) × 100 = 376%

**Common Markups**:
- 2x markup = 50% food cost
- 3x markup = 33% food cost
- 4x markup = 25% food cost

### Component Breakdown

#### **Batch Portions List**
- Each batch portion with size, cost breakdown
- Shows recipe cost and labor cost separately
- Click batch name to view batch details
- Indicates if using percentage or amount-based portioning

#### **Direct Ingredient Portions List**
- Each ingredient with quantity, unit, and cost
- Click ingredient name to view ingredient details
- Shows current cost (updates with ingredient price changes)

#### **Total Costs Summary**
- **Total Recipe Cost**: Sum of all recipe costs from batch portions
- **Total Labor Cost**: Sum of all labor costs (varies by calculation method)
- **Direct Ingredient Cost**: Sum of all direct ingredient costs
- **Grand Total**: Recipe + Labor + Direct Ingredients

---

## Editing Dishes

Click the **"Edit"** button on a dish detail page to modify:
- Basic information (name, category, description, sale price)
- Add, remove, or modify batch portions
- Add, remove, or modify ingredient portions
- Adjust quantities, units, or portioning methods

**Important Notes**:
- Changes to sale price affect profit margins immediately
- Changes to portions affect food costs
- Costs update in real-time based on current ingredient and batch costs
- Consider impact on menu pricing before making significant changes

---

## Deleting Dishes

Click the **"Delete"** button on a dish detail page.

**Note**:
- Dishes can typically be deleted without dependencies
- No other parts of the system depend on dishes
- Historical sales data is not affected by deletion
- Use caution as deletion is permanent

---

## How Dishes Connect to Other Parts

### Batches
- Dishes are built primarily from batch portions
- Batch costs (recipe + labor) determine dish food costs
- The cost flow: Batches → Dishes → Sale Price → Profit

### Recipes
- Dishes indirectly use recipes through batches
- Changes to recipes affect batch costs, which affect dish costs
- The complete flow: Ingredients → Recipes → Batches → Dishes

### Ingredients
- Dishes can use ingredients directly (without batches)
- Ingredients are also used indirectly through batches/recipes
- When ingredient prices change, dish costs update automatically

### Tasks
- Completed tasks provide actual labor data for batches
- This data is used in dish cost calculations
- More completed tasks = more accurate dish costing

### Categories
- Organizes dishes into menu sections
- Same category system used across entire application
- Helps with menu planning and analysis

---

## Best Practices

### Pricing Strategy

#### Initial Pricing
1. Calculate expected cost (with estimated labor)
2. Determine target food cost percentage (usually 25-35%)
3. Calculate initial sale price: `Food Cost ÷ Target Food Cost %`
4. Round to psychologically appealing price ($15.99 not $15.87)
5. Consider perceived value and competition

#### Price Monitoring
- Review actual costs weekly or monthly
- Compare expected vs actual costs
- Identify items with high cost variance
- Adjust prices when actual costs consistently exceed estimates

#### Menu Engineering
- Track food cost % for all dishes
- Identify high-cost items (> 35% food cost)
- Consider: increase price, reduce portion, or remove item
- Balance menu with different margin items

### Portioning Consistency

#### Amount-Based Portioning
- Use for items with fixed portions (6 oz of protein, 8 oz of sauce)
- Easier for kitchen staff to execute consistently
- Better cost control with proper training
- Use kitchen scales or portion tools

#### Percentage-Based Portioning
- Use for variable yield batches
- Good for items naturally divided (pizza slices, cake slices)
- Ensures consistent cost percentage even if yield varies

#### Documentation
- Document standard portion sizes
- Include photos or examples
- Train staff on proper portioning
- Regular audits to ensure compliance

### Cost Control

#### Track Variances
- Compare estimated vs actual costs regularly
- Investigate large variances (>10%)
- Common causes: portioning errors, ingredient waste, recipe not followed

#### Update Regularly
- Review ingredient costs monthly
- Update sale prices when costs change significantly
- Monitor food cost % trends
- Adjust portions if needed to maintain margins

#### Optimize Components
- Review which batches contribute most to cost
- Can expensive batches be modified?
- Look for ingredient substitutions
- Consider seasonal ingredients

---

## Common Scenarios

### Scenario 1: Simple Plated Dish
**Example**: Grilled Chicken with Vegetables
- **Batch Portions**:
  - 8 oz Marinated Chicken Breast (from batch)
  - 6 oz Roasted Vegetables (from batch)
  - 2 oz Herb Butter (from batch)
- **Direct Ingredients**:
  - 0.1 oz Fresh Parsley (garnish)
- **Sale Price**: $18.99
- **Total Cost**: $5.25
- **Food Cost %**: 27.6%

**Result**: Well-balanced dish with good profit margin

### Scenario 2: Composed Dish with Multiple Components
**Example**: Pasta Primavera
- **Batch Portions**:
  - 12 oz Fresh Pasta (from batch)
  - 8 oz Primavera Vegetables (from batch)
  - 4 oz Cream Sauce (from batch)
  - 1 oz Parmesan Crisp (from batch)
- **Sale Price**: $16.99
- **Total Cost**: $4.85
- **Food Cost %**: 28.5%

**Result**: Multiple prep components come together in one dish

### Scenario 3: Pizza Using Percentage Portioning
**Example**: Margherita Pizza (Individual)
- **Batch Portions**:
  - 0.125 (12.5%) of Pizza Dough batch (1 dough ball from 8-ball batch)
  - 0.125 of Tomato Sauce batch (portion for 1 pizza from 8-pizza batch)
  - 0.125 of Mozzarella Prep batch
- **Direct Ingredients**:
  - 0.25 oz Fresh Basil
- **Sale Price**: $14.99

**Result**: Percentage-based portioning perfect for evenly-divided items

### Scenario 4: High-End Dish with Multiple Proteins
**Example**: Surf & Turf
- **Batch Portions**:
  - 8 oz Beef Tenderloin (from batch)
  - 6 oz Lobster Tail (from batch)
  - 4 oz Béarnaise Sauce (from batch)
  - 6 oz Roasted Asparagus (from batch)
  - 4 oz Duchess Potatoes (from batch)
- **Direct Ingredients**:
  - 0.5 oz Microgreens
  - 0.25 oz Edible Flowers
- **Sale Price**: $54.99
- **Total Cost**: $18.75
- **Food Cost %**: 34.1%

**Result**: Higher food cost acceptable for premium dish with higher profit margin

---

## Troubleshooting

### "Food cost percentage too high"
- **Target**: Most items should be 25-35% food cost
- **Solutions**:
  - Increase sale price
  - Reduce portion sizes
  - Use less expensive ingredients/batches
  - Improve batch yields to lower batch costs
  - Verify portioning is accurate (over-portioning increases cost)

### "Actual cost much different than expected"
- Check actual labor costs vs estimated labor costs for batches
- Review recent task completions for the batches used
- Verify ingredient prices haven't changed significantly
- Check if portions are being measured correctly
- Use month average instead of most recent for more stability

### "Can't find batch in dropdown"
- Batch must be created first in Batches section
- Check that batch still exists and hasn't been deleted
- Refresh the page if you just created the batch
- Verify you're looking for the right batch name

### "Units not compatible"
- Portion unit must be compatible with batch yield unit
- Weight batches: use weight units (oz, lb, g, kg)
- Volume batches: use volume units (fl_oz, cup, qt, gal, ml, l)
- Count batches: use count units (item, case)
- Cannot mix unit types (can't use oz with a gallon-yielding batch)

### "Profit margin seems low"
- Check food cost percentage (should be 25-35% for most operations)
- If food cost is appropriate, profit margin depends on sale price
- Consider raising prices if margin doesn't cover other costs
- Remember: food cost % is only one part of total costs
- Must also cover: labor, rent, utilities, overhead, profit

### "Costs keep changing"
- Expected: costs update when ingredient prices change
- This is a feature - you see real-time cost impact of price changes
- Use actual cost methods (week/month average) for more stability
- Set up regular menu price reviews
- Build price increases into menu design

---

## Advanced Topics

### Menu Engineering Matrix

Categorize dishes into four quadrants:

#### **Stars** (High Profit, High Popularity)
- Food Cost %: Low (< 30%)
- Sales: High
- **Strategy**: Promote heavily, maintain quality, don't change

#### **Plowhorses** (Low Profit, High Popularity)
- Food Cost %: High (> 35%)
- Sales: High
- **Strategy**: Increase prices carefully, reduce portions slightly, improve yields

#### **Puzzles** (High Profit, Low Popularity)
- Food Cost %: Low (< 30%)
- Sales: Low
- **Strategy**: Improve presentation, reposition on menu, add descriptive text, better promotion

#### **Dogs** (Low Profit, Low Popularity)
- Food Cost %: High (> 35%)
- Sales: Low
- **Strategy**: Remove from menu, dramatic changes needed if keeping

### Dynamic Pricing

Use cost data to implement dynamic pricing:
- Seasonal pricing based on ingredient costs
- Specials based on low-cost inventory
- Happy hour items with lower margins
- Premium pricing for high-cost ingredients

### Cost Scenario Analysis

Compare different costing methods:
- **Expected vs Actual**: Are estimates accurate?
- **Week vs Month**: Are costs trending up or down?
- **Most Recent vs Average**: How much variance between runs?

**Action Items**:
- High variance: Improve process consistency
- Rising trend: Consider price increases
- Actual >> Expected: Update estimates or improve efficiency

### Contribution Margin

Calculate each dish's contribution to fixed costs:
- **Formula**: `(Sale Price - Variable Costs) × Units Sold`
- Variable costs include food cost + preparation labor
- Fixed costs include rent, salaried labor, utilities
- **Use**: Prioritize high-contribution items in menu design

### Ideal vs Theoretical Food Cost

- **Theoretical**: Based on recipes and portions (what system shows)
- **Actual**: Based on purchases and sales (from accounting)
- **Variance**: Theoretical - Actual
- **Common causes of variance**: Waste, theft, over-portioning, spoilage

**System provides theoretical cost; compare to actual regularly**

### Multi-Stage Value Addition

Track value added at each stage:
1. **Ingredients**: Raw cost
2. **Batches**: + Prep labor
3. **Dishes**: + Assembly/cooking labor + presentation
4. **Service**: + Front-of-house labor + experience
5. **Sale Price**: Final value to customer

Each stage adds cost and value, justifying final price.
