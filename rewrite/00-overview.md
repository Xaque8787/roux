# 00 - Overview

Status: REVISED - review round 3 incorporated, pending approval

This is the root blueprint for the Roux rewrite. It records the decisions made so far, sums up the current system, and sets the conventions every later sub-blueprint follows. Feature details belong in sub-blueprints 05-09, not here.

---

## 1. Decisions locked in

| # | Decision | Notes |
|---|----------|-------|
| D1 | **SPA + JSON API** | React frontend, FastAPI backend that serves JSON only. Jinja templates are retired. |
| D2 | **Full rewrite on a branch** | `main` is frozen apart from critical fixes. When the rewrite is done, it replaces `main` with a force push. |
| D3 | **SQLite stays** | The target is a Raspberry Pi 3 B with 1 GB RAM. A Postgres sidecar would cost too much memory. |
| D4 | **SQLite tuned for concurrency** | WAL journal mode, `busy_timeout`, short transactions. Details in 01 and 11. |
| D5 | **Alembic owns the schema** | One initial migration builds a clean schema. Later changes use Alembic batch mode where SQLite needs it. `create_all` and hand-rolled migration scripts are removed. |
| D6 | **Blank-slate data** | No migration from production is required. An optional recipe/ingredient import can be done after launch (see section 7). |
| D7 | **Self-hosted Docker, one container** | Same deployment model as today: app plus SQLite file in a named volume. Vendor price sync (F5) is **bundled inside the app**, not run as a sidecar. Postgres stays possible later through `DATABASE_URL`, but it is not a goal. |
| D8 | **Blueprint process** | One sub-blueprint per concern. Each one is reviewed and approved before the next is written. New domains/features are listed early in `99-feature-backlog.md` so the schema accounts for them, then designed in detail inside the relevant section. |
| D9 | **Three role tiers** | **Admin**: full control and access. **Manager**: login; runs daily operations (start/finalize day, take inventory, assign tasks) and most of the app. **Employee**: no login; can be assigned tasks and can start/finish them; used for labor tracking. The old `user` role and the `is_admin`/`is_user` flags are removed. |
| D10 | **64-bit only: `linux/amd64` + `linux/arm64`** | One multi-arch manifest on GHCR, and `docker pull` picks the right one automatically. The Pi 3 B on its 64-bit OS uses `arm64`. 32-bit images (`386`, `arm/v7`) are dropped: Playwright (F5) can't run there, they need slow compile-from-source builds, and two feature sets would have to be tested. This can be revisited later by building those images without price sync. |
| D11 | **Iroh-ready networking** | Remote access will come later through iroh. The app must work unchanged behind any tunnel or proxy (see section 6). |
| D12 | **TypeScript + Tailwind** | Neither choice affects iroh; picked for maintainability. |
| D13 | **Shared-device task flow** | A Manager or Admin signs in on a kitchen device. Employees (no login) tap tasks assigned to them to start and stop them. Hardening is deferred: a likely approach is a PIN-locked "task station" view that asks for a Manager/Admin PIN before you can leave the page. The data model leaves room for a per-user PIN hash so this can be added after the rewrite. |
| D14 | **Keep the CI/versioning system** | GHCR at `ghcr.io/xaque8787/roux`. `.dockerversion` holds the version. A push to `main` builds the image and tags it `latest` plus that version. Manual dispatch stays available. Details in 11. |
| D15 | **Launch scope includes F1 + F2** | Stock/ordering and the US/Metric unit system are part of the rewrite itself, not later additions. |
| D16 | **F5 follows F1** | Vendor price sync is built right after stock/ordering, bundled in the app. Chromium starts only for a run and exits afterwards, so it uses no memory while idle. A swap file covers the occasional peak on a 1 GB Pi. |
| D17 | **Generic Schedules page** | Administration > Schedules is one job manager for all recurring work (vendor price pulls, S3 backups, email reports, future jobs). Each job type plugs in with its own settings; the page handles timing, enable/disable, "run now", and run history. It is built with the first scheduled job (F5). |
| D18 | **F3, F4 later** | Iroh access and S3 backups come after launch. Their constraints are still respected now (section 6, D17). |
| D19 | **Readable URLs, no sequential IDs exposed** | See section 5.1. |
| D20 | **Full CRUD + dependency-aware changes everywhere** | See section 5.2. |

---

## 2. Current system snapshot (what we are replacing)

