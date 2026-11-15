# Down the Hill · mandatory serving standard for ALL new food packs (Build 34+)

1. A canonical per-100g or per-100ml nutrition reference is REQUIRED and must remain unchanged during portion conversion. Never overwrite label or source values for convenience.
2. Each record MUST have base_unit exactly 'g' or 'ml', and valid kcal, protein, carbohydrates and fat. No fabricated nutrition values. FTS and metadata count must match SQLite; checksums SHA256.
3. A genuine source serving_size, if present, MUST be finite, >0 and <=5000 in the same native unit. An invalid source serving fails prepublication QA (legacy installed packs safely ignore bad source serving).
4. The app's shared FoodPortionCatalog adds a source serving when available, recognized natural portion estimates with editability, or a clearly labeled user-editable fallback. Grams/ml always remain available for precise entry.
5. Drinks documented by mass (g) may show estimated ml ONLY with an explicit density assumption (currently 1g/ml), editable amount and source-mass option. Do not silently claim per-100g = per-100ml or rewrite historical nutrition data.
6. Names and metadata in Hebrew/English/local languages are searchable when present. Do not claim a translation is human-reviewed without manual QA. Preserve original language and source provenance.
7. Each new Release must pass the source/serving/SQLite/FTS/SHA256 tests before promotion. Candidate, draft and prerelease packs MUST remain blocked inside Build 33+.
8. If a pack is removed, foods already eaten must remain in the user's saved personal foods and meal diary, and removal must fail safely if preservation fails.
9. Georgia (travel.ge): Open Food Facts is ODbL 1.0; Georgian 2009 National Association of Nutritionists tables are not redistributed until rights are verified. Traditional recipes need authenticated/traceable nutrient data, not invented calorie values.
10. Test every new country with ordinary foods, packaged products, drinks, and 3 traditional dishes before approving. Evaluate natural portions on the actual iPhone.

The verifier included in the downloadable Build 34 source bundle:
Tools/verify-serving-contract.py --strict [new-pack.dthpack]
