# Country food packs — current development status (16 Nov 2026)

This section supersedes the dated 15 Nov notes below. Check live GitHub Actions before assuming completion.

- App source: Down the Hill Build 34 (v0.6.6) prepared for Xcode installation; actual phone installation and user data remain separate. Its FoodPackRegistry supports travel.XX and optional removable International Core. Universal portion engine supplies source servings or explicit editable estimates; original per-100g/ml data must remain immutable.
- Austria 1.4 and International Core 1.0 are the existing ordinary published Releases, with immutable independent ZIP backups, manifest and SHA256.
- Georgia source scan: 2,430 country-tagged CSV products; 574 with complete valid protein/carbs/fat/energy, 28 source serving sizes, 34 native ml-based nutrition items, 5 Hebrew names in SOURCE candidate. Verified SQLite/FTS/pack SHA256. Source candidate `country-georgia-source-qa-3` is a PRERELEASE and **NOT app-installable**.
- Georgian traditional cuisine is NOT covered comprehensively: the 2009 Georgian composition tables have unresolved redistribution rights. Do not fabricate nutrient values or copy unlicensed entries.
- Source CSV exports for Spain (ES), Italy (IT), France (FR), Greece (GR) are also set up using official OFF country-specific downloadable search CSV, rather than querying rate-limited API pages. Jobs: https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43811724359
- Translation workflow: https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43812190358 . Applies Helsinki Marian multilingual model labels only, compares SHA256 hashes of all protected source ID, nutrient, original name, and serving fields. Ordinary Releases are published only if Hebrew coverage and data QA gates pass. Machine translation is NOT human linguistic review.
- Prior Georgia 64-food archive `georgia-he-candidate-2` is clearly labeled INVALID partial and must never be promoted.
- Required permanent serving unit standard: `PACK_SERVING_STANDARD_HE.md`, valid source serving and editable natural units, never fabricated nutrition or silent g/ml substitution.
- An hourly condition-watch notification is enabled; notify with exact approved Release URL only when a NEW normal verified country pack has actually been published, not for candidates. GitHub completion ≠ installed on iPhone.
- No country is considered approved solely because a CSV file downloaded; check production Release metadata and QA evidence.

---

# Down the Hill · Food Pack Status and Recovery (15 Nov 2026)

This file is the persistent source-of-truth index for country and international food packs.
It remains accessible independently from ChatGPT conversations.
Read the latest GitHub Actions and Releases for live status; do not infer iPhone installation from a successful workflow.

## Built and archived

| Pack | Verified food records | Hebrew labels | Durable downloadable GitHub Release | QA |
|---|---:|---:|---|---|
| Austria BLS 4.0 (German source) | 7,090 | Limited curated aliases in original | [Original pack + full backup ZIP](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/austria-original-backup-2026-11-15) | Verified and permanently archived |
| Austria Open Food Facts | 3,000 | Limited curated aliases in original | [Same original backup Release](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/austria-original-backup-2026-11-15) | Verified and permanently archived |
| USDA International Core | 13,535 | 13,418 machine-translated | [international-core-candidate-2026-11-15](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/international-core-candidate-2026-11-15) | Structural QA passed; Hebrew linguistic QA pending |
| Austria Hebrew candidate | Target: preserve all 10,090 | Target: >=95% per source | [Check Austrian Hebrew Action](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43750853015) | In progress when this file was written; see live action |


### Durable Recovery Releases — verified on 15 Nov 2026
- [Austria original 10,090 foods — source files + offline backup ZIP + checksums](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/austria-original-backup-2026-11-15); [successful publishing Action](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43751987510).
- [USDA International Core — 13,535 foods + offline backup ZIP + translation report](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/international-core-candidate-2026-11-15); pending human translation review.
- [Food pack builder code + QA tests + workflows + recovery documentation ZIP](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/food-pack-builder-backup-2026-11-15); [successful archive Action](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43752109079).
- [Austria extended Hebrew candidate Action](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43750853015): **not yet a verified Release** as of this update. If successful its workflow publishes a new prerelease with original and translated backup ZIPs. Do not uninstall installed Austria food packs before a tested upgrade.
- The **iOS Build 31 Xcode source ZIP is not included in these GitHub Releases**. It was provided in the conversation and must remain backed up separately on the user's computer unless deliberately uploaded to a code repository/Release.

