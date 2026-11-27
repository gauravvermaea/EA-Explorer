# Releasing EA Explorer (8.5, D513 to D515)

How a version gets from `main` to the installations, what the owner runs, and which versions are supported. The owner
runs git; nothing here pushes on its own.

## The branches and the channels (D417)

| Channel | Branch | Offered | Installations see it |
|---|---|---|---|
| **Prod** | `release` | the **published GitHub Releases** (tags `vX.Y.Z`) | always |
| **RC** | `rc` | the published **pre-releases** too (tags `vX.Y.Z-rc.N`, or `vX.Y.Z` marked pre-release) | once a Super Admin or IT Admin enables RC |

R5.6 (owner, 16 Nov 2026: "Release should not be picked from the main branch, instead pick them from here -
https://github.com/gauravvermaea/EA-Explorer/releases only upgrade forward"): installations, `eax deploy` and the
installers read the repository's **GitHub Releases** (public, no sign-in) and offer only what is **published** there:
a tag with no published release, a draft, or the `main` branch is never offered. **So a release reaches installations
only once its GitHub release is published.** When GitHub cannot be reached or its limit on calls without a sign-in is
reached, they say so and offer nothing.

## Setting it up, once (the owner)

1. Make the repository public (installations read it without credentials).
2. Create the two branches from `main` and push them:

   ```
   git checkout main
   git pull
   git branch release
   git branch rc
   git push origin release rc
   ```

3. Give the repository link to each installation: System admin › Updates › Change… (or
   `eax update --url https://github.com/<owner>/<repository>.git`, or `EAX_UPDATE_GIT_URL` in work/eaexplorer.env).

## Releasing a version

1. On `main`, with every test green, set the version in `services/api/version.toml` (e.g. `0.19.0`).
2. Write the notes: `python tools/release.py notes 0.19.0` makes `releases/0.19.0.md` from the commits since the last
   release. Edit it: two or three lines on what people will notice, then anything to check before updating.
   Then the GitHub home page (D956): `README.md`'s status line says the new version and links its notes, its releases
   table's row for the release links `releases/0.19.0.md` and no longer says planned, and the title of
   `docs/capabilities.md` says the version. `python tools/release.py check v0.19.0` and the dev check's
   test_d956_front_page_names_the_release.py fail until they do.
3. Print the git commands: `python tools/release.py commands 0.19.0`. For the first release they are:

   ```
   git checkout main
   git pull
   git add releases/0.19.0.md services/api/version.toml README.md docs/capabilities.md
   git commit -m "Release 0.19.0"
   git push origin main

   git checkout release
   git merge --ff-only main
   git tag -a v0.19.0 -m "EA Explorer 0.19.0"
   git push origin release v0.19.0
   git checkout main
   ```

4. CI runs on the tag: the API tests and lint, the web build, the compose files and images (built to test them, not
   published), then `tools/release.py check` (the tag, version.toml and the notes agree) and the GitHub release with the
   notes. Installations on Prod now offer 0.19.0.

**A release candidate** is the same with `-rc.N` and the `rc` branch: `python tools/release.py notes 0.20.0-rc.1`
(optional: without its own file an RC shows `releases/0.20.0.md` once that exists), then
`python tools/release.py commands 0.20.0-rc.1` (`git checkout rc`, `git merge --ff-only main`,
`git tag -a v0.20.0-rc.1 …`, `git push origin rc v0.20.0-rc.1`). Installations with RC enabled see it.

Publish it on GitHub as a **pre-release** (the "Set as a pre-release" box) so only installations with RC enabled see it.
The Latest channel (every commit of `main`) is gone (R5.6): nothing is offered from `main`.

## Release notes (D510)

The GitHub release's own text; when it is empty, `releases/<version>.md` in the repository, read at the tag (an RC
without its own file shows its release's file). Installations show the notes when choosing a
version, and to everyone once afterwards as **What's new**.

## Images (D514)

Not published. D373 asked for published images; D417 (later) builds every version **on the installation's own host**
from the repository, with no registry, so an update needs nothing but the public repository. CI still builds every image
on every change, to prove they build. If a registry is wanted later (air-gapped sites, faster updates), CI can push the
images it already builds; nothing in the updater depends on it.

## Supported versions (D515)

- The **newest release line** (X.Y) and **the one before** are supported: e.g. with 0.21.x out, 0.21.x and 0.20.x.
- A **release candidate** is supported until its release is out; (Latest builds are no longer offered, R5.6.)
- Within a line, only its newest patch gets fixes: update to it.

Installations check once a day (with a repository link set) and tell their Super Admins and IT Admins, once per version,
when the installed version is out of support, with the version to update to.

## Alerts to operations (D515)

The Super Admins and IT Admins are told (the bell, and the webhooks) when an update fails (needs action: Retry or Roll
back), finishes, is rolled back or does not start, and when the installed version is out of support. CI failures are
GitHub's own notifications to the owner.
