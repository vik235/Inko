# TODO — pick this up before next significant work

> **READ ME FIRST** when you next sit down with this repo.

## 1. Apply branch protection rules on `main` (manual, GitHub UI)

The CI workflow, PR template, and CONTRIBUTING guide are committed but
**branch protection itself is not enforced yet** — you can still
`git push origin main` directly. Lock it down with a 5-click sequence:

1. Go to https://github.com/vik235/Inko/settings/branches
2. Click **Add branch ruleset** (or "Add classic branch protection rule").
3. **Branch name pattern**: `main`
4. Tick:
   - ☑ **Require a pull request before merging**
     - Required approvals: **0** (solo dev — leave at 0 so you can self-merge)
     - ☑ Dismiss stale pull request approvals when new commits are pushed
   - ☑ **Require status checks to pass before merging**
     - Search and add: **`Tests (Python 3.12 on ubuntu-latest)`**
       *(this name comes from the matrix in `.github/workflows/ci.yml` —
       you may need to push at least one commit triggering CI before the
       check appears in the picker)*
     - ☑ Require branches to be up to date before merging
   - ☑ **Require linear history**
   - ☑ **Restrict deletions** (block deleting `main`)
   - ☑ **Block force pushes**
5. Save.

Then in **Settings → General → Pull Requests**:
- ☑ Allow squash merging — and set "Default merge commit message" to
  *Pull request title and description*.
- ☐ Allow merge commits (off — keeps history linear)
- ☐ Allow rebase merging (off — keep it simple)
- ☑ Automatically delete head branches

After this is applied, direct `git push origin main` will be rejected and
you'll always go through a PR.

## 2. (Optional) Install GitHub CLI for future automation

```bat
winget install --id GitHub.cli
gh auth login
```

With `gh` installed, future setup like adding labels, applying rule sets,
or creating issues from this repo can be automated from the terminal
instead of clicking through the web UI.

## 3. (Optional) Move `.git` up so the working dir == repo

Currently the source lives in `E:\Projects\Quickr\` and the git mirror in
`E:\Projects\Quickr\Quickr\`. Each push needs a sync step. To collapse:

```bat
:: 1. Close the running app and any tools holding files open.
:: 2. Move the .git folder up.
move E:\Projects\Quickr\Quickr\.git E:\Projects\Quickr\.git

:: 3. Delete the now-redundant nested copy.
rmdir /s /q E:\Projects\Quickr\Quickr

:: 4. Clean up any tracked dupes; verify.
cd E:\Projects\Quickr
git status
```

Single source of truth, no syncing. Mostly cosmetic but nice.
