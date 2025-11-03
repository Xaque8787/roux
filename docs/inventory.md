# Daily Inventory

The Daily Inventory system helps you track what you have on hand, what needs to be made, and assigns production tasks to your team. It's designed to streamline daily prep and maintain proper par levels.

## Overview

The Daily Inventory system allows you to:
- Define inventory items with par levels
- Start new inventory days and assign employees
- Enter daily quantities and identify items below par
- Automatically create production tasks
- Track task completion and labor
- Generate daily reports
- Finalize completed days

## Accessing Inventory

Navigate to **Inventory** from the main navigation menu.

---

## Part 1: Inventory Items Setup

Before you can use daily inventory, you need to define what items you track.

### Creating Inventory Items

Click **"Manage Inventory Items"** or **"Add Inventory Item"** to create a new item.

#### **Name**
- Descriptive name for the inventory item
- Examples: "Marinara Sauce", "Chocolate Chip Cookies", "House Salad Mix"
- **Used in**: Daily inventory tracking, task creation, reports

#### **Category**
- Organizes items into logical groups
- Example categories: Sauces, Baked Goods, Prep Items, Proteins, Produce
- **Used in**: Filtering inventory, organizing daily counts
- **Note**: Categories are shared across the entire system

#### **Batch** (optional)
- Link to a production batch if this item is made in-house
- **When to use**: Items you prepare using batches
- **When not to use**: Purchased items, simple items without formal batches
- **Impact**: Determines what gets made when item is below par

---

### Par Level Configuration

Par levels determine how much of each item you should have on hand.

#### **Par Unit Name**
- The unit you count in for this item
- Examples: "Container", "Pan", "Bag", "Box", "Portion"
- **Note**: Par unit names are managed in Administration section
- **Purpose**: Makes counting easier and consistent

#### **Par Level**
- How many par units you want to have
- Enter as decimal number (5.0, 10.0, 2.5, etc.)
- This is your target inventory level
- **Used in**: Identifying items below par, determining what to make

#### **Par Unit Equals Configuration**

This section tells the system how much a "par unit" actually represents. Critical for accurate task creation.

##### **Par Unit Equals Type**

Choose one of three methods:

###### **Option 1: Auto**
- System calculates based on linked batch yield and par level
- **Formula**: `Batch Yield ÷ Par Level`
- **Example**:
  - Batch makes 128 oz
  - Par level is 4 containers
  - Auto calculation: 128 ÷ 4 = 32 oz per container
- **When to use**: Items linked to batches with fixed yields
- **Advantage**: Automatic, always in sync with batch

###### **Option 2: Par Unit Itself**
- One par unit equals exactly 1
- **When to use**: Count-based items (cookies, portions, sandwiches)
- **Example**: Par unit is "cookie", 1 cookie = 1 cookie
- **Advantage**: Simple, intuitive for countable items

###### **Option 3: Custom**
- You define exactly what one par unit equals
- **Par Unit Equals Amount**: Enter the amount
- **Par Unit Equals Unit**: Select the unit
- **Example**:
  - Par unit name: "Container"
  - Custom definition: 1 container = 32 oz
- **When to use**:
  - Items without linked batches
  - Items where auto calculation doesn't work
  - Custom packaging or containers

##### **Why This Matters**

When an item is below par, the system needs to know how much to make:
- You have 2 containers, par is 5 containers, need 3 more containers
- System needs to convert 3 containers → actual amount to make
- Uses "par unit equals" to calculate: 3 containers × 32 oz = 96 oz to make

---

## Part 2: Daily Inventory Days

### Starting a New Day

From the Inventory main page, click **"Start New Inventory Day"** or **"Today's Inventory"**.

#### **Date Selection**
- System defaults to today's date
- Can select a different date if needed (back-dating or planning ahead)
- Each date can only have one inventory day
- **Note**: Cannot create duplicate days for same date

#### **Employees Working**
- Select which employees are working today
- Multiple selection allowed
- **Used in**: Task assignment, labor cost calculations
- **Impact**: Only selected employees appear in task assignment dropdowns
- **Tip**: Select employees before finalizing so tasks can be assigned

#### **Global Notes**
- Optional notes for the entire day
- Examples: "Special event tonight", "Training day", "New hire"
- **Used in**: Reports, communication, tracking special circumstances

---

### Entering Inventory Quantities

After creating the day, enter the current quantity for each inventory item.

#### **Quantity Field**
- Enter how many par units you currently have
- Enter as decimal (0.5, 1.0, 2.5, 5.0, etc.)
- **Example**: If par unit is "container", enter number of containers
- Zero is allowed (item is completely out)

#### **Visual Indicators**

##### **Green (At or Above Par)**
- Current quantity ≥ par level
- No action needed
- Item is adequately stocked

