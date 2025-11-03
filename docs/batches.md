# Production Batches

Batches turn recipes into producible items by defining yields, labor requirements, and scaling options. They represent the actual production runs you do in your kitchen.

## Overview

The Batches section allows you to:
- Convert recipes into production items with defined yields
- Calculate labor costs based on time and wages
- Enable batch scaling for different production sizes
- Track historical labor performance
- View total costs including ingredients and labor

## Accessing Batches

Navigate to **Batches** from the main navigation menu to view all batches in your system.

---

## Creating a New Batch

Click the **"Add New Batch"** button to create a new batch.

### Basic Information

#### **Recipe**
- Select the recipe this batch is based on
- **Required**: Every batch must have a recipe
- The recipe determines what ingredients are needed and base costs
- **Note**: Recipe costs update automatically when ingredient prices change

#### **Category**
- Organizes batches into logical groups
- Can be the same or different from the recipe's category
- Example categories: Sauces, Baked Goods, Prep Items, Stocks, Desserts
- **Used in**: Production planning, filtering batches, inventory organization
- **Note**: Categories are shared across Ingredients, Recipes, Batches, Dishes, and Inventory

---

### Yield Information

This section defines how much the batch produces.

#### **Variable Yield**
- Check this if the batch doesn't produce a consistent amount
- **When to use**:
  - Reduction sauces where final volume varies
  - Items where yield depends on raw ingredient quality
  - Any production where you can't predict exact output
- **Impact**:
  - Tasks for variable yield batches REQUIRE entering the actual made amount
  - Cost per unit cannot be calculated until actual yield is recorded
  - Allows tracking of actual yields over time

#### **Yield Amount** (Fixed yield only)
- How much this batch produces
- Enter as a decimal number
- Examples: 128 (oz), 5 (qt), 24 (portions)
- **Used in**: Cost per unit calculations, portioning for dishes, task tracking

#### **Yield Unit** (Fixed yield only)
- The unit of measurement for the yield
- Should match how you'll use this batch in dishes or inventory
- Examples: oz, lb, gal, cup, qt, item, portion
- **Impact**: Determines what units can be used when portioning for dishes

---

### Labor Information

This section defines the labor cost for producing this batch.

#### **Estimated Labor Minutes**
- How long it takes to make this batch from start to finish
- Include all steps: prep, cooking, cooling, cleanup
- Be realistic - track actual time and update as needed
- **Used in**: Labor cost calculations, production scheduling

#### **Hourly Labor Rate**
- The labor cost per hour for making this batch
- Default is typically set system-wide but can be customized per batch
- Use the highest wage if multiple people work on it
- Can be based on:
  - Specific employee wage
  - Blended kitchen wage
  - Position wage (prep cook, line cook, pastry chef)
- **Used in**: Calculating estimated and actual labor costs

#### **Calculated Labor Cost** (displayed, not editable)
- Automatically calculated: `(Estimated Labor Minutes ÷ 60) × Hourly Labor Rate`
- This is your estimated labor cost for planning purposes
- **Used in**: Dish costing, menu pricing, profit margin calculations

---

### Scaling Options

This section determines if and how the batch can be scaled.

#### **Can Be Scaled**
- Check this to enable scaling options
- Allows making larger or smaller versions of the batch
- **When to use**: Recipes that can be reliably multiplied or divided
- **Impact**: Tasks can select different scale factors

#### **Available Scale Factors**

When "Can Be Scaled" is enabled, check which scales are appropriate:

##### **Larger Scales**
- **Double (2x)**: Make twice as much
- **Triple (3x)**: Make three times as much
- **Quadruple (4x)**: Make four times as much
- **Use when**: You have equipment capacity and recipe scales well

##### **Smaller Scales**
- **Half (1/2)**: Make half as much
- **Quarter (1/4)**: Make a quarter as much
- **Eighth (1/8)**: Make an eighth as much
- **Sixteenth (1/16)**: Make a sixteenth as much
- **Use when**: Testing recipes, small production runs, limited demand

