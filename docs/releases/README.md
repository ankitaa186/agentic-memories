# Releases

[Documentation](../README.md) / Releases

The repository has not established a tagged release history yet. The version in
`pyproject.toml` is `0.1.0`; a package version alone is not a published release.
[GitHub Releases](https://github.com/ankitaa186/agentic-memories/releases) is the source
of truth for published versions.

## Next release candidate

[v0.2.0 — Persistent context through MCP](v0.2.0-draft.md) is a **draft**, intended to
establish a versioned baseline for the existing MCP implementation and recent improvements.
Its version and release date must be confirmed during release preparation. No tag or
release is created by adding this document.

## Preparing a release

1. Choose the commit and run CI, documentation checks, and relevant MCP/live-backend checks.
2. Review `CHANGELOG.md`, migrations, dependency compatibility, and known limitations.
3. Set the version consistently in `pyproject.toml` and application metadata; regenerate
   affected lock/export files. Do this in the release commit, not retrospectively.
4. Convert the selected Unreleased entries into a dated version section, retaining any
   later changes under Unreleased. Finalize release notes from the draft.
5. Create an annotated `vX.Y.Z` tag for the reviewed commit and publish its GitHub release.
6. Record the matching container digest when a versioned image is published. Do not
   label an unrelated `latest` image as that release.
7. Deploy separately and record the deployed revision plus post-deployment checks.

Older work remains an unversioned baseline; do not invent historical tags or release dates.

## Notes and automation

[GitHub release-note configuration](../../.github/release.yml) groups labeled PRs into
features, fixes, documentation, and maintenance. Use generated notes as an inventory,
then edit them for user outcomes, migrations, compatibility, and verified limitations.
Direct commits and unlabeled work still require review; generated notes are not the whole changelog.

The existing CI publishes branch/SHA container tags from main. Tag-triggered release
image publishing is not configured by this documentation change. Before enabling it,
ensure release builds run the same quality gates and identify the exact source commit.