##### **Red (Below Par)**
- Current quantity < par level
- Needs attention
- May trigger task creation

#### **Override Options**

Two override checkboxes give you control over automatic task creation:

##### **Override: Create Task**
- Forces task creation even if item is at or above par
- **When to use**:
  - Making extra for special events
  - Batch is close to expiring, using it up
  - Preparing for high-volume day
  - Training new staff
- **Result**: Task will be created regardless of par level

##### **Override: No Task**
- Prevents task creation even if item is below par
- **When to use**:
  - Intentionally running low (ingredient spoiling, being discontinued)
  - Will be restocked by delivery soon
  - Not serving this item today
  - No staff available to make it
- **Result**: No task created even though below par

---

### Task Creation Logic

When you finalize the day, the system automatically creates production tasks:

#### **Task is Created When**:
- Item is below par AND linked to a batch AND "Override: No Task" is NOT checked
- OR "Override: Create Task" IS checked (regardless of par level)

#### **Task is NOT Created When**:
- Item is at or above par (unless override create is checked)
- "Override: No Task" is checked
- Item has no linked batch
- Item already has an open task for this day

#### **What the Task Includes**:
- **Description**: Auto-generated based on item and batch names
- **Batch**: The linked batch to be made
- **Category**: From the batch or inventory item
- **Auto-generated**: Marked as automatically created
- **Quantity Snapshot**: Records current quantity for reference
- **Par Level Snapshot**: Records par level for reference

---

### Adding Janitorial Tasks

In addition to production tasks, you can add janitorial/cleaning tasks to the day.

#### **Daily Janitorial Tasks**
- Tasks that should be done every day
- Examples: "Clean walk-in", "Mop floors", "Sanitize prep tables"
- Managed in Administration section
- Automatically available to add to each day

#### **Manual Janitorial Tasks**
- One-off cleaning tasks
- Examples: "Deep clean oven", "Organize dry storage"
- Created as needed for specific days

#### **Adding Janitorial Tasks to a Day**
1. View the inventory day
2. Click "Edit Janitorial Tasks" or similar
3. Check which daily tasks to include
4. Add any manual tasks
5. Save

**Result**: Janitorial tasks appear alongside production tasks for the day

---

### Managing Tasks

#### **Viewing Tasks**
- Tasks for the day are listed on the inventory day page
- Organized by category
- Color-coded by status:
  - **Gray**: Not started
  - **Blue**: In progress
  - **Green**: Completed
  - **Yellow**: Paused

#### **Task Assignment**
- Assign tasks to employees from the "employees working" list
- Can assign to multiple employees (team task)
- Can reassign at any time
- **Impact**: Labor costs use assigned employee wages

#### **Task Status Tracking**

##### **Not Started**
- Task created but not begun
- Can be edited or deleted
- No time tracking yet

##### **In Progress**
- Employee has started the task
- Timer is running
- Can be paused
- Shows elapsed time

##### **Paused**
- Task temporarily stopped
- Time does not accumulate while paused
- Can be resumed
- Pause time is tracked separately

##### **Completed**
- Task is finished
- Total time calculated (excluding pause time)
- Labor cost calculated
- Made amount recorded (if variable yield or requires input)
- Cannot be edited once completed

#### **Task Actions**

##### **Start Task**
- Begins time tracking
- Changes status to "in progress"
- Records start timestamp

##### **Pause Task**
- Temporarily stops time tracking
- Can be resumed later
- Use when interruptions occur

##### **Resume Task**
- Continues time tracking after pause
- Returns to "in progress" status

##### **Complete Task**
- Finishes the task
- Requires made amount if needed
- Calculates final labor cost
- Changes status to "completed"
- Records finish timestamp

##### **Delete Task**
- Removes task from day
- Only available for not-started or auto-generated tasks
- Cannot delete started or completed tasks (data integrity)

---

### Task Details and Completion

Click on any task to view full details:

#### **Information Displayed**
- Task description and instructions
- Assigned employee(s)
- Batch information (if production task)
- Category
- Time tracking (start, finish, pauses, total time)
- Status
- Notes
- Made amount (if applicable)
- Labor cost (if completed)

#### **Completing a Task**

When completing a task:

##### **Made Amount** (if required)
Required when:
- Batch has variable yield
- Inventory item has par unit configuration and no fixed batch yield
- System needs to know actual output

**Enter**:
- Amount: How much was made (decimal number)
- Unit: What unit was made in (must match batch yield unit or par unit equivalent)

**Example**:
- Making marinara sauce (variable yield batch)
- Made 112 oz (batch usually makes 120 oz)
- Enter: 112 oz
- System calculates: Cost per oz based on actual yield

##### **Notes** (optional)
- Add any relevant notes about the task
- Examples: "Recipe scaled 1.5x", "Needed extra time for browning", "New employee"
- Useful for future reference and process improvement