#### **Scaling Considerations**
- Not all recipes scale linearly
- Cooking times may not scale proportionally
- Equipment limitations may prevent certain scales
- **Best Practice**: Test scaled recipes before offering all scale options

#### **Impact of Scaling**
- Ingredient quantities are multiplied by scale factor
- Labor time is multiplied by scale factor (adjust if needed)
- Yield amount is multiplied by scale factor
- Costs scale proportionally

---

## Viewing Batch Details

Click on any batch name to view its full details:

### Cost Breakdown

#### **Recipe Cost**
- Total cost of all ingredients from the recipe
- Includes any batch portions used in the recipe
- Updates automatically when ingredient prices change

#### **Estimated Labor Cost**
- Based on Estimated Labor Minutes and Hourly Labor Rate
- Used for planning and initial dish costing

#### **Actual Labor Cost** (if tasks exist)
- Based on the most recent completed task
- Reflects real production time and worker wages
- More accurate than estimated cost

#### **Average Labor Costs** (if tasks exist)
- **Week Average**: Average of all completed tasks in the last 7 days
- **Month Average**: Average of all completed tasks in the last 30 days
- **All-Time Average**: Average of all completed tasks ever
- **Use cases**: Identify trends, adjust estimates, refine processes

#### **Total Cost**
- Recipe Cost + Labor Cost (estimated or actual)
- This is your true cost to produce the batch

#### **Cost Per Unit** (fixed yield only)
- Total Cost ÷ Yield Amount
- Example: $45 total cost ÷ 128 oz = $0.35 per oz
- **Used in**: Menu item costing, pricing decisions

### Production History

#### **Recent Tasks**
- Shows recently completed production tasks for this batch
- Displays actual time taken and labor cost
- Click task to view full details
- **Useful for**: Performance tracking, process improvement, variance analysis

### Recipe Information
- Shows the base recipe this batch uses
- Link to view full recipe details
- Lists all ingredients and their current costs

### Usage Information
- **Used in Dishes**: Lists all menu items that use portions of this batch
- **Used in Inventory**: Shows if this batch is tracked in daily inventory
- **Used in Recipes**: Shows if other recipes use this as a batch portion
- **Impact**: Helps understand how batch changes affect the operation

---

## Editing Batches

Click the **"Edit"** button on a batch detail page to modify:
- Category
- Yield amount and unit (fixed yield only)
- Variable yield setting
- Labor minutes and rate
- Scaling options

**Important Notes**:
- Cannot change the base recipe (create a new batch instead)
- Changes to yield affect cost per unit and dish costs
- Changes to labor estimates don't affect historical actual labor costs
- Scaling option changes only affect future tasks

---

## Deleting Batches

Click the **"Delete"** button on a batch detail page.

**Warning**:
- You cannot delete a batch that is used in any dishes
- You cannot delete a batch that is used in inventory items
- You cannot delete a batch that is used as a portion in other recipes
- You must remove all usages first, then delete
- This protects against accidentally breaking cost calculations

---

## How Batches Connect to Other Parts

### Recipes
- Every batch is based on exactly one recipe
- The recipe provides ingredients and instructions
- Recipe costs flow into batch costs
- Cannot delete a recipe that has batches

### Ingredients
- Batches inherit ingredient costs from their recipe
- When ingredient prices change, batch costs automatically update
- The cost flow: Ingredients → Recipe → Batch

### Dishes
- Dishes use portions of batches
- Batch yield determines how portions are calculated
- Batch costs (recipe + labor) determine dish food costs
- The cost flow: Batch → Dish → Menu Price → Profit Margin

### Inventory Items
- Inventory items can be linked to batches
- Links production to inventory tracking
- When below par, tasks are auto-created to make the batch
- Batch yield helps calculate par unit conversions

