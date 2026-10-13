# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

We use the following:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.

## [unreleased]

### Added

- after running the tasks, a summary with the number of succeeded / failed / not run tasks and the arguments of the
  failed tasks is logged (`basic` and `queue` mode)

### Changed

- matching of several pattern arguments: one task is generated per file matched by the first pattern on the command
  line, which has to match existing files (a warning names it otherwise); other patterns that match existing files are
  paired with it by corresponding names (e.g. `a.tif` / `a_out.tif`, files without an existing counterpart get the
  derived value), pairing by folder is only used if no names correspond; files of the first pattern that a more
  specific pattern matches as well (like the `*_out.tif` results of a previous run for `*.tif`) are not used for the
  first pattern
- `--mode` only accepts the implemented modes (`basic`, `queue`); the `queue` mode is listed in the help, and an
  unknown mode is an error instead of silently doing nothing

### Removed

- `argument_matching.expand_args` (internal helper, replaced by `path_pattern.PathPattern`)

### Fixed

- `run-distributed` passed the solution arguments to `RunManager.run` in the wrong position (as `run_immediately`),
  so every task ran the solution without any arguments
- patterns given as `--arg=value` were never replaced by the matched values; both `--arg value` and `--arg=value` are
  supported now, and an argument value that cannot be replaced (e.g. an abbreviated argument name) raises an error
  instead of silently running the solution with the unexpanded pattern
- `queue` mode exited with status 0 even if tasks failed; the command fails now if any task failed. `basic` mode still
  stops at the first failing task and passes its error on
- `--threads 0` (or a negative number) made `queue` mode wait forever without running any task; values below 1 are
  rejected now
- on Windows, matched files without a `.tif` extension were not recognized as paths (glob joins them with `\`), so
  several pattern arguments were combined with each other instead of being paired by folder; a folder spelled with
  `/` in one pattern and matched by a wildcard in another (`data/sub/*.json` and `data/*/a.png`) did not count as
  the same folder, so no tasks were generated
- README: patterns are quoted in all examples (unquoted patterns are expanded by the shell before album sees them),
  the wrong advice to replace slashes with backslashes on Windows is replaced, and the `queue` mode and the exit
  status are documented
- patterns that do not match existing files yet, like the documented `--output_data '*_out.tif'`,
  `--output_data 'output/*.tif'` and `--output_data '**/*_out.tif'`, generated no tasks at all; their values are
  derived from the matched files again (the wildcards are replaced by what the corresponding wildcards matched, `**`
  keeps the sub folders); if several tasks would get the same derived value and overwrite each other's results, no
  task is generated
- a value with `*`, `?` or `[` that is not meant as a pattern, like `--prompt 'Is this a cell?'`, generated no tasks
  next to a file pattern; a value that matches no file is now passed unchanged unless the argument is of type `file`
  or `directory` or the value looks like a path (contains a `/` or ends with a file extension)
- an argument without pattern in another folder than the matched files (e.g. `--output results/`) generated no tasks;
  arguments without pattern are now passed unchanged to every task
- a warning explains why no task was generated

## [0.2.1]

### Changed

- pyproject.toml over setup.cfg

## [0.2.0]

### Added

- changelog to the repository

[unreleased]: https://gitlab.com/album-app/album-distributed/-/compare/v0.2.1...HEAD
[0.2.1]: https://gitlab.com/album-app/album-distributed/-/compare/v0.2.0...v0.2.1
[0.2.0]: https://gitlab.com/album-app/album-distributed/-/tags/v0.2.0