**Stack:** FastAPI 0.104, SQLAlchemy 2.0, Pydantic 2.5, Jinja2 + Bootstrap 5 + vanilla JS, python-jose (JWT), passlib/bcrypt, Resend (email), markdown, gunicorn with 1 uvicorn worker, Python 3.11-slim image published to GHCR.

**Size:** about 22k lines in total. The largest files are `routers/inventory.py` (1.5k), `models.py` (1k, with business and cost logic mixed into the ORM), and `inventory_day.html` (1.3k).

**Domain areas** (taken from the nav and the routers):
- Employees (stored in the `users` table: wage, schedule, role)
- Ingredients, Categories, Vendors, Vendor Units, Par Unit Names
- Recipes (ingredients plus batch portions from other recipes, soft delete)
- Batches (fixed or variable yield, labor estimates, scaling)
- Dishes (batch portions plus direct ingredients, margins)
- Inventory (items, daily counts, day finalization, reports)
- Tasks (prep and janitorial tasks, timed sessions, labor cost)
- Utilities (monthly costs, prorated)
- Administration (backup and restore), How-To docs viewer, email reports

**Data model:** 23 tables, listed in 01.

### Problems found that the rewrite must fix

1. **The event loop is blocked. This is the most likely cause of the SSE concurrency issue.** Nearly every route is `async def` but makes synchronous SQLAlchemy calls. With a single worker, each DB call freezes the event loop, which stalls every open SSE stream and every other request until that call returns. SQLite locking makes this worse, but it is not the main cause. Switching to Postgres would not have fixed it.
2. **No WAL and no busy_timeout.** SQLite runs in its default rollback-journal mode, so writers block readers.
3. **Fragile DB path detection.** The code guesses whether it is running in Docker by checking which folders exist. Inside Docker it ignores `DATABASE_URL`, and if the data folder is not writable it **silently falls back to `/tmp`, so data is not saved**.
4. **Schema drift.** `create_all` runs at startup and is patched by ad-hoc migration scripts. The User model has redundant `role`, `is_admin`, and `is_user` fields.
5. **Business logic lives inside ORM models.** Cost and conversion math is mixed into `models.py`, so it can't be tested on its own.
6. **Auth is duplicated.** `get_current_user` and the role checks exist in both `auth.py` and `dependencies.py`. There is a default fallback `SECRET_KEY`, and JWT expiry is computed from naive local time instead of UTC.
7. **CORS is wide open.** It allows `*` together with credentials. A same-origin SPA does not need CORS at all.
8. **Routes are scattered.** One stats endpoint sits in `main.py`, and HTML and JSON routes are mixed together.
9. **SSE logging is too noisy.** Every broadcast is logged at INFO level, which wears out the Pi's SD card.

---

## 3. Target stack

### Backend
- Python 3.11+, FastAPI (current version), Pydantic v2
- SQLAlchemy 2.0 with the typed `Mapped[]` style, **synchronous** sessions
- Route handlers that touch the DB are plain `def`, not `async def`, so FastAPI runs them in its thread pool and the event loop stays free for SSE. Only the SSE stream handlers are `async`.
- Alembic for migrations (`render_as_batch=True` for SQLite)
- Auth: JWT in an HttpOnly cookie (details in 02). `PyJWT` replaces the unmaintained `python-jose`, and `bcrypt` is used directly instead of passlib.
- Email: Resend (kept)
- Server: a single uvicorn process. With one process, the in-memory SSE broadcaster stays correct and memory use stays low.

### Frontend
- React + TypeScript, built with Vite
- React Router for client-side routing
- TanStack Query for server data: caching, refetching, and invalidation when SSE events arrive
- Tailwind CSS for styling (replaces Bootstrap)
- Built into static files that FastAPI serves from the same origin, so there is no separate frontend server and no CORS

### Infrastructure
- One Docker image, multi-stage: Node build stage, Python build stage, slim runtime
- Multi-arch images (`linux/amd64`, `linux/arm64`) built by GitHub Actions and pushed to GHCR. Chromium for Playwright is included in the image.
- SQLite file in a Docker **named volume**
- Entrypoint runs `alembic upgrade head`, then starts uvicorn

---

## 4. Proposed repository layout

