---
title: Release it
summary: How a version gets from the main branch to installations: branches, tags, GitHub Releases, the notes.
group: The code
roles: platform-developer
---

## How releases travel

Installations offer only **published GitHub Releases** of the EA Explorer repository: a tag with no published release,
a draft, or the main branch is never offered. The **Prod** channel offers releases; **RC** also offers pre-releases,
once an admin turns it on. Installations move forward one release at a time, taking a pinned backup first.

## The steps

1. The version in `services/api/version.toml`, the migration that records it, and `releases/<version>.md`.
2. All tests pass; the self-test passes on a clean installation.
3. Merge to the `release` branch (or `rc`), tag `vX.Y.Z`, and publish the GitHub Release with the notes.
4. Each installation's System Admin › Updates offers it; this website is rebuilt for the release
   (`.\eax site build` makes `site/<version>/`).

The repository's `docs/release-process.md` has the full commands.

## Read next

- [[update-to-a-new-release]]
