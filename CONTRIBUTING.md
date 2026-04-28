# Contributing to Inko

## Branch naming

| Prefix | Use for |
|--------|---------|
| `feature/<short-name>` | New user-facing functionality (e.g. `feature/csv-export`) |
| `fix/<short-name>` | Bug fixes (e.g. `fix/signature-cache-stale`) |
| `chore/<short-name>` | Refactors, dependency bumps, tooling, docs (e.g. `chore/bump-flask`) |
| `release/<vX.Y.Z>` | Cutting a release (only used when tagging a build) |

Keep branches short-lived — open a PR within a day or two of starting.

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: <imperative summary>
fix: <imperative summary>
chore: <imperative summary>
docs: <imperative summary>
```

Body is optional; if present, explain *why* not *what* (the diff says what).
Trailers go at the bottom (e.g. `Co-Authored-By:`).

## Pull requests

1. Push your branch to `origin`.
2. Open a PR against `main` — the template auto-populates.
3. Wait for CI to be green (smoke + signature + feature tests).
4. **Squash and merge** (linear history is required). Delete the branch on
   merge.

Direct pushes to `main` are blocked by branch protection (see TODO.md if
those rules aren't yet applied on this repo).

## Running tests locally

```bat
.venv\Scripts\activate.bat
python smoke_test.py
python test_signature_flow.py
python test_features.py
```

All three should print `All checks passed.` and exit 0.

## Local development

See `README.md` for app architecture, file locations, build steps, and the
SMTP / signature / branding plumbing.
