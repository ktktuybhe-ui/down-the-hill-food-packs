# Down the Hill — Build 36 consolidated scope (17 Nov 2026)

This document records user-reported on-device QA and requested features; it is not a claim that iOS changes have shipped.

## Confirmed Build 35 iPhone QA summary
- 13 of 16 tests attempted: 7 passed, 2 partial, 4 failed; 3 untested.
- Passed: 01 installed Build 35, 03 five country packs listed, 07 natural units (khinkali-style), 09 linked kcal/macros, 14 meal-item/name editing, 15 home screen widget, 16 backup export/Apple Health.
- Partial: 04 install/use a pack, 10 unified search/deduplication.
- Failed: 02 TestFlight migration photos initially not visible; 05 offline Hebrew search for Georgia test terms; 08 Margarita/drinks ml serving, 11 label inline image zoom.
- Untested: 06 Files .dthpack import, 12 multipage menu photo analysis, 13 two views of the same meal without double counting.
- Crucial follow-up: backup 6.json contained embedded JPEG photoArchive and all referenced photoIDs. User restored from backup and reported "שיחזר הכל"; whether absolutely every photo is visible was not independently re-checked. Do not assume the root cause is fixed simply because restore worked.
- The user reports the other tested food providers are useful and Georgia is the sole major outstanding country pack. Distinguish absent traditional products from defective FTS/offline loading.

## P0 — no data loss / photo migration
1. Investigate why photos were missing immediately after TestFlight migration while food history existed. On-device compare referenced IDs, stored blobs/paths, backup photoArchive, and gallery UI caching. Preserve original files and prevent orphaning; migration must be additive/idempotent. Test same-bundle-ID upgrade and backup restore.
2. Backup/import UX: separate recent backup from prior backup, user preview of counts/photos, safe pre-restore backup and rollback, verify that image bytes not just IDs survive. Restore NEVER destroys personal foods, weigh-ins, goals, recent meals/photos without clear confirmation and safe preservation.
3. Preserve current TestFlight install, bundle ID, Health permissions and local data. No destructive reinstall/reset.

## P0 — Georgia country food coverage
1. Current Georgia travel.ge 1.0 contains 574 Open Food Facts marketplace products, not Georgian restaurant cuisine. Curated aliases alone do NOT create rows, causing missing khinkali/khachapuri and salads. Keep existing commercial product entries.
2. Curate and add traceably sourced traditional dishes: meat khinkali, mushroom/cheese/potato khinkali, Adjarian/Imeruli/Megruli khachapuri, sulguni, churchkhela, tkemali, lobio, ajapsandali, mtsvadi, etc. See builder/georgia_traditional_coverage.json.
3. Explicit user's highest-priority preference: green spinach salad (Ispanakhis salata) AND spinach-walnut pkhali are distinct foods; comprehensive Georgian salads include cucumber/tomato with AND without walnuts, herb/green salad, beetroot, carrot walnut, green tomato walnut, eggplant walnut, green bean, beet greens, leek and cabbage pkhali, and assorted pkhali. Variants differ nutritionally, should not be merged. Expand coverage as credible data becomes available.
4. Recipe estimates require transparent source_URL, 100g macros and portion weight, "estimate based on recipe" label, editable natural units; no fabricated nutrient values. A source with some nutrition but unclear redistribution terms is a research candidate, not automatically a pack ingredient. Do not copy unlicensed Georgian composition tables.
5. Preserve source language and aliases and FTS for Hebrew, English and Georgian, OFF product IDs/nutrients, per-100g/ml basis, original georgia-1.0 and all other releases. Build a new version/tag only after hard QA. Never silently overwrite the old pack.
6. On iPhone test 5 known *existing packaged* Georgian items in all languages and airplane mode to distinguish data omission vs broken FTS; test all new traditional foods.

## P0 — serving & time correctness
1. Margarita and other drinks: allow natural ml/unit/portion; source per 100g is not automatically 100ml. Show editable estimated density when conversion is needed; linked kcal/macros update in one operation.
2. Meal createdAt/plannedAt != actual eatenAt: clicking "אכלתי" records the actual time then; planned meals do not consume budget; editable retrospective date/time without changing iPhone system clock. Historical meal timestamps remain unchanged unless explicitly edited; migration preserves backward compatibility and diary-day correctness.

## P1 — food pack screen and download UX
1. Present **Georgia, Greece, Italy, Spain, France, Austria** as friendly English display names, not technical travel.ge, OpenFoodFacts, filenames or region codes. Group Austria's two subpacks under one country.
2. Within each installed pack card show **"הסר חבילה"** with confirmation. No separate red remove list below. Uninstalled show "הורד חבילה". A genuinely newer version shows "עדכן". Installed exact-version pack must never also show as downloadable.
3. Uninstall removes ONLY pack provider files/index; never meal nutritional snapshots, photos, profile, goals, personal foods or weigh-ins. App prevents accidental double install and protects download integrity. Show installed count, size, version, download state and offline confirmation in readable UI.

## P1 — food search, media and app usability
1. Universal search continues across Ministry of Health, USDA core, country packs, history and personal foods; carefully deduplicate identical IDs, preserve distinct brands/recipe variants and provenance. Source provider not a separate visible workflow.
2. Inline food-label photo with pinch zoom and edit fields; preserve image on OCR failure. Inspect obstructing portion popover and RTL alignment in meal editor (user screenshot), keep destructive controls separated from inputs.
3. Two meal photos must merge as one meal and not double-count food. Multi-page menu import and Files .dthpack import need real on-device QA (currently untested).
4. Contextual practical serving defaults, always editable. No automatic calorie credit for steps unless explicitly changed by user.

## Release acceptance
- Before Build 36, export validated user backup including JPEG photoArchive; never delete current TestFlight app or change Bundle ID.
- Distinguish verified fixed vs regression tested vs open/unimplemented. Run old Build 35 pass items as regression.
- Test old photos, timestamps, planned/eaten transitions, Georgian language search offline, pack download/update/remove, 100g->natural portion recalculation, backup/restore and iCloud/Health continuity.
- Only label Build 36 shipped when actual Xcode build/TestFlight upload AND real phone QA are confirmed.
