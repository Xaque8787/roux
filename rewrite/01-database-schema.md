# 01 - Database Schema

Status: REVISED - review round 1 incorporated, pending approval

This blueprint defines every table in the rewrite. It covers the whole current app (all 22 tables in `models.py`) plus the launch additions (F1 stock/ordering, F2 units), and reserves room for post-launch work (Schedules, F5, F4). Behavior and screens live in 05-09 and 12. This document covers only the data and the rules that protect it.

Section 9 maps every current table and notable column to where it ends up, so you can check that nothing is missing.

---

## 1. Storage conventions

### 1.1 Column types used in this document

| Notation | Stored as | Meaning |
|----------|-----------|---------|
| `id` | INTEGER PK | Internal key. Never leaves the server (00 section 5.1). |
| `public_id` | TEXT(10), unique | Random lowercase code (for example `k3f9x2qa7m`) for records that have no name or date. Not sequential. |
| `name` | TEXT, `COLLATE NOCASE`, unique | Trimmed before saving. Uniqueness ignores case. |
| `slug` | TEXT, unique | Generated from the name, with a `-2`/`-3` suffix only if two names produce the same slug. |
| `ts` | DATETIME | Always **UTC**. Converted to `TZ` only for display and for working out the business day. |
| `date` | DATE | A calendar business date (for example the inventory day). |
| `qty` | INTEGER | Quantity in **thousandths of a base unit**: milligrams, microliters, or 1/1000 of an "each". `1500 g` is stored as `1500000`. Integers keep the stock ledger exact (no float drift). |
| `money` | INTEGER | **Micro-dollars** (1 dollar = 1,000,000). Uniform for prices, totals, wages, and per-gram costs (which need precision below a cent). Shown rounded to cents. |
| `factor` | two INTEGERs (`_num`, `_den`) | An exact fraction, used for batch scales (2/3 stays exact). |
| `enum` | TEXT with CHECK constraint | Fixed list of values, named in the table. |
| `json` | TEXT holding JSON | Only for settings and step lists, never for data that gets searched or joined. |

### 1.2 Standard column groups

Most tables include one or more of these groups instead of repeating them:

- **[STD]** `id`, `created_at ts`, `created_by_id -> users`, `updated_at ts`, `updated_by_id -> users`. The "by" columns are empty for system actions.
- **[NAMED]** `name`, `slug`. Old slugs go to `slug_aliases` on rename (section 7.2).
- **[ARCH]** `archived_at ts`, `archived_by_id -> users`. An empty `archived_at` means active. Archived rows keep their name reserved.
- **[PUB]** `public_id`.

### 1.3 Database settings (set on every connection)

- `PRAGMA foreign_keys = ON`: SQLite ignores foreign keys unless this is on, so every delete rule in section 8 depends on it.
- `PRAGMA journal_mode = WAL`, `busy_timeout = 5000`, `synchronous = NORMAL`. Rationale in 11.

---

## 2. Units and quantities (F2)

### 2.1 Dimensions and base units

| Dimension | Base unit | Stored `qty` unit |
|-----------|-----------|-------------------|
| `mass` | gram | milligram |
| `volume` | milliliter | microliter |
| `count` | each | 1/1000 each |

### `units` (built-in, seeded by the migration, read-only in the app)
| Column | Type | Notes |
|--------|------|-------|
| `code` | TEXT PK | `g`, `kg`, `oz`, `lb`, `ml`, `l`, `tsp`, `tbsp`, `fl_oz`, `cup`, `pt`, `qt`, `gal`, `each` |
| `dimension` | enum mass/volume/count | |
| `system` | enum us/metric/neutral | `each` is neutral |
| `to_base` | REAL | How many base units in one of this unit (for example `cup` = 236.588 ml) |
| `display_name`, `plural_name` | TEXT | |

- The old **baking measurements** (3/4 cup, 1/3 cup and so on) stop being separate units. A user enters `3/4` with `cup`, and the amount is stored exactly. The display engine (05) turns stored amounts back into kitchen fractions.
- The old **Baking Measurements Conversion** stays as the user sees it today: **one reference measurement per ingredient**, for example "1 tbsp of dried basil weighs 2.1 g" or "1 cup of honey weighs 12 oz". It can be entered in either direction, using any volume unit and any weight unit. From that single measurement the app works out every other size (tsp, cup, qt, fl oz to g, oz, lb, kg). It does three jobs:
  1. **Costing:** an item sold by weight (a 1.5 lb tub) but used by volume (tbsp) gets a real cost per tbsp.
  2. **Metric view:** volume recipes can be shown fully in weights.
  3. **Stock:** usage in cups comes off a stock level kept in pounds.
- Internally the measurement is turned into a density (section 3.3), but the user only ever sees and edits the measurement they typed.

### 2.2 How a quantity is stored

