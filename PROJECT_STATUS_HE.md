# Down the Hill · Food Pack Status and Recovery (15 Nov 2026)

This file is the persistent source-of-truth index for country and international food packs.
It remains accessible independently from ChatGPT conversations.
Read the latest GitHub Actions and Releases for live status; do not infer iPhone installation from a successful workflow.

## Built and archived

| Pack | Verified food records | Hebrew labels | Durable downloadable GitHub Release | QA |
|---|---:|---:|---|---|
| Austria BLS 4.0 (German source) | 7,090 | Limited curated aliases in original | [austria-1.3-attempt.1](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/austria-1.3-attempt.1) | Released |
| Austria Open Food Facts | 3,000 | Limited curated aliases in original | Same Release, separate ODbL file | Released |
| USDA International Core | 13,535 | 13,418 machine-translated | [international-core-candidate-2026-11-15](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/releases/tag/international-core-candidate-2026-11-15) | Structural QA passed; Hebrew linguistic QA pending |
| Austria Hebrew candidate | Target: preserve all 10,090 | Target: >=95% per source | [Check Austrian Hebrew Action](https://github.com/ktktuybhe-ui/down-the-hill-food-packs/actions/runs/43750853015) | In progress when this file was written; see live action |

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
