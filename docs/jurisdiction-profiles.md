# Jurisdiction profiles

AR is the only launch-active jurisdiction profile in this repository.

## Current rule

- Guest/check-in validation defaults to `AR`.
- `UY` and `CL` exist only as experimental skeleton profiles.
- Country extension should happen by adding a new profile definition in `app/services/jurisdiction_profile.py`.

## Why

- The guest data model stays shared and stable across launch countries.
- Validation differences live in a small profile layer instead of branching the schema.
- Adding a new country should be a profile change plus tests, not a data model rewrite.