### Reproducibility
- Original Austria source binaries SHA256 (Release 1.3):
  - BLS: `a994590c54fc1424592e685380f011d4c7c3796e13e88f355011b4463538efcd`
  - Open Food Facts: `176e804c6416dc2471c4e0216adccde28bd96a150b81bec96336c4a2d6756726`
- Original USDA Core candidate binary SHA256:
  - `f740753c26dd6f977bce7aaad16f0d3ce5f09a337a83752de4b4e2ce39abeed9`
- Each Release includes its checksums and attribution/licensing. Never overwrite old Release tags.
- GitHub Actions run artifacts expire. Preserve usable, reviewed data through Releases, not artifacts alone.
- Releases are durable relative to Actions artifacts, but GitHub does not promise indefinite hosting. Keep local and independent secondary backups.

## Pipelines
- [Original Austria build workflow](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/blob/main/.github/workflows/build-austria.yml).
- [Austria Hebrew preserve + translate workflow](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/blob/main/.github/workflows/archive-translate-austria.yml). Archives original source first and only changes names/search. Protects numerical fields and identifiers with per-record hash verification. New candidate is a **prerelease**, not a silent replacement.
- [USDA artifact preserve workflow](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/blob/main/.github/workflows/archive-international-core.yml).
- [Austrian Hebrew Action (run 43750853015)](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43750853015).


### Austria Hebrew retry, 15 Nov 2026
- Initial attempt [43750853015](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43750853015) failed because **Open Food Facts achieved 88.37% Hebrew name coverage**, versus the 95% gate. The BLS translation phase completed.
- Root cause confirmed from authentic source package: 3,000 Open Food Facts items have an empty `name_en` field, but many `name_de` product names are English or brand names. First run tried German→Hebrew for all.
- Fixed [builder/translate_austria_he.py](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/blob/main/builder/translate_austria_he.py) to retry terms missing Hebrew with English→Hebrew while keeping original German/English fields, nutrition, provenance and serving sizes intact. Added sample reporting for uncovered names and automatic workflow trigger on code changes.
- New retry: [GitHub Action 43753904629](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43753904629). **In progress when written; do not claim success yet**. Its candidate Release must contain two separate packs, checksums, QA report and the original/translated ZIPs. Do not uninstall the current packs.

## iPhone / Build 31
- Do not delete the installed app.
- The app's existing Israeli and small common-food catalogs remain built-in.
- International Core must be **optional to download, update and remove**, despite older Build 31 code protecting it as built-in. This is an approved design change not implemented in the iOS app in this workflow.
- Austria remains an independent removable package; uninstalling a package must never delete personal foods, previous meal logs or their nutritional snapshots.
- Build 31 source and iPhone installation were not modified by these GitHub food-pack operations.
- Do not call a machine-translated package “human-reviewed” before manual QA: sample at least 100 random and 20 challenging entries per publishing batch.
- Food sources retain license segregation: BLS CC BY 4.0, Open Food Facts ODbL 1.0, USDA CC0; translation model Apache-2.0.

## Offline recovery
1. Download the data files and matching `SHA256SUMS` from the Release; retain `ATTRIBUTION.md` and QA report.
2. Verify SHA-256 after downloading. On macOS Terminal in extracted release directory use: `shasum -a 256 -c SHA256SUMS`.
3. Store an original unmodified ZIP on your Mac **plus a second copy** on external storage or another cloud account.
4. Downloaded food packs are independent of private meal-history backups. App data must be backed up separately through its own export / iPhone backup workflow.
5. Keep the source and version identifier with every pack so a future developer can reliably restore it.

## Current conversation continuation
The user asked for more Hebrew names in Austria, independent optional International Core, permanent GitHub Releases, and a full computer-downloadable backup. GitHub production/QA status must be checked at the links above, rather than reconstructed from an expired chat history.