##### **Labor Cost Calculation**
Automatically calculated when task completes:
- **Formula**: `(Total Minutes ÷ 60) × Highest Employee Wage`
- Uses highest wage if multiple employees assigned
- Excludes pause time from total minutes
- Stored with task for historical accuracy

---

### Finalizing the Day

When all work is complete, finalize the day to lock it in.

#### **Click "Finalize Day"**
- Locks the day from further editing
- Marks the day as complete
- Records finalization timestamp
- **Note**: Cannot unfinalizing (protects historical data)

#### **What Can't Be Changed After Finalization**:
- Employee assignments
- Inventory quantities
- Task creation/deletion
- Janitorial task selection
- Global notes

#### **What Can Still Be Viewed**:
- All inventory quantities
- All task details
- Labor costs and time tracking
- Reports

---

## Part 3: Reports and Analysis

### Inventory Day Report

View detailed report for any inventory day:

#### **Inventory Summary**
- All items with quantities and par levels
- Items below par highlighted
- Percentage of par for each item

#### **Task Summary**
- Total tasks created
- Tasks completed
- Tasks in progress
- Tasks not started

#### **Labor Summary**
- Total labor hours
- Total labor cost
- Labor by employee
- Labor by category

#### **Production Summary**
- Items produced
- Quantities made
- Variance from estimates (variable yield items)

### Historical Comparison

Compare multiple days:
- Inventory levels over time
- Labor costs trending
- Production volumes
- Employee performance
- Category breakdowns

---

## How Inventory Connects to Other Parts

### Batches
- Inventory items can link to batches
- When below par, tasks are created to make the batch
- Batch yields determine how much to make
- Batch labor estimates vs. actual from tasks

### Tasks
- Inventory creates production tasks automatically
- Tasks track actual labor and made amounts
- Completed tasks provide real cost data
- Task history improves batch labor estimates

### Employees
- Employees are assigned to work days
- Tasks are assigned to employees
- Labor costs use employee wages
- Performance tracking by employee

### Categories
- Organizes inventory items
- Groups tasks by category
- Enables category-level analysis
- Consistent across entire system

### Par Unit Names
- Standardizes inventory counting
- Makes daily counts faster and more consistent
- Shared across all inventory items
- Managed in Administration section

---

## Best Practices

### Setting Up Inventory Items

#### **Choose the Right Par Units**
- Use containers or measures you actually count
- Be consistent across similar items
- Examples:
  - "Hotel Pan" for bulk sauces
  - "Container" for portioned items
  - "Dozen" for baked goods
  - "Each" for whole items

#### **Set Realistic Par Levels**
- Consider daily usage
- Account for lead time to make
- Buffer for unexpected demand
- Don't over-par (waste, quality issues)
- Review and adjust based on actual usage

#### **Link to Batches When Appropriate**
- If you make it, link it to a batch
- Use auto par unit calculation for consistency
- Update batch yields as needed
- Don't link if it's a purchased item or too simple for batching

### Daily Inventory Workflow

#### **Best Time to Count**
- Morning: Before service, after deliveries
- Evening: After service, planning for next day
- **Consistency**: Same time each day for accurate trending

