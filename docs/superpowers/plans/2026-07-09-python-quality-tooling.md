# Python Quality Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add blocking Ruff, mypy, and pytest checks locally and in GitHub Actions while leaving trading behavior unchanged.

**Architecture:** Centralize static-analysis configuration in `pyproject.toml`, keep development tools in `requirements-dev.txt`, and use one GitHub Actions job that runs the same commands documented for local use. Exclude the official KIS distribution from static analysis and introduce mypy only for application-owned strategy, broker, and state modules.

**Tech Stack:** Python 3.11, Ruff, mypy, pytest, GitHub Actions

---

### Task 1: Add the local quality toolchain

**Files:**
- Create: `pyproject.toml`
- Create: `requirements-dev.txt`
- Modify: `requirements.txt`

- [ ] **Step 1: Record the missing-tool baseline**

Run:

```bash
test -x venv/bin/ruff
test -x venv/bin/mypy
```

Expected: both commands exit non-zero because the tools are not installed.

- [ ] **Step 2: Add the Ruff and mypy configuration**

Create `pyproject.toml` with:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
extend-exclude = ["src/kis/kis_api"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "B"]

[tool.mypy]
python_version = "3.11"
check_untyped_defs = true
ignore_missing_imports = true
show_error_codes = true
pretty = true
exclude = ["^src/kis/kis_api/"]
```

- [ ] **Step 3: Add reproducible development dependencies**

Change the existing `pytest` line in `requirements.txt` to:

```text
pytest>=8,<9
```

Create `requirements-dev.txt` with:

```text
-r requirements.txt
ruff>=0.12,<1
mypy>=1.16,<2
```

- [ ] **Step 4: Install the development toolchain**

Run:

```bash
venv/bin/pip install -r requirements-dev.txt
```

Expected: installation exits zero and `venv/bin/ruff --version`,
`venv/bin/mypy --version`, and `venv/bin/pytest --version` succeed.

- [ ] **Step 5: Run Ruff and fix only in-scope violations**

Run:

```bash
venv/bin/ruff check src tests scripts
```

Expected initially: Ruff reports existing violations outside
`src/kis/kis_api/**`. Apply safe import-order and unused-import fixes with:

```bash
venv/bin/ruff check src tests scripts --fix
```

Review every resulting diff, manually fix remaining violations without changing
behavior, then rerun the check. Expected final result: exit zero.

- [ ] **Step 6: Run mypy and resolve the initial typed boundary**

Run:

```bash
venv/bin/mypy src/strategy src/broker src/state
```

Expected initially: mypy may report existing type inconsistencies. Fix
annotations or add the narrowest justified local suppression, without changing
runtime behavior. Expected final result: exit zero.

- [ ] **Step 7: Verify the existing tests**

Run:

```bash
venv/bin/pytest tests
```

Expected: all collected tests pass.

### Task 2: Add blocking GitHub Actions checks

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the CI workflow**

Create `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  quality:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: python -m pip install -r requirements-dev.txt

      - name: Run Ruff
        run: ruff check src tests scripts

      - name: Run mypy
        run: mypy src/strategy src/broker src/state

      - name: Run pytest
        run: pytest tests
```

- [ ] **Step 2: Validate workflow structure**

Run:

```bash
venv/bin/python -c "import yaml; data=yaml.safe_load(open('.github/workflows/ci.yml')); assert data['jobs']['quality']['steps']"
```

Expected: exit zero.

### Task 3: Document the quality workflow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a development quality section**

Add a `코드 품질 검사` section after `중요한 운영 원칙` documenting:

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/ruff check src tests scripts
venv/bin/mypy src/strategy src/broker src/state
venv/bin/pytest tests
```

Explain that Ruff checks lint problems, mypy performs static type checking,
pytest executes behavior tests, GitHub Actions runs all commands on pushes and
pull requests, and `venv/bin/ruff check src tests scripts --fix` is an optional
developer command that must be diff-reviewed.

- [ ] **Step 2: Check documentation formatting**

Run:

```bash
git diff --check
```

Expected: exit zero with no whitespace errors.

### Task 4: Run the final verification suite

**Files:**
- Verify all files changed by Tasks 1-3

- [ ] **Step 1: Run all local quality gates**

Run:

```bash
venv/bin/ruff check src tests scripts
venv/bin/mypy src/strategy src/broker src/state
venv/bin/pytest tests
```

Expected: all three commands exit zero.

- [ ] **Step 2: Run the repository-required Docker test suite**

Run:

```bash
docker compose exec -T trading-bot python -m pytest tests
```

Expected: all collected tests pass without live order-changing actions.

- [ ] **Step 3: Audit the final diff**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; only quality-tool configuration, workflow,
documentation, and narrowly necessary Ruff/mypy cleanup files are changed.