### Tasks
- Production tasks are created for batches
- Tasks track actual labor time and calculate actual labor costs
- Completed tasks provide real performance data
- Historical task data improves cost accuracy

### Batch Portions in Recipes
- Other recipes can use portions of this batch
- Creates multi-stage production workflows
- Example: Stock batch used in soup recipe
- Costs flow through: Stock Batch → Soup Recipe → Soup Batch

---

## Best Practices

### Yield Definition

#### Accuracy
- Measure actual yields during production
- Update yields if they consistently differ from estimate
- Consider wastage, evaporation, trimming
- Use units that make sense for portioning

#### Consistency
- Use the same unit system across similar batches
- Weight for consistency (volume can vary with temperature/settling)
- Consider how the batch will be used when choosing units

### Labor Estimation

#### Initial Setup
- Time several production runs to get average
- Include all steps from start to finish
- Consider cleanup and cooling time
- Be realistic - rushing leads to quality issues

#### Updates
- Review actual task completion times regularly
- Adjust estimates based on real data
- Consider skill level differences
- Account for efficiency improvements over time

#### Labor Rate Selection
- Use the highest wage if multiple people work together
- Consider specialized skills (pastry chef vs. prep cook)
- Update rates when wages change
- Be consistent across similar batches

### Scaling Decisions

#### When to Enable Scaling
- Recipe has been tested at different sizes
- Equipment can handle scaled quantities
- Cooking times and techniques work at all scales
- Quality remains consistent

#### Which Scales to Offer
- Consider typical demand patterns
- Think about equipment capacity (mixer size, oven space, pot size)
- Smaller scales for testing or low-volume items
- Larger scales for high-demand items

#### When NOT to Scale
- Delicate recipes that don't scale well
- Items requiring precise technique
- Limited equipment capacity
- First-time recipes (test at base scale first)

### Variable Yield Batches

#### When to Use
- Reduction sauces (unpredictable final volume)
- Bone broths (yield varies with bones)
- Roasted items (moisture loss varies)
- Any time you can't reliably predict yield

#### Best Practices
- Always require made amount entry on task completion
- Track yields over time to identify patterns
- Consider making yield fixed once you have enough data
- Document factors that affect yield in recipe instructions

---

## Common Scenarios

### Scenario 1: Simple Fixed Yield Batch
**Example**: House Marinara Sauce
- Recipe: House Marinara Sauce
- Yield: 128 fl_oz
- Yield Unit: fl_oz
- Estimated Labor: 45 minutes
- Hourly Rate: $16.75
- Labor Cost: $12.56
- Can Be Scaled: Yes (Double, Half)

**Result**: Standard batch with clear yield and labor, scalable for different needs

### Scenario 2: Variable Yield Batch
**Example**: Bone Broth
- Recipe: Chicken Bone Broth
- Variable Yield: Yes
- Estimated Labor: 90 minutes
- Hourly Rate: $16.75
- Labor Cost: $25.13

**Result**: Tasks require entering actual made amount; system tracks yields over time

### Scenario 3: High-Volume Scaled Batch
**Example**: Pizza Dough
- Recipe: Pizza Dough Base
- Yield: 10 lb (makes ~20 pizzas)
- Can Be Scaled: Yes
- Scales Available: Double (40 pizzas), Triple (60 pizzas), Quadruple (80 pizzas), Half (10 pizzas)

**Result**: Flexible production to match demand; costs scale automatically

### Scenario 4: Count-Based Batch
**Example**: Chocolate Chip Cookies
- Recipe: Chocolate Chip Cookie Dough
- Yield: 48 (cookies)
- Yield Unit: item
- Can Be Scaled: Yes (Double = 96 cookies, Half = 24 cookies)

**Result**: Easy portioning for dishes (cookies per plate) or inventory (cookies per day)

---

## Troubleshooting

### "Cost per unit seems wrong"
- Check recipe cost (click recipe link to view)
- Verify yield amount is correct (are you measuring correctly?)
- Check labor minutes and rate
- Review ingredient costs in the recipe
- Ensure yield unit matches how you're actually measuring

