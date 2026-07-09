# Python Quality Tooling Design

## Goal

Introduce Ruff, mypy, pytest, and a blocking GitHub Actions workflow without
changing trading behavior. Local and CI checks must use the same configuration
and commands.

## Scope

- Add Ruff and mypy configuration in `pyproject.toml`.
- Add development-only quality dependencies in `requirements-dev.txt`.
- Run Ruff against application-owned Python and tests.
- Run mypy incrementally against application-owned modules.
- Run the complete pytest suite.
- Run all three checks for pushes and pull requests in GitHub Actions.
- Document the local commands.

The official KIS distribution under `src/kis/kis_api/**`, private runtime
configuration, generated data, and external mounts are excluded from Ruff and
mypy. Existing pytest tests may continue to import KIS modules as needed.

## Ruff Policy

Ruff checks `src/`, `tests/`, and Python scripts while excluding the official
KIS distribution. The initial rule set covers Python errors, unused and
undefined names, import ordering, and common bug patterns. CI runs checks
without automatic fixes; developers may use Ruff's fix command locally.

Formatting is checked only if adopting Ruff formatting does not require an
unrelated repository-wide rewrite. The lint configuration remains the required
CI gate.

## mypy Policy

mypy targets application-owned modules with existing typing value, beginning
with `src/strategy`, `src/broker`, and `src/state`. It checks bodies of
untyped functions but does not initially require every function to be
annotated. Missing third-party stubs are tolerated so adoption is not blocked
by external packages.

The target list may expand after additional application modules are annotated.
The official KIS distribution remains outside the type-checking boundary.

## Dependencies

Runtime dependencies remain in `requirements.txt`. `requirements-dev.txt`
includes the runtime requirements and pins compatible ranges for Ruff, mypy,
and pytest so local development and CI install the same toolchain.

## Continuous Integration

`.github/workflows/ci.yml` runs on pushes and pull requests using Python 3.11,
matching the Docker image. It installs `requirements-dev.txt` and runs:

1. Ruff lint checks.
2. mypy static type checks.
3. the complete pytest suite.

Any failed command fails the workflow. CI must not access live KIS, Toss,
Telegram, credentials, private configuration, or place orders.

## Documentation

Repository documentation records installation, local commands, optional Ruff
auto-fixing, and the distinction between static checks and runtime tests.

## Verification

- Ruff completes with no violations in its configured scope.
- mypy completes with no errors in its configured scope.
- Host-side pytest completes successfully where safe.
- The workflow syntax and commands match the verified local commands.
- The diff contains no private data or changes to trading behavior.
