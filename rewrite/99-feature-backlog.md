# 99 - Feature Backlog

Features and domains that are NOT in the current code. Each one gets a short entry here first, so the schema (01) and navigation (04) can plan for it. Full design happens in the section listed under "Lands in".

## Entry template

```
### F<n>: <name>
- What / Who uses it / Lands in / Touches data / Priority
- Design notes and risks
```

---

## F1: Stock and ordering

- **What:** Keep track of how much of each ingredient is on hand. Set a par (target) level per ingredient. Generate an **order guide** for each vendor that shows what to order to get back up to par. Stock goes down automatically when prep tasks or batches are completed.
- **Who:** Manager (order guide, receiving), Admin (setup). Employees affect stock indirectly by finishing tasks.
- **Lands in:** new `12-stock-ordering.md`. The schema is planned in 01 from the start.
- **Touches data:** yes. New tables.
- **Priority:** **Launch (D15)**

**Design notes**
- Stock is kept as a **ledger of movements** (received, used by batch, waste, count adjustment) rather than a single number that gets overwritten. The current level is the sum of the movements. This gives a history and makes mistakes easy to fix.
- Inventory counts become "count adjustment" movements, which ties the current Inventory domain into stock.
- Taking stock out on task completion works like this: task, then batch, then recipe ingredients times the scale factor, then a stock movement for each ingredient. This **depends on F2**, because every quantity has to convert into the ingredient's stock unit.
- **Automatic removal rules (decided):**
  - **Global setting** "Remove stock automatically when tasks are finished". **On** by default. When it is off, finishing a task creates no stock movements, and the manager keeps stock accurate with manual counts before ordering.
  - **Per-task override:** each task can be set to *Use global setting* (default), *Always remove*, or *Never remove*.
  - **Only tasks linked to a batch or recipe can affect stock.** Janitorial and general tasks have nothing to remove, and the stock options are hidden for them.
  - If a finished task is edited (for example, a different scale) or deleted, its stock movements are adjusted or reversed to match.
- This needs a **vendor item** concept: what a vendor sells (SKU, pack size, case price), linked to an ingredient. F5 needs the same thing, so it is designed once in 01.
- Possible later addition: orders/purchase orders (placed, then received), so that receiving an order adds stock automatically.

## F2: US / Metric unit system

- **What:** A proper unit engine that replaces the inventory "backing measurements converter". Recipes and scaled batches can be shown in US or Metric with a toggle.
- **Who:** Everyone (display preference). Admin sets the default.
- **Lands in:** 01 (how quantities are stored) and 05 (the engine and the UI).
- **Touches data:** yes. **This is foundational and must be decided in 01**, because it affects every quantity column.
- **Priority:** **Launch (D15).** F1 depends on it.