### "Can't scale batch"
- Verify "Can Be Scaled" is checked
- Ensure at least one scale option is selected
- Save the batch after enabling scaling
- Refresh the page if scaling options don't appear

### "Actual labor cost very different from estimate"
- Review completed tasks to see actual times
- Are workers taking longer than expected?
- Is the estimated time unrealistic?
- Consider updating estimated labor minutes to match reality
- Check if the right employees are being assigned (skill level)

### "Variable yield batch cost calculations"
- Variable yield batches can't show cost per unit until produced
- Each task records actual made amount and calculates cost per unit
- View task history to see cost per unit for each production run
- Consider making yield fixed if production becomes consistent

### "Can't delete batch"
- Check "Used in Dishes" section
- Check "Used in Inventory" section
- Check "Used in Recipes" section (as batch portion)
- Remove all usages, then delete
- Cannot delete if any links exist

### "Labor averages not showing"
- Need at least one completed task for actual labor data
- Week/month averages need tasks within those timeframes
- Tasks must be finished (not just started)
- Made amount must be entered if variable yield

### "Scaling not affecting costs correctly"
- Scaling multiplies all quantities by the scale factor
- Verify the scale factor is what you expect (2x, 0.5x, etc.)
- Check that recipe ingredients scale linearly
- Some recipes don't scale perfectly (cooking times, etc.)

---

## Advanced Topics

### Multi-Stage Production

Batches can be part of complex production workflows:

**Example Flow**:
1. Make "Chicken Stock" batch (Recipe A → Batch A)
2. Make "Velouté Sauce" batch using Chicken Stock (Recipe B uses Batch A → Batch B)
3. Make "Chicken Pot Pie Filling" using Velouté Sauce (Recipe C uses Batch B → Batch C)

**Cost Flow**:
- Batch A: Ingredients cost only
- Batch B: Batch A cost + new ingredients + labor
- Batch C: Batch B cost + new ingredients + labor

Each level adds value and cost.

### Historical Cost Analysis

Use task history to analyze trends:
- **Labor Efficiency**: Are you getting faster?
- **Cost Trends**: How do actual costs compare to estimates?
- **Seasonality**: Do yields or times vary seasonally?
- **Training Impact**: New workers vs. experienced workers

**Action Items**:
- Update estimates to match reality
- Adjust menu prices if costs are consistently higher
- Identify training opportunities
- Refine recipes based on actual data

### Batch Scheduling

Use batch information for production planning:
- **Labor Minutes**: Total time needed for daily/weekly production
- **Scaling Options**: Match production to demand
- **Category**: Group similar production tasks
- **Yield**: Calculate how many batches needed

**Example**:
- Need 400 oz of marinara for weekend
- Batch yields 128 oz
- Need 4 batches (or 1 triple batch + 1 single batch)
- Labor: 4 × 45 min = 180 minutes = 3 hours

### Cost Control

Monitor batch costs to control food costs:
- **Recipe Cost %**: How much of total cost is ingredients
- **Labor Cost %**: How much of total cost is labor
- **Variance**: Actual vs. estimated costs
- **Trends**: Are costs rising or falling over time

**Red Flags**:
- Actual labor consistently exceeds estimate (inefficiency or underestimate)
- Recipe cost suddenly increases (ingredient price increases)
- High variance between runs (inconsistent production)
- Cost per unit higher than menu price (losing money)

### Yield Optimization

Improve profitability by optimizing yields:
- Track yield percentages for variable yield batches
- Identify factors that increase yield (technique, ingredient quality, equipment)
- Reduce waste through better processes
- Update recipes to maximize yield without sacrificing quality

**Example**:
- Bone broth normally yields 100 oz from recipe
- Improved technique increases yield to 115 oz
- Same cost, 15% more product
- Cost per oz drops from $0.35 to $0.30
- Better profit margins on dishes using the batch