```
roux/
  backend/
    app/
      main.py              # app factory, mounts API + SPA
      config.py            # settings from env (pydantic-settings), fail-fast
      db.py                # engine, session, SQLite pragmas
      models/              # ORM models, one module per domain
      schemas/             # Pydantic request/response models per domain
      services/            # business logic: costing, conversions, scaling
      api/                 # routers per domain, all under /api
      realtime/            # SSE broadcaster + stream endpoints
      auth/                # tokens, password hashing, role dependencies
    alembic/
    tests/
    pyproject.toml
  frontend/
    src/
      api/                 # typed fetch client + query hooks per domain
      features/            # one folder per domain (recipes, inventory, ...)
      components/          # shared UI pieces
      routes.tsx
    package.json
    vite.config.ts
  docs/                    # user How-To guides (kept, served by the app)
  rewrite/                 # these blueprints
  Dockerfile
  docker-compose.yml
```

The rule is that **routers stay thin, services hold the logic, and models hold only data**. Cost calculations live in `services/` and have unit tests.

---

## 5. Core principles

These rules apply to every domain. Each sub-blueprint must show how it satisfies them.

### 5.1 Identity and URLs

- **URLs and API paths use meaningful identifiers and never sequential database IDs.**
  - Named things are addressed by slug: `/ingredients/carrots`, `/recipes/blue-cheese-dressing`, `/api/vendors/sysco`.
  - Date-based things are addressed by date: `/inventory/days/2026-10-22`, with **one inventory day per calendar date** enforced by a unique constraint.
  - Child rows are addressed under their parent by the child's natural key: `/api/recipes/blue-cheese-dressing/ingredients/blue-cheese`.
  - Things that have no name or date (task sessions, stock movements, sync runs) use a **short random ID** (for example `k3f9x2qa`). It is never sequential or guessable.
- Integer primary keys still exist for foreign keys and joins, but they **never leave the server**. API responses identify records by slug, date, or random ID.
- **Names are unique** within each table. The comparison ignores case and surrounding spaces, and is enforced by a database constraint, not only by the UI. Saving a duplicate name gives a clear message ("An ingredient named Carrots already exists").
- **Slugs** are generated from the name. If two different names produce the same slug ("Carrots!" and "carrots"), the second one gets a `-2` suffix, then `-3`, and so on.
- **Renaming changes the slug, and old URLs keep working.** Previous slugs are kept as aliases, and visiting one redirects to the current URL. Bookmarks and shared links do not break.
- **Archived items keep their name reserved.** Creating a new item with an archived item's name offers to restore the archived one instead.

### 5.2 CRUD and cross-domain dependencies

- **Everything users enter can be created, viewed, edited, renamed, archived, restored, and deleted.** There are no write-only records. Read-only exceptions are system-generated history (finalized inventory days, completed task sessions, stock movements, sync/backup runs). These can only be corrected through an explicit adjustment, which is itself recorded.
- **Live references.** Batches, dishes, inventory items, stock, and tasks link to the current recipe/ingredient rather than to a copy. Editing a recipe updates every batch, dish, and cost that uses it.
- **History is frozen.** Finalized or completed records store a snapshot of the values they used (cost, quantity, unit, name). Editing a recipe today does not rewrite last month's reports.
- **Dependency check before a destructive change.** Before an archive or delete, the server returns an **impact list** of everything affected, grouped by domain. For example: deleting "Blue Cheese Dressing" affects 1 batch (Blue Cheese Batch), 1 inventory item, 2 dishes, and 3 prep tasks.
- **The user chooses what happens:**
  1. **Archive (recommended, the default)**: hidden from pickers and lists, existing links keep working with an "archived" badge, and it can be restored at any time.
  2. **Delete this only**: allowed only if nothing depends on it. Otherwise the user is told what still uses it.
  3. **Delete with dependents**: shows the full list once more and needs a typed confirmation. Removes the item and everything listed, in **one transaction**. Frozen history keeps its snapshots and is never deleted by a cascade.