**Design notes**
- Every quantity is stored in a canonical base unit for its dimension: **grams** (weight), **milliliters** (volume), or **each** (count). The unit originally entered is kept too, so it can be shown the way the user typed it.
- Converting between weight and volume needs a **density per ingredient** (for example, 1 cup of flour is about 120 g). Conversion is only offered when a density is set.
- Pack/case units (a "case" is 6 x #10 cans, for example) are defined per vendor item and convert down to base units.
- Display rounding is "kitchen-friendly". US amounts show as fractions (1 1/2 cup rather than 1.5 cup) and change to a larger unit at sensible points (48 tsp becomes 1 cup). Metric shows g/kg and ml/L.
- The conversion math lives in `services/` and is covered heavily by unit tests.

## F3: Iroh remote connectivity

- **What:** Reach the app from anywhere with no port forwarding, using iroh. A browser connects through a **WASM client page hosted on GitHub Pages**.
- **Who:** Admin and Managers, remotely.
- **Lands in:** new `13-remote-access.md`. It also constrains 02 (auth) and 04 (the frontend data layer) **now**.
- **Touches data:** a little (node identity/keys, which devices are allowed).
- **Priority:** Later (D18). The design accommodates it now.

**Design notes and impact on earlier decisions**
- If the app runs from a GitHub Pages origin, it is **no longer the same origin as the Pi**. Requests travel over an iroh connection instead of normal HTTP from the browser. This affects two choices made in 00:
  1. **Frontend:** every API call and SSE stream goes through one API client layer that can **swap its transport** (normal `fetch` locally, an iroh-backed transport remotely). No `fetch()` calls scattered through the code. This will be written into 04.
  2. **Auth:** cookies may not work across a custom transport. Auth will accept **either** an HttpOnly cookie (local) **or** a bearer token in a header (remote client). This will be written into 02.
- SSE needs a streaming path over iroh. The browser's `EventSource` won't work there, so the client uses a fetch-stream-based SSE reader that works with both transports.
- Iroh in the browser can only connect through relays (no direct hole-punching). This will be noted for latency.

## F4: Scheduled S3 backups and restore

- **What:** Back up the whole database to any S3-compatible storage on a custom schedule, and restore from a chosen backup. The design will follow the approach of the user's other app that already does this.
- **Who:** Admin.
- **Lands in:** 09 (as a job type on the Schedules page) and 11 (runtime).
- **Touches data:** yes. Backup settings and a backup history log. The timing and run history come from the generic Schedules system (D17).
- **Priority:** Later (D18).

**Design notes**
- The scheduler (APScheduler) runs inside the app process. That is safe because 00 commits to a single process.
- Backups use SQLite's **online backup API** (or `VACUUM INTO`). Copying the file directly is not safe in WAL mode and can produce a corrupt backup.
- Restore: download the backup, check its integrity and Alembic version, pause writes, swap the file, run migrations, then reconnect. Restoring an older backup has to migrate it forward.
- S3 credentials are encrypted at rest (see "Secrets" below).
- Memory: `boto3` is heavy for a Pi 3. A lighter S3 client will be evaluated in 11.
- Optional retention policy (keep the last N backups, or N days).

## F5: Vendor price sync (headless browser)

- **What:** Neither vendor offers an API. A headless browser (Playwright) logs into the vendor's ordering site and pulls item prices. Admins **build the steps inside the app** (go to page, fill in login, click, wait, read price) so it works with any vendor's web ordering platform.
- **Who:** Admin (builds the steps). Managers see the updated prices.
- **Lands in:** new `14-vendor-price-sync.md`. Scheduled through the Schedules page (D17).
- **Touches data:** yes. Sync definitions (steps), vendor credentials, and price history linked to vendor items (shared with F1). Run history comes from the Schedules system.
- **Priority:** Right after F1 (D16). **Bundled in the app**, 64-bit images only (D10).

**Design notes and risks (important)**
- **Hardware limits:** headless Chromium needs about 200-400 MB of RAM while running, which is a large share of the Pi 3's 1 GB. It also adds roughly 400 MB or more to the image.
- **Architecture limits:** Playwright ships browsers only for 64-bit Linux (`amd64`, `arm64`). It **cannot run on `386` or `arm/v7`**.
- **Decision:** bundled in the main image (D7, D16). Each run starts Chromium in a child process, does its work, and exits, so nothing stays in memory between runs. Only one run at a time. 32-bit images were dropped so the feature works everywhere (D10).
- The step builder is a small, safe action list (goto, fill, click, wait-for, extract-text, select a row by text, next page) with **no arbitrary code**. Extracted prices are matched to vendor items by SKU or name, and a manager reviews them before they are applied.
- Vendor logins are encrypted at rest. Sites with MFA or captchas may not be possible to automate; that will be documented as a known limitation.
- Check each vendor's terms of use. Some prohibit automated access.

---

## Cross-cutting needs these features create

- **Encrypted secrets storage** (F4 S3 keys, F5 vendor logins). One app-wide encryption key comes from the environment, and secrets are never sent back to the browser after they are saved. Belongs in 01/02.
- **Background jobs** (F4 backups, F5 price pulls, email reports, future jobs). One in-process scheduler behind a generic **Administration > Schedules** page, with job types, per-job settings, enable/disable, run now, and run history (D17). UI in 09, runtime in 11.
- **Vendor items** (F1, F5). Designed once in 01.

## Open questions

_None for now._
