# Archive Directory

This directory contains preserved historical, unreferenced, draft, and duplicate files removed from active runtime paths to eliminate technical debt, dead bloat, and maintain zero duplication.

## Preserved Structure:
- rchive/scripts/ci/: 178 unreferenced CI check scripts that were not wired into any GitHub Actions workflows or master runner.
- rchive/scripts/ops/: 72 bit-for-bit duplicate files previously shadowed between scripts/ and scripts/ops/.
- rchive/scripts/divergent_copies/: 112 older/divergent versions of scripts previously duplicating scripts/ops/ (consolidated to scripts/ops/ as SSOT).
- rchive/gateway/skills/: Completely duplicate skills directory previously mirroring the root skills/ directory.
- rchive/core/skills/: 13 duplicate skill subdirectories previously mirroring root skills/.
- rchive/gateway/duplicates_of_core/: 50 bit-for-bit identical files between gateway/ and core/ (consolidated to core/ as SSOT).
- rchive/github_scripts/: 56 dead and unreferenced scripts removed from .github/scripts/.
- rchive/plans/: 6 draft and unmaintained legacy roadmap/plan documents removed from root code directories.

All active, verified runtime and CI code remains in its canonical locations: scripts/ci/, scripts/ops/, skills/, core/, and gateway/.