- **The preview matches the action.** The impact list and the actual delete use the same service function, so the result can never differ from what was shown.
- **Every relationship has a declared rule** in 01: cascade with parent (a recipe's own ingredient lines), block (a recipe used by a batch), or detach (an optional link set to empty). The database enforces these with foreign keys (`PRAGMA foreign_keys=ON`, which SQLite leaves off by default). The service layer runs the cascades explicitly.
- **No circular recipes.** A recipe that uses batch portions from other recipes is checked on save so it can never end up using itself, directly or indirectly.
- **Changes broadcast.** Every create, update, archive, or delete sends a realtime event, so other screens update themselves (see 10).

---

## 6. Cross-cutting conventions (expanded in 03 and 04)

- All JSON routes live under `/api/...`. Every other path returns the SPA's `index.html`.
- Errors use one consistent JSON shape, and the frontend shows them in a standard way.
- All timestamps are stored in UTC and converted to the configured `TZ` only for display and for "business day" logic.
- Money is stored as integer cents, or Decimal. This is decided in 01. Floats are not used for money.
- Secrets have no defaults. The app refuses to start without `SECRET_KEY`.
- Logs are at INFO for lifecycle events and DEBUG for per-event detail, written to stdout only.

### Tunnel/proxy readiness (for iroh)
- The frontend uses only **relative URLs** (`/api/...`, `/events/...`). No hostnames or ports are baked into the build.
- One origin serves both the SPA and the API, so there is no CORS and no cross-site cookie problem.
- The cookie `Secure` flag is configurable, because a tunnel may present plain `http://localhost` to the browser.
- SSE sends heartbeats and disables proxy buffering (`X-Accel-Buffering: no`), and the client reconnects automatically. This lets streams survive tunnel hiccups.
- No feature depends on the client's IP address or on LAN-only discovery.
- The browser-based iroh client (backlog F3) may run from a different origin (GitHub Pages). To support it: all frontend network calls go through one API client with a swappable transport, SSE is read with a fetch-stream reader rather than `EventSource`, and auth accepts either a cookie or a bearer token. Details in 02/04/13.

---

## 7. Memory budget (Pi 3 B, 1 GB)

| Component | Target |
|-----------|--------|
| OS + Docker | ~300 MB |
| uvicorn + app | <= 120 MB |
| SQLite | in process (negligible) |
| Chromium during a price sync (F5) | ~200-400 MB, only while a run is active |
| Headroom while idle | > 500 MB |

- The built frontend is static files and uses no server memory beyond serving them.
- Price sync runs in a **child process**. When it ends, all of its memory goes back to the system, and a crash in the browser can't take the app down. Only one sync runs at a time.
- Recommended Pi setup: a 1-2 GB swap file (documented in 11).

---

## 8. Scope and phasing

- **Launch:** all current domains plus F1 (stock/ordering) and F2 (US/Metric).
- **Right after launch:** F5 (vendor price sync) and the generic Schedules page.
- **Later:** F3 (iroh), F4 (S3 backups, as a Schedules job).
- **Out of scope:** migrating production data (an optional import script may come later), Postgres support beyond a configurable `DATABASE_URL`, multiple workers.

---

## 9. Sub-blueprint index

| File | Concern | Status |
|------|---------|--------|
| 00-overview.md | Architecture, stack, layout | Draft |
| 01-database-schema.md | Tables, relationships, indexes, money/time types | Pending |
| 02-authentication.md | Setup wizard, login, sessions, roles | Pending |
| 03-api-design.md | Conventions, endpoint map, errors | Pending |
| 04-frontend-architecture.md | React structure, routing, data fetching | Pending |
| 05-recipes-ingredients.md | Ingredients, units, conversions, recipes | Pending |
| 06-dishes-batches.md | Batches, yields, scaling, dishes, margins | Pending |
| 07-inventory.md | Items, pars, days, finalization, reports | Pending |
| 08-employees-tasks.md | Employees, prep/janitorial tasks, sessions, labor | Pending |
| 09-admin-utilities.md | Admin, Schedules page, backup/restore, vendors, categories, utilities, docs, email | Pending |
| 10-realtime-sse.md | Broadcaster, rooms, events, client reconnect | Pending |
| 11-deployment.md | Dockerfile, compose, entrypoint, WAL, multi-arch CI | Pending |
| 12-stock-ordering.md | Stock ledger, pars, order guide (F1) | Pending |
| 13-remote-access.md | Iroh connectivity, WASM client (F3) | Pending |
| 14-vendor-price-sync.md | Headless price pulls, step builder (F5) | Pending |
| 99-feature-backlog.md | New domains/features not in the current code | Collecting |

---

## 10. Open questions for review

1. **Edits to frozen history:** confirm that finalized inventory days and completed task sessions can only be corrected by an adjustment that is recorded, never edited directly. Or should Admins be able to edit them directly?
2. **Inventory days:** confirm it is exactly one per calendar date (no second count on the same date).

### Notes carried into 11-deployment
- The current workflow has no QEMU setup step, and its final "Image digest" step refers to a build step ID that doesn't exist, so it prints nothing. Both will be fixed.
- The workflow's `paths:` filter will be updated for the new `backend/` and `frontend/` folders.
- Change `platforms` to `linux/amd64,linux/arm64` (the same as today).
- The frontend build stage runs on the build machine's native architecture (its output is plain static files).
- Chromium adds roughly 300-400 MB to the image. A smaller headless-only Chromium build will be evaluated.
