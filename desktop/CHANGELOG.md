# Changelog

Every released version of the Monitra desktop client, newest first, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style.

This file is **hand-written, not generated.** GitHub's auto-generated release
notes list commit titles, which answer "what did we change" and not "what
changed for you" — the question a member of staff actually has when they are
asked to install something. Both go out with a release; only this one is
written for the person installing it.

`tools/check_changelog.py` fails CI if the version in `version.py` has no
entry here, so a release cannot ship without one.

The version numbers follow semver as `version.py` describes: **patch** for
fixes with no behaviour change worth knowing about, **minor** for new features
and additive backend contract changes, **major** for a breaking desktop↔backend
contract change, a data-directory migration, or anything that makes every user
re-grant a permission.

## [Unreleased]

### Added

- **Update notice.** The app now checks periodically whether a newer release
  has been published and tells you once, through the usual notification. It
  never downloads or installs anything — you still choose when to update, and
  from where. If the check cannot reach the backend, or the backend has not
  been told what the current release is, nothing is shown.
- **Version visibility for support.** The desktop identifies its own version
  on every request, so support can see which build you are running when you
  report a problem, and can tell whether a fix has actually reached everyone.
  Nothing else about your machine is collected.

## [1.0.1]

This file was introduced after 1.0.1 was already tagged, so this entry is a
placeholder rather than a reconstruction. What shipped in 1.0.1 was not
recorded at the time and is not being guessed at here; `git log v1.0.0..v1.0.1`
is the only accurate account of it. Every version from the next release
onwards has a written entry.

## [1.0.0]

First packaged release: Windows installer and portable build, macOS DMGs for
Apple Silicon and Intel.