Every place a person enters an amount stores three things:
- `*_qty qty`: the canonical amount in base units. All math uses this.
- `*_entered_amount` TEXT: what was typed, kept exactly (`"1 1/2"`).
- `*_entered_unit` TEXT: a `units.code` **or** the slug of one of that item's custom units (section 3.3).

The US/Metric toggle only changes how the canonical amount is **displayed**. The entered amount is shown when the viewer is in the same unit system it was typed in.

### 2.3 Conversion rules (enforced by the service layer)

- Same dimension: always convertible.
- Weight to volume or back: only if the ingredient (or batch) has a reference measurement.
- **Ounces are never ambiguous.** `oz` (weight) and `fl_oz` (volume) are separate units, and every unit picker labels them "oz (weight)" and "fl oz (volume)". Old data that says just "oz" is listed for review during the data move (13), not guessed.
- **No automatic water assumption.** The conversion popup offers a "Fill in as water (1 cup = 8.35 oz weight)" shortcut for thin liquids. It saves an ordinary measurement the user can see and change, so nothing is assumed silently.
- Count to weight/volume: only through a custom unit such as "1 each = 50 g".
- **No silent fallbacks.** Today an impossible conversion quietly counts as 1:1, which gives wrong costs. In the rewrite the line is marked "Can't price: no conversion for Dried Basil" with two actions: **Add conversion** (opens a popup to enter the measurement, which applies to every recipe that uses the ingredient) or **Leave out of cost** (sets the line's `exclude_from_cost`). Totals show a warning while any line is unpriced or excluded.

---

## 3. Catalog: ingredients, vendors, categories

### `categories` [STD] [ARCH]
| Column | Type | Notes |
|--------|------|-------|
| `kind` | enum ingredient/recipe/batch/dish/inventory/chore | `chore` replaces the old janitorial type |
| `name` | TEXT NOCASE | Unique **per kind** (`UNIQUE(kind, name)`) |
| `slug` | TEXT | Unique per kind |
| `icon` | TEXT | Emoji or icon name |
| `color` | TEXT | Hex |
| `position` | INTEGER | Display order |

### `vendors` [STD] [NAMED] [ARCH]
| Column | Type | Notes |
|--------|------|-------|
| `contact_name`, `phone`, `email`, `website`, `account_number` | TEXT | Replaces the single `contact_info` text blob |
| `notes` | TEXT | Anything that doesn't fit the fields above |
| `order_days` | TEXT | Optional, for example "Mon, Thu" (shown on the order guide) |

### `purchase_units` [STD] [NAMED] [ARCH]
The pack labels a vendor sells in: Case, Bag, Sack, Box, Tub... Replaces the free-text `purchase_unit_name`. The old `vendor_units` table (a vendor selling by the gallon or pound when the kitchen tracks something else) is retired. Its job is now done by a vendor item's `pricing_mode = per_unit` + `price_unit`, with conversion through the units engine.
| Column | Type | Notes |
|--------|------|-------|
| `description` | TEXT | |

### 3.3 `ingredients` [STD] [NAMED] [ARCH]
| Column | Type | Notes |
|--------|------|-------|
| `category_id` | -> categories | Detach on delete |
| `dimension` | enum mass/volume/count | How it is measured and costed. Replaces `usage_type` and `use_item_count_pricing` |
| `conv_volume_amount`, `conv_volume_unit` | TEXT, TEXT, null | The reference measurement as typed: "1" + `tbsp` |
| `conv_weight_amount`, `conv_weight_unit` | TEXT, TEXT, null | "2.1" + `g`. All four are set together or all empty (CHECK) |
| `density_g_per_ml` | REAL, null | Calculated from the four fields above on save. Never edited directly. Replaces the old baking conversion fields |
| `preferred_vendor_item_id` | -> vendor_items, null | The pack price used for costing. Detach on delete |
| `stock_tracked` | bool | F1: include in stock and the order guide |
| `stock_par_qty` | qty, null | F1: how much should ideally be on hand |
| `stock_near_par_percent` | INTEGER, null | F1: how close to par counts as "near par" for the order guide. Empty means use the global setting |
| `order_override` | enum auto/force/skip | F1: like the daily inventory override. `force` puts an above-par item on the order guide, and `skip` keeps a below-par item off it |
| `order_override_at`, `order_override_by_id` | ts, -> users, null | Who set the override. Cleared automatically when an order containing this ingredient is placed |
| `notes` | TEXT | |

**Cost per base unit** is calculated, never stored: the preferred vendor item's price divided by its pack amount.

### `ingredient_units` [STD]
Custom units for one ingredient: "1 each = 50 g", "1 bunch = 450 g", "1 dozen = 12 each", "1 #10 can = 3 kg".
| Column | Type | Notes |
|--------|------|-------|
| `ingredient_id` | -> ingredients | Cascade |
| `name`, `slug` | TEXT | Unique per ingredient |
| `qty` | qty | Amount in the ingredient's base dimension |

### `vendor_items` [STD] [ARCH] (new, F1/F5)
What a vendor actually sells, linked to an ingredient. One ingredient can have several (two vendors, or two pack sizes). This replaces the purchase fields on today's ingredient.
| Column | Type | Notes |
|--------|------|-------|
| `ingredient_id` | -> ingredients | Cascade |
| `vendor_id` | -> vendors | Block |
| `vendor_description` | TEXT | Name as the vendor lists it |
| `sku` | TEXT, null | `UNIQUE(vendor_id, sku)` when present. Used by F5 matching |
| `slug` | TEXT | Unique per ingredient, from vendor + pack, for example `sysco-case-6x10` |
| `purchase_unit_id` | -> purchase_units | Block |
| `items_per_pack` | INTEGER | 1 for a single item. Replaces `items_per_case` and `purchase_type` |
| `item_qty` | qty | Net amount per item. Replaces `item_weight_volume` and `net_weight_volume_item` |
| `pack_qty` | qty | Net amount per pack. Usually `items_per_pack x item_qty`, but stored so it can be overridden. Replaces `net_weight_volume_case` |
| `pricing_mode` | enum per_pack/per_unit | `per_unit` covers "$3.49/lb" catch-weight items (old `uses_price_per_weight_volume`) |
| `price` | money | Pack price, or the price per `price_unit` |
| `price_unit` | TEXT, null | `units.code` for per-unit pricing |
| `breakable` | bool | Can order single items from the pack (old `breakable_case`) |
| `price_updated_at` | ts | |
| `price_source` | enum manual/sync/import | |

### `price_history` [PUB]
One row each time a vendor item's price changes, so trends can be shown. The price history view filters by **last month, quarter, year, or all time**. An Admin-only **Purge price history** action deletes rows older than a chosen date after a typed confirmation, and records the purge in `change_log`. This is the one deliberate exception to "history is never erased". It never touches a vendor item's current price.
| Column | Type | Notes |
|--------|------|-------|
| `vendor_item_id` | -> vendor_items | Cascade |
| `price` | money | |
| `observed_at` | ts | |
| `source` | enum manual/sync/import | |
| `job_run_id` | -> job_runs, null | F5 |
| `created_by_id` | -> users, null | |

---

## 4. Recipes, batches, dishes

### `recipes` [STD] [NAMED] [ARCH]
| Column | Type | Notes |
|--------|------|-------|
| `category_id` | -> categories | Detach |
| `instructions` | TEXT | Markdown |
| `notes` | TEXT | |

`deleted` (the old soft delete) becomes `archived_at`.

### `recipe_ingredients` [STD] [PUB]
The same ingredient may appear on more than one line (for example cooked into the base, then added fresh to finish). Lines are addressed by `public_id`, not by the ingredient.
| Column | Type | Notes |
|--------|------|-------|
| `recipe_id` | -> recipes | Cascade |
| `ingredient_id` | -> ingredients | Block |
| `qty`, `entered_amount`, `entered_unit` | see 2.2 | |
| `prep_note` | TEXT | "diced", "for finishing". Shown so duplicate lines can be told apart |
| `exclude_from_cost` | bool | Set by "Leave out of cost" (2.3). The line still shows on the recipe |
| `position` | INTEGER | Line order |

### `recipe_sub_batches` [STD]
A recipe that uses part of another batch (old `recipe_batch_portions`).
| Column | Type | Notes |
|--------|------|-------|
| `recipe_id` | -> recipes | Cascade |
| `batch_id` | -> batches | Block |
| `portion_mode` | enum quantity/fraction | Replaces `use_recipe_portion` |
| `qty`, `entered_amount`, `entered_unit` | | For `quantity` mode |
| `fraction` | factor | For `fraction` mode (old `recipe_portion_percent`) |
| `position` | INTEGER | |
| | | `UNIQUE(recipe_id, batch_id)`. **No cycles**: checked on save |

### `batches` [STD] [ARCH]
A batch is a recipe made at a set yield, with labor and scale options. Each recipe has **at most one batch**, and that batch covers every size through the scale slider (below). The batch takes its name and slug from the recipe and follows it on rename, so [NAMED] does not apply: `name`/`slug` are not stored on the batch. The slug alias for old batch URLs comes from the recipe's alias.
| Column | Type | Notes |
|--------|------|-------|
| `recipe_id` | -> recipes, **unique** | Block. If the current data has two batches on one recipe, the data migration (13) lists them for you to merge or keep as a scale |
| `category_id` | -> categories | Detach |
| `yield_mode` | enum fixed/variable | Replaces `variable_yield` |
| `yield_dimension` | enum mass/volume/count | |
| `yield_qty`, `yield_entered_amount`, `yield_entered_unit` | | Fixed yield only |
| `density_g_per_ml` | REAL, null | Lets dish portions use weight when the yield is a volume |
| `labor_minutes_estimate` | INTEGER | |
| `labor_rate` | money, null | Per hour. Empty means use the global default (settings). The old hard-coded `16.75` default moves to settings |
| `stock_deduct_mode` | enum inherit/always/never | Default for tasks that make this batch (F1) |
| `scalable` | bool | Old `can_be_scaled`. Off means the batch is always made at 1x |
| `scale_min_num`, `scale_min_den` | factor | Lowest size allowed. Default 1/16 |
| `scale_max_num`, `scale_max_den` | factor | Highest size allowed. Default 8/1 |
| | | CHECK: 1/16 <= min <= 1 <= max <= 8 |

**Scale slider** (replaces the nine `scale_*` on/off columns; there is no scales table):
- Range 1/16x to 8x, limited per batch by min/max.
- Snaps to: 1/16, 1/8, 1/4, 1/3, 1/2, 2/3, 3/4, 1, 1.5, 2, 3, 4, 5, 6, 7, 8.
- Between snap points it moves in steps of 1/16 below 1x and 1/4 above 1x.
- These lists live in code, not in the database. The chosen size is stored on the task as an exact fraction.
- Scaled amounts are shown in kitchen terms (05): US volumes as fractions (1 1/2 cups, 3/4 tsp), with **1/4 tsp as the smallest step** (anything smaller shows as "less than 1/4 tsp" with the exact weight beside it). Decimal amounts (weights, metric) are rounded to one decimal place.

### `dishes` [STD] [NAMED] [ARCH]
| Column | Type | Notes |
|--------|------|-------|
| `category_id` | -> categories | Detach |
| `sale_price` | money | |
| `description` | TEXT | |

### `dish_batches` [STD]
Old `dish_batch_portions`. Same columns and rules as `recipe_sub_batches`, with `dish_id` (cascade) instead of `recipe_id`. `UNIQUE(dish_id, batch_id)`.

### `dish_ingredients` [STD] [PUB]
Old `dish_ingredient_portions`. `dish_id` (cascade), `ingredient_id` (block), `qty`/`entered_*`, `prep_note`, `exclude_from_cost`, `position`. Like recipe lines, the same ingredient may appear twice.

> Costing fix: today a dish ignores the cost of a batch's own sub-batches, while a recipe includes it. In the rewrite one costing service is used everywhere (06).

---

## 5. People, inventory, tasks

### `users` [STD] [ARCH]
Holds Admins, Managers, and Employees (D9).
| Column | Type | Notes |
|--------|------|-------|
| `name` | TEXT NOCASE, unique | Full name (old `full_name`) |
| `slug` | TEXT unique | `/employees/jane-doe` |
| `role` | enum admin/manager/employee | Replaces `role` + `is_admin` + `is_user` |
| `username` | TEXT NOCASE, unique, null | Required for admin/manager, empty for employees |
| `password_hash` | TEXT, null | Same rule as username |
| `pin_hash` | TEXT, null | Reserved for the task-station PIN (D13) |
| `email` | TEXT, null | Email reports |
| `hourly_wage` | money | |
| `unit_system` | enum us/metric, null | Personal display preference. Empty means use the global default |
| `is_active` | bool | Inactive users can't sign in or be assigned work. Separate from archive: an inactive user is still listed, an archived user is hidden |
| | | CHECK: admin/manager rows must have a username and password hash |

### `user_work_days`
Replaces the comma-separated `work_schedule`.
| Column | Type | Notes |
|--------|------|-------|
| `user_id` | -> users | Cascade |
| `weekday` | INTEGER 0-6 | Monday = 0. `PRIMARY KEY(user_id, weekday)` |

### `count_units` [STD] [NAMED] [ARCH]
The labels inventory items are counted in: Quart, Pan, Bag, 1/6 Pan... (old `par_unit_names`).

### `inventory_items` [STD] [NAMED] [ARCH]
| Column | Type | Notes |
|--------|------|-------|
| `category_id` | -> categories | Detach |
| `batch_id` | -> batches, null | Block. Prepped items made by a batch |
| `ingredient_id` | -> ingredients, null | Block. **New**: raw goods counted on the inventory day. A count posts a stock count movement (F1) |
| | | CHECK: not both `batch_id` and `ingredient_id` |
| `count_unit_id` | -> count_units, null | Block |
| `par_level` | qty | In count units (thousandths), for example 2.5 pans = `2500` |
| `count_unit_mode` | enum self/batch_fraction/fixed | Old `par_unit_equals_type` values `par_unit_itself` / `auto` / `custom` |
| `count_unit_qty`, `count_unit_entered_amount`, `count_unit_entered_unit` | | `fixed` mode: how much one count unit holds (old `par_unit_equals_amount/unit`) |
| `department_id` | | **Not added at launch.** Future departments (00 section 5.1) will add this column |

### `inventory_days` [STD]
| Column | Type | Notes |
|--------|------|-------|
| `business_date` | date | `UNIQUE` at launch. Becomes `UNIQUE(department_id, business_date)` when departments arrive |
| `status` | enum open/finalized | Replaces `finalized` |
| `started_at` | ts | |
| `finalized_at`, `finalized_by_id` | ts, -> users | Latest finalize |
| `reopened_at`, `reopened_by_id` | ts, -> users, null | Latest reopen (full history in `change_log`) |
| `notes` | TEXT | Old `global_notes` |

### `inventory_day_staff`
Replaces the comma-separated `employees_working`.
| Column | Type | Notes |
|--------|------|-------|
| `day_id` | -> inventory_days | Cascade |
| `user_id` | -> users | History detach (see 8) |
| `user_name_snapshot` | TEXT | Shown if the user is later deleted |
| | | `UNIQUE(day_id, user_id)` |

### `inventory_counts` [STD]
Old `inventory_day_items`.
| Column | Type | Notes |
|--------|------|-------|
| `day_id` | -> inventory_days | Cascade |
| `inventory_item_id` | -> inventory_items, null | History detach |
| `counted` | qty | In count units |
| `task_override` | enum auto/force/skip | Replaces `override_create_task` + `override_no_task` (they could both be on, which made no sense) |
| `snap_item_name`, `snap_par_level`, `snap_count_unit` | | Written at finalize |
| `snap_unit_cost` | money, null | Cost of one count unit at finalize, for reports. Kept on reopen unless refreshed |
| | | `UNIQUE(day_id, inventory_item_id)` |

### `chores` [STD] [NAMED] [ARCH]
Old `janitorial_tasks`, renamed **Chores** everywhere in the app.
| Column | Type | Notes |
|--------|------|-------|
| `instructions` | TEXT | |
| `frequency` | enum daily/manual | Old `task_type` |
| `category_id` | -> categories (kind chore) | Detach |

### `inventory_day_chores`
Old `janitorial_task_days`.
| Column | Type | Notes |
|--------|------|-------|
| `day_id` | -> inventory_days | Cascade |
| `chore_id` | -> chores | Cascade (a planning toggle, not history) |
| `included` | bool | |
| | | `UNIQUE(day_id, chore_id)` |

### `tasks` [STD] [PUB]
URL: `/inventory/days/2026-10-22/tasks/k3f9x2qa7m`. Today task slugs are built from names and can collide.
| Column | Type | Notes |
|--------|------|-------|
| `day_id` | -> inventory_days | Cascade |
| `kind` | enum prep/chore/general | Prep = batch or inventory item. Chore = from a chore. General = free text |
| `origin` | enum auto/manual | Old `auto_generated` |
| `title` | TEXT | Old `description`. Generated for auto tasks |
| `inventory_item_id` | -> inventory_items, null | Open task: block. Finished task: history detach |
| `batch_id` | -> batches, null | Same rule |
| `chore_id` | -> chores, null | Same rule. **Fixes a current bug**: deleting a janitorial task today also deletes its completed tasks and their labor history |
| `category_id` | -> categories, null | Detach |
| `status` | enum not_started/in_progress/paused/completed | Stored so it can be filtered quickly. Kept consistent with sessions by the service |
| `started_at`, `finished_at` | ts, null | First start and completion |
| `notes` | TEXT | |
| `scale_num`, `scale_den` | factor | The size picked on the slider, stored exactly (for example 5/4 for 1.25x) |
| `made_qty`, `made_entered_amount`, `made_entered_unit` | | For variable yields and manual restocks |
| `gen_counted`, `gen_par_level`, `gen_override` | | Old `snapshot_*`: the inventory values the auto task was generated from, used to detect changes |
| `stock_deduct_mode` | enum inherit/always/never | Per-task override (F1). Defaults from the batch |
| `labor_minutes` | INTEGER, null | **Frozen at completion**, recalculated (and audited) when a finished task is edited |
| `labor_cost` | money, null | Same |
| `edited_at`, `edited_by_id` | ts, -> users, null | Drives the "Edited by" badge (D21) |

### `task_assignees`
Replaces `assigned_to_id` + the comma-separated `assigned_employee_ids`.
| Column | Type | Notes |
|--------|------|-------|
| `task_id` | -> tasks | Cascade |
| `user_id` | -> users | History detach |
| `user_name_snapshot` | TEXT | |
| `wage_snapshot` | money | Hourly wage frozen when the task completes |
| | | `UNIQUE(task_id, user_id)` |

**Labor cost rule:** task minutes x the **highest** `wage_snapshot` among the assignees. Today the app intends this but only reads the first assignee. The rewrite applies it properly.

### `task_sessions` [PUB]
Pausing ends a session and resuming starts a new one. This removes the duplicate pause bookkeeping (`is_paused`, `paused_at`, `total_pause_time` on tasks and `pause_duration` on sessions).
| Column | Type | Notes |
|--------|------|-------|
| `task_id` | -> tasks | Cascade |
| `started_at` | ts | |
| `ended_at` | ts, null | Empty means running. At most one running session per task (partial unique index) |
| `created_at`, `edited_at`, `edited_by_id` | | |

---

## 6. Stock and ordering (F1)

### `stock_movements` [PUB]
The ledger. Every change to stock on hand is one row.
| Column | Type | Notes |
|--------|------|-------|
| `ingredient_id` | -> ingredients, null | History detach |
| `ingredient_name_snapshot` | TEXT | |
| `kind` | enum receive/usage/count/waste/adjust | |
| `qty_delta` | qty, signed | For all kinds except `count` |
| `counted_qty` | qty | `count` only: the absolute amount counted |
| `unit_cost` | money | Cost per base unit at the time (valuation) |
| `occurred_at` | ts | When it happened (may be backdated) |
| `task_id` | -> tasks, null | Cascade: created by a finished task |
| `inventory_count_id` | -> inventory_counts, null | Cascade: created by a finalized count |
| `order_line_id` | -> order_lines, null | Cascade: created by receiving |
| `note` | TEXT | Required for `waste` and `adjust` |
| `created_at`, `created_by_id`, `edited_at`, `edited_by_id` | | |

**How the current level is calculated:** start from the most recent `count` for that ingredient, then add every other movement that happened after it. Fixing an old count, or editing a task from last week, then gives the right answer without rewriting later rows.

**What moves stock automatically** (when `stock_auto_deduct` is on and the task's mode allows it):
- **Completing a prep task** that makes a batch (directly, or through an inventory item linked to a batch) posts one `usage` movement per ingredient in that batch's recipe, scaled by the task's scale or made amount. Sub-batches are followed down to their raw ingredients.
- **Finalizing an inventory day** posts a `count` movement for every counted inventory item linked to an ingredient.
- **Receiving an order line** posts a `receive` movement.

**Owned movements:** movements created by a task, a count, or a receipt belong to that record. When the record is edited, reopened, or deleted, its movements are recalculated or removed in the same transaction. Hand-entered movements (waste, adjust, manual receive) stand on their own.

### `purchase_orders` [STD] [PUB]
| Column | Type | Notes |
|--------|------|-------|
| `vendor_id` | -> vendors | Block |
| `status` | enum draft/placed/received/cancelled | |
| `placed_at`, `received_at` | ts, null | |
| `notes` | TEXT | |
| `vendor_name_snapshot` | TEXT | |

### `order_lines` [STD]
| Column | Type | Notes |
|--------|------|-------|
| `order_id` | -> purchase_orders | Cascade |
| `vendor_item_id` | -> vendor_items, null | History detach |
| `description_snapshot`, `sku_snapshot` | TEXT | |
| `packs_ordered` | qty | Thousandths of a pack, so broken cases work |
| `packs_received` | qty, null | |
| `price_snapshot` | money | Pack price when the order was placed |

The **order guide** itself is not stored. It works like the daily inventory par system and is calculated live:
- An ingredient appears when its stock is **at or below par, or within the near-par margin** (per-ingredient percent, otherwise the global `order_near_par_percent`, default 10%).
- `order_override = force` adds an item that is above par, and `skip` removes one that is below par.
- The suggested amount is enough to get back to par, rounded up to whole packs of the preferred vendor item (or single items when the pack is breakable). It is grouped by vendor. "Create order from guide" saves it as a draft `purchase_order` (12).

---

## 7. System tables

### `settings`
| Column | Type | Notes |
|--------|------|-------|
| `key` | TEXT PK | |
| `value` | json | |
| `updated_at`, `updated_by_id` | | |

Launch keys: `business_name`, `default_unit_system`, `default_labor_rate`, `stock_auto_deduct` (default true), `order_near_par_percent` (default 10). Each key has a typed definition in code with a default. Unknown keys are rejected.

### 7.2 `slug_aliases`
| Column | Type | Notes |
|--------|------|-------|
| `entity_type` | TEXT | `ingredient`, `recipe`... |
| `old_slug` | TEXT | |
| `entity_id` | INTEGER | |
| `created_at` | ts | |
| | | `PRIMARY KEY(entity_type, old_slug)`. Removed when the entity is deleted. Reusing an old slug for a new item removes the alias |

### `change_log` (D21)
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `change_group` | TEXT | One save that changes several fields shares a group code |
| `entity_type`, `entity_id` | TEXT, INTEGER | |
| `entity_label` | TEXT | Readable name, kept after a delete ("Task: Blue Cheese - Oct 22") |
| `action` | enum update/reopen/finalize/delete/restore | |
| `field` | TEXT, null | |
| `old_value`, `new_value` | json, null | |
| `user_id` | -> users, null | Detach |
| `user_name_snapshot` | TEXT | |
| `at` | ts | |

Written for finished records: finalized inventory days and their counts, completed tasks, sessions and assignees, and stock movements. Index `(entity_type, entity_id, at)`.

### `utility_costs` [STD] [NAMED] [ARCH]
| Column | Type | Notes |
|--------|------|-------|
| `monthly_cost` | money | |

Only the monthly total is stored. The Utilities page shows both the monthly total and a **daily breakdown**, calculated as the monthly cost divided by the actual number of days in that month (so February days cost more than July days). Today's flat `/ 30` is replaced. Reports that cover a date range add up the daily amounts for those exact days.

### Post-launch tables (designed now, created by later migrations)

- **`scheduled_jobs`** [STD] [NAMED]: `job_type`, `settings json`, `schedule` (cron-style text), `enabled`, `next_run_at`, `last_run_at`. Built with the Schedules page (D17).
- **`job_runs`** [PUB]: `job_id`, `started_at`, `finished_at`, `status` (running/succeeded/failed), `summary`, `log` (trimmed). Read-only.
- **`secrets`**: `key`, `ciphertext`, `updated_at`. Encrypted with an app-wide key from the environment. Never returned to the browser (F4, F5).
- **`price_sync_definitions`** [STD] [NAMED]: `vendor_id`, `steps json`, `credential_secret_key`, `match_rules json` (F5, designed in 14).
- **Backup targets** (F4): a Schedules job type whose settings point to a secret. No extra table expected.
- **Auth sessions**: 02 may add a table for sign-out and revoking tokens.

Removed: `migrations_applied` (replaced by Alembic's own `alembic_version` table).

---

## 8. Delete and archive rules

Every relationship uses one of four rules. Section 00 5.2 describes what the user sees.

| Rule | Meaning | "Delete this only" | "Delete with dependents" |
|------|---------|--------------------|--------------------------|
| **Cascade** | Child rows are part of the parent (recipe lines, custom units, sessions) | Deleted with the parent. Shown as a count, not listed | Same |
| **Block** | Something live depends on it (a batch uses a recipe) | Not allowed, and the blockers are listed | The dependents are deleted too, in one transaction, after a typed confirmation |
| **Detach** | Optional label (category, preferred vendor item) | Link cleared | Link cleared |
| **History detach** | Finished history (completed tasks, finalized counts, stock ledger, order lines, staff lists) | Link cleared, and the snapshot columns keep the name and values | Same. **History is never deleted by a cascade** |

**Archive** never breaks anything. Archived items disappear from pickers and lists but still show (with a badge) wherever they are already used, and still cost correctly.

### Relationship map

| Parent deleted | Child | Rule |
|----------------|-------|------|
| ingredient | recipe_ingredients, dish_ingredients, inventory_items | Block |
| ingredient | ingredient_units, vendor_items | Cascade |
| ingredient | stock_movements | History detach |
| vendor | vendor_items, purchase_orders | Block |
| vendor_item | price_history | Cascade |
| vendor_item | order_lines | History detach |
| vendor_item | ingredients.preferred_vendor_item_id | Detach |
| purchase_unit | vendor_items | Block |
| recipe | batches | Block |
| recipe | recipe_ingredients, recipe_sub_batches (as parent) | Cascade |
| batch | recipe_sub_batches, dish_batches, inventory_items, open tasks | Block |
| batch | finished tasks | History detach |
| dish | dish_batches, dish_ingredients | Cascade |
| inventory_item | open tasks | Block |
| inventory_item | inventory_counts, finished tasks | History detach |
| count_unit | inventory_items | Block |
| chore | inventory_day_chores | Cascade |
| chore | open tasks | Block |
| chore | finished tasks | History detach |
| inventory_day | inventory_counts, inventory_day_staff, inventory_day_chores, tasks | Cascade (deleting a whole day is an explicit, typed-confirm action on that day's own records) |
| task | task_sessions, task_assignees, owned stock_movements | Cascade |
| inventory_count | owned stock_movements | Cascade |
| purchase_order | order_lines | Cascade |
| order_line | owned stock_movements | Cascade |
| user | task_assignees, inventory_day_staff, change_log | History detach |
| user | user_work_days | Cascade |
| user | created_by/updated_by columns | Detach |
| category | everything using it | Detach |

The foreign keys use `ON DELETE CASCADE`, `RESTRICT`, or `SET NULL` to match, so the database itself refuses anything the service layer gets wrong.

---

## 9. Current-to-new mapping

| Current table | New | Notable changes |
|---------------|-----|-----------------|
| `users` | `users`, `user_work_days` | `role` + `is_admin` + `is_user` become one `role`. Schedule becomes rows. Username/password optional for employees. Wage as money |
| `categories` | `categories` | Unique per kind, slug, position, archive |
| `vendors` | `vendors` | `contact_info` split into fields |
| `vendor_units` | (retired) | Unused. Covered by vendor item per-unit pricing. `purchase_unit_name` becomes `purchase_units` |
| `par_unit_names` | `count_units` | Renamed, slug, archive |
| `ingredients` | `ingredients`, `ingredient_units`, `vendor_items`, `price_history` | Purchase/pack/price fields move to vendor items. Baking conversion becomes one reference measurement per ingredient. Item-count pricing becomes `dimension = count` |
| `recipes` | `recipes` | `deleted` becomes `archived_at` |
| `recipe_ingredients` | `recipe_ingredients` | Canonical qty plus entered amount/unit, position, prep note. Duplicates allowed |
| `recipe_batch_portions` | `recipe_sub_batches` | Mode enum, exact fraction, cycle check |
| `batches` | `batches` | One per recipe, named by the recipe. Nine scale switches become a 1/16x-8x slider with per-batch limits. Labor rate default moves to settings. Stock deduct mode |
| `dishes` | `dishes` | Price as money |
| `dish_batch_portions` | `dish_batches` | Same as recipe sub-batches. Costing fixed |
| `dish_ingredient_portions` | `dish_ingredients` | Canonical qty |
| `inventory_items` | `inventory_items` | Optional ingredient link (F1). Clearer count-unit modes |
| `inventory_days` | `inventory_days`, `inventory_day_staff` | Status, reopen tracking, staff as rows |
| `inventory_day_items` | `inventory_counts` | One override enum. Finalize snapshots. Unique per day |
| `janitorial_tasks` | `chores` | Renamed Chores, slug, archive |
| `janitorial_task_days` | `inventory_day_chores` | Unique per day |
| `tasks` | `tasks`, `task_assignees` | Random public ID. Kind and status enums. Assignees as rows with wage snapshots. Frozen labor. Stock deduct override |
| `task_sessions` | `task_sessions` | Pause = end of session. Pause columns removed |
| `utility_costs` | `utility_costs` | Money, slug, archive. Daily breakdown by actual days in the month |
| `migrations_applied` | (removed) | Alembic |
| (new) | `units`, `purchase_orders`, `order_lines`, `stock_movements`, `settings`, `slug_aliases`, `change_log` | Launch |
| (new) | `scheduled_jobs`, `job_runs`, `secrets`, `price_sync_definitions` | Post-launch |

Things the current app keeps outside the database stay outside it: backups (files), How-To docs (markdown files), and email credentials (environment). Email recipients are still picked per send from users that have an email address.

---

## 10. Indexes (beyond primary keys and the unique constraints above)

- Every foreign key column (SQLite does not index them automatically).
- `archived_at` on catalog tables, for "active only" lists.
- `tasks(day_id, status)`, `tasks(batch_id, finished_at)` for actual/average labor figures.
- `task_sessions(task_id) WHERE ended_at IS NULL` (unique: one running session).
- `stock_movements(ingredient_id, occurred_at)`, plus a partial index on `kind = 'count'`.
- `price_history(vendor_item_id, observed_at)`.
- `change_log(entity_type, entity_id, at)`.

---

## 11. Review decisions (round 1)

1. **Labor with several assignees:** task minutes x the highest assigned wage (section 5, `task_assignees`).
2. **Duplicate ingredients:** allowed on recipe and dish lines. Lines are addressed by their own code, and the prep note tells them apart.
3. **Vendor units:** retired. Vendor items priced per pound or gallon cover that case.
4. **Utilities:** monthly total stored, daily breakdown shown using the actual days in each month.
5. **Stock from inventory:** confirmed. Ingredient-linked counts post stock counts, and completed batch tasks (direct or through an inventory item) use up the recipe's ingredients.
6. **Batches:** one batch per recipe, named by the recipe. All sizes come from its scale slider.
7. **Chores:** confirmed as the new name for janitorial tasks.

## 12. Review decisions (round 2)

- **Conversions:** one reference measurement per ingredient, entered either direction, used for costing, the metric view, and stock. Weight oz and fluid oz are always separate. "Fill in as water" is an optional shortcut, never an assumption.
- **Missing conversion:** the line offers "Add conversion" (popup) or "Leave out of cost".
- **Scaling:** slider from 1/16x to 8x with snap points, fine steps between them, and per-batch limits. Kitchen-friendly display with 1/4 tsp as the smallest step.
- **Price history:** filter by month, quarter, year, or all time. Admin purge with typed confirmation.
- **Order guide:** par-based like daily inventory. Near or below par is listed, and you can force-add or skip items.
- Accepted as suggested: tiny-fraction money, several vendor options per ingredient, employees without sign-in, inactive vs archived, history never erased, order guide calculated live.

_No open questions remain for 01._