#### **Counting Tips**
- Use the same person when possible (consistency)
- Don't round too aggressively
- Be honest about quality (don't count unusable product)
- Count before accessing tasks (avoids confusion)

#### **Task Assignment Strategy**
- Assign based on skill level (complex vs. simple tasks)
- Balance workload across employees
- Consider training opportunities
- Group similar tasks for efficiency

### Using Overrides Effectively

#### **Override: Create Task**
Use when:
- Special events requiring extra production
- Making ahead for day off
- Using up product (batch before batch expires)
- Training production runs

Don't overuse:
- Creates extra labor cost
- Can lead to waste
- Defeats purpose of par levels

#### **Override: No Task**
Use when:
- Intentionally running low
- Item being discontinued
- Delivery expected soon
- Insufficient staff
- Equipment unavailable

Document why:
- Add note explaining override
- Helps with future planning
- Trains other staff on decision-making

### Labor Management

#### **Accurate Time Tracking**
- Start tasks when actually starting
- Pause for interruptions (deliveries, customer issues)
- Complete immediately when done
- Don't round times excessively

#### **Made Amount Accuracy**
- Weigh or measure actual output
- Record real yield (not estimated)
- Note variances in task notes
- Use data to improve recipes/processes

#### **Performance Analysis**
- Compare actual labor to estimates
- Identify training needs
- Recognize efficient employees
- Adjust estimates based on reality

### Par Level Management

#### **Regular Review**
- Check par levels monthly
- Adjust for seasonal changes
- Account for menu changes
- Remove items no longer used

#### **Optimization**
- Too low: Frequent stockouts, rush production
- Too high: Waste, quality issues, storage problems
- **Sweet spot**: Always enough, minimal waste

#### **Seasonal Adjustments**
- Increase pars for busy seasons
- Decrease for slow periods
- Plan for holidays and events
- Adjust for menu seasonality

---

## Common Scenarios

### Scenario 1: Simple Production Item
**Example**: Marinara Sauce
- **Par Unit Name**: Hotel Pan
- **Par Level**: 3.0
- **Linked Batch**: Marinara Sauce (yields 128 oz)
- **Par Unit Equals**: Auto (128 oz ÷ 3 = 42.67 oz per pan)

**Daily Use**:
- Count: 1.5 pans on hand
- Below par (need 1.5 more pans)
- Task created automatically: Make batch to produce 64 oz (1.5 pans)

### Scenario 2: Count-Based Item
**Example**: Chocolate Chip Cookies
- **Par Unit Name**: Dozen
- **Par Level**: 10.0 (120 cookies)
- **Linked Batch**: Cookie Batch (yields 48 cookies)
- **Par Unit Equals**: Par Unit Itself (1 dozen = 12 cookies)

**Daily Use**:
- Count: 6 dozen (72 cookies)
- Below par (need 4 dozen / 48 cookies)
- Task created: Make 1 batch (48 cookies)

### Scenario 3: Variable Yield Item
**Example**: Bone Broth
- **Par Unit Name**: Container
- **Par Level**: 4.0
- **Linked Batch**: Bone Broth (variable yield)
- **Par Unit Equals**: Custom (1 container = 32 oz)

**Daily Use**:
- Count: 1.5 containers
- Below par (need 2.5 containers = 80 oz target)
- Task created to make batch
- Worker completes task, records actual made: 76 oz (close to target)

### Scenario 4: Special Event Override
**Example**: House Salad Mix (normally at par)
- Count: 5 containers (par is 5 - at par)
- **Override: Create Task** checked
- Reason: Large catering event tomorrow
- Task created to make extra batch despite being at par

---

## Troubleshooting

### "Task not created for below-par item"
- Verify item is linked to a batch
- Check that "Override: No Task" is not checked
- Ensure the day has been saved/finalized
- Confirm batch still exists
- Check if task was already created (can't duplicate)

### "Task created when item at par"
- Check if "Override: Create Task" is checked
- This is intentional if override is used
- If not, may be a display issue (refresh page)

### "Can't enter made amount"
- Made amount only required for:
  - Variable yield batches
  - Inventory items with par units but variable output
- Fixed yield batches don't require input
- Check batch configuration if expected

### "Labor cost seems wrong"
- Verify employee wage is correct
- Check total time (include pause time?)
- Ensure highest wage used if multiple employees
- Look at time tracking (start/stop times correct?)

### "Can't finalize day"
- May have tasks still in progress
- Check for validation errors
- Ensure all required fields filled
- Try refreshing page

### "Par unit conversion not working"
- For Auto: Verify batch has yield amount and unit
- For Custom: Check that amount and unit are filled
- Ensure par level is set
- Check that units are compatible

### "Wrong employees in task dropdown"
- Only employees marked as "working" for the day appear
- Edit day to add more employees
- Check that employees are active in system
- Must save day after adding employees

---

## Advanced Topics

### Inventory Forecasting

Use historical data to predict needs:
- Track usage patterns by day of week
- Identify seasonal trends
- Adjust pars proactively
- Plan production schedules

### Waste Tracking

Document waste reasons:
- Over-production (par too high)
- Spoilage (quality issues)
- Mistakes (production errors)
- Customer returns

**Use to**:
- Adjust par levels
- Improve training
- Refine recipes
- Reduce costs

### Multi-Location Management

If running multiple locations:
- Use categories to separate locations
- Prefix item names with location
- Separate inventory days by location
- Compare efficiency across locations

### Integration with Purchasing

Use inventory data to inform purchasing:
- Items frequently below par → order more
- Items always above par → reduce orders
- Usage trends → negotiate better pricing
- Seasonal patterns → plan ahead

### Labor Productivity Analysis

Calculate productivity metrics:
- Units produced per labor hour
- Labor cost per unit produced
- Employee efficiency comparisons
- Category-level productivity

**Use to**:
- Set labor targets
- Identify training needs
- Optimize scheduling
- Control costs

### Predictive Task Creation

Advanced usage:
- Create tasks before counting (based on historical usage)
- Adjust as you count
- Start production earlier in day
- Reduce afternoon rush

### Quality Control Integration

Add quality notes to tasks:
- Temperature logs
- Visual checks
- Taste testing
- Compliance verification

**Benefits**:
- Improved consistency
- Training documentation
- Regulatory compliance
- Problem identification
