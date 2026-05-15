---
inclusion: manual
---

# Git Commit Workflow

When asked to commit, push, or work with git, follow this process:

## Step 1: Inspect Changes

1. Run `git status` to see modified, staged, and untracked files.
2. Run `git diff` for unstaged changes.
3. Run `git diff --cached` for staged changes.
4. If needed, read specific files to understand the intent of the changes.

## Step 2: Analyze and Group

- Group changes into logical commits. Do not combine unrelated changes.
- If a file contains mixed concerns, mention it and recommend splitting.
- If something is unclear, say what is uncertain instead of guessing.

## Step 3: Write Commit Messages

Use Conventional Commits format:

- `feat:` — new feature
- `fix:` — bug fix
- `refactor:` — code restructuring without behavior change
- `docs:` — documentation only
- `test:` — adding or updating tests
- `chore:` — maintenance, dependencies, config
- `style:` — formatting, whitespace
- `perf:` — performance improvement
- `build:` — build system or external dependencies
- `ci:` — CI/CD configuration

Rules:
- Each commit message must be specific and based on actual code changes, not just filenames.
- Avoid vague messages like "update code", "fix bug", "changes".
- Use a short title line (imperative mood, max ~72 chars).
- Add a body explaining what changed and why when the change is non-trivial.

## Step 4: Execute

- Stage files and commit directly using git commands. Do not ask the user to copy-paste.
- Use `git add -p` only when absolutely necessary (interactive). Prefer staging whole files or resetting and re-staging.
- After committing, run `git status` and `git log --oneline -n` to verify.
- If the user says "push", run `git push` immediately.

## Output Format (before executing)

Show a brief summary:
- Repository status
- Change analysis (what changed and why, grouped logically)
- Proposed commit split with messages
- Then execute the commits.
