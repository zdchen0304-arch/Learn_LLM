---
name: release-workflow
description: End-to-end git release workflow for this repository. Use when the user asks to publish a release, says release or ship, or otherwise wants Codex to complete release work by checking and updating docs, reviewing all changes since the previous tag, committing and pushing changes, choosing a version tag based on release scope, and drafting concise Chinese GitHub-ready release notes in a fenced Markdown block.
---

# Release Workflow

Apply this skill when the user wants Codex to turn the current repository state into a release.

## Workflow

1. Inspect the release state.
- Read `git status --short`, current branch, remotes, latest tags, and the full diff from the previous release tag to `HEAD`.
- Treat the release scope as `last-tag..HEAD`, not just the current uncommitted worktree diff.
- If there are unreleased local changes on top of the last tagged commit, include them in the release only after confirming they belong in this release.
- Summarize the change set in terms of user-facing behavior, APIs or contracts, schema or config impact, docs impact, and operational risk.
- If the worktree contains obviously unrelated, experimental, or incomplete changes, pause and confirm before committing, tagging, or pushing.
- If there are no meaningful release changes, say so and stop before creating a commit or tag.

2. Align documentation.
- Update documentation that is no longer true before releasing.
- Prioritize `README.md`, `docs/README.md`, setup docs, workflow docs, and release-related docs.
- If `docs/RELEASE_NOTE_STANDARD.md` exists, read it and use it as input, but improve the final structure when the standard is weak, duplicated, or outdated.
- Tie every doc edit to observed code or config changes; do not add speculative promises.

3. Verify the change set.
- Do not rerun the main test suite by default during release prep; assume development-time verification has already happened unless the user explicitly asks to rerun tests or the release process itself introduces risky new edits.
- Prefer release-integrity checks such as `git diff --check`, broken-reference scans, or other cheap consistency checks tied to the release edits.
- If you do run extra verification, report exactly what was run; if you intentionally skip test reruns, state that plainly in the final response and release notes.

4. Determine the version bump.
- Infer the repository's tag scheme from existing tags and continue that pattern when possible.
- If no tags exist, default to `v0.1.0`.
- Classify the release:
  - `patch`: fixes, refactors, docs-only updates, or internal changes with no contract change
  - `minor`: backward-compatible features, new workflows, new endpoints or options, materially expanded capability
  - `major`: breaking API, schema, CLI, config, or output changes; deleted or renamed public contracts; required migration
- For `0.y.z` series, treat breaking changes as a `minor` bump unless the repo already uses `1.x` or the user explicitly wants a `1.0.0` transition.
- Record the rationale for the chosen bump in the final summary.

5. Commit and push the release commit.
- Stage only the intended release changes.
- Use non-interactive git commands only.
- Prefer a commit message like `chore(release): prepare <next-tag>`.
- Push the release commit to the current upstream branch before tagging.
- If push fails because of auth, branch protection, or non-fast-forward state, stop and report the exact blocker.

6. Create and push the tag.
- Create an annotated tag for the chosen version after the branch push succeeds.
- Use a short annotation that reflects the release scope.
- Push the tag to the same remote after branch push succeeds.
- If the computed tag already exists, inspect the next valid bump rather than force-reusing it.

7. Draft release notes.
- Base the notes on the actual `last-tag..new-tag` diff, commit set, and any release-time verification results.
- Output release notes inside a fenced `md` code block so the user can paste them into GitHub.
- Write the release notes in Simplified Chinese.
- Prefer a concise, audience-friendly structure similar to a short GitHub Release body.
- Do not include a top-level version heading inside the release note body; GitHub already shows the release title separately.
- Keep the summary to 1-2 sentences and keep the total body tight unless the change set truly requires more detail.
- Prefer this structure:

```md
**<Chinese label for Release Date>**: YYYY-MM-DD

## <Chinese heading for Summary>

- 1-2 short sentences, or 1-2 concise bullets

## <Chinese heading for Added> (Added)
- ...

## <Chinese heading for Fixed> (Fixed)
- ...

## <Chinese heading for Changed> (Changed)
- ...
```

- Add optional sections such as deprecated or removed, security, migration notes, or docs only when the release genuinely needs them.
- Drop empty sections instead of filling them with placeholders.
- Keep wording factual, concrete, and traceable to the changes.

## Output Expectations

After completing the workflow:

- Report the branch, commit hash, pushed remote, and created tag.
- Explain the version bump rationale in 1-3 bullets.
- Explicitly state the release review range, such as `v5.6.0..v5.7.0`.
- Provide the final concise Chinese release notes in a fenced `md` block.
