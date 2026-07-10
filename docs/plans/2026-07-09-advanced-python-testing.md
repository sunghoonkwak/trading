# Advanced Python Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add coverage, property tests, dependency auditing, offline API replay, mutation diagnostics, and a credential-free Docker smoke check.

**Architecture:** Keep generated and replay tests inside the existing module-oriented pytest suites and exercise application-owned pure functions directly. Add fast checks to the normal CI job, isolate Docker verification in its own job, and keep mutation testing diagnostic until a baseline exists.

**Tech Stack:** Python 3.11, pytest, pytest-cov, Hypothesis, pip-audit, mutmut, GitHub Actions, Docker

---

## File Structure

- `requirements-dev.txt`: pin the new development-only quality tools.
- `pyproject.toml`: configure coverage and mutation scope.
- `tests/raoeo/test_properties.py`: generated strategy invariants.
- `tests/fixtures/kis/ws_records.json`: sanitized KIS replay samples.
- `tests/fixtures/toss/holdings_responses.json`: sanitized Toss replay samples.
- `tests/kis/test_kis_replay.py`: offline WebSocket replay assertions.
- `tests/toss/test_toss_replay.py`: offline Toss response replay assertions.
- `.github/workflows/ci.yml`: coverage, audit, and Docker smoke jobs.
- `README.md`: document blocking and diagnostic commands.

### Task 1: Development Toolchain

**Files:**
- Modify: `requirements-dev.txt`
- Modify: `pyproject.toml`

- [ ] **Step 1: Verify the tools are not yet available**

Run:

```bash
venv/bin/python -c "import coverage, hypothesis"
venv/bin/pip-audit --version
venv/bin/mutmut --version
```

Expected: at least one import or command fails because the new toolchain has
not been installed.

- [ ] **Step 2: Add bounded development dependencies**

Append:

```text
pytest-cov>=6,<8
hypothesis>=6.130,<7
pip-audit>=2.9,<3
mutmut>=3,<4
```

- [ ] **Step 3: Configure coverage and mutation scope**

Add to `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src"]
omit = ["src/kis/kis_api/*"]

[tool.coverage.report]
show_missing = true
skip_covered = true

[tool.mutmut]
source_paths = ["src/strategy/", "src/broker/"]
pytest_add_cli_args_test_selection = ["tests/raoeo/", "tests/kis/"]
```

- [ ] **Step 4: Install the development dependencies**

Run:

```bash
venv/bin/pip install -r requirements-dev.txt
```

Expected: installation completes and all four tools report versions.

### Task 2: Property-Based Strategy Invariants

**Files:**
- Create: `tests/raoeo/test_properties.py`

- [ ] **Step 1: Write generated invariant tests**

Create tests equivalent to:

```python
from hypothesis import given, strategies as st

from strategy.base import OrderSide, StrategyOrder
from strategy.raoeo import calculate_cash_funding_order
from strategy.rebalancing import _build_rebalance_orders


@given(
    price=st.floats(min_value=0.01, max_value=10_000, allow_nan=False),
    quantity=st.integers(min_value=1, max_value=10_000),
    orderable=st.floats(min_value=0, max_value=1_000_000, allow_nan=False),
)
def test_cash_funding_never_sells_more_than_the_holding(price, quantity, orderable):
    buy = StrategyOrder("SOXL", OrderSide.BUY, quantity, price)
    holding_qty = quantity + 1
    order, _ = calculate_cash_funding_order(
        [buy],
        {"SGOV": {"qty": holding_qty}},
        {"SGOV": price},
        "SGOV",
        orderable,
    )
    assert order is None or 0 < order.quantity <= holding_qty


@given(
    current_price=st.floats(min_value=1, max_value=10_000, allow_nan=False),
    quantity=st.integers(min_value=0, max_value=10_000),
    target_base=st.floats(min_value=1, max_value=1_000_000, allow_nan=False),
    target_weight=st.floats(min_value=0, max_value=1, allow_nan=False),
)
def test_rebalance_orders_always_have_positive_quantity(
    current_price, quantity, target_base, target_weight
):
    orders, _ = _build_rebalance_orders(
        {
            "SOXL": {
                "cur_price": current_price,
                "qty": quantity,
                "current_value": current_price * quantity,
                "target_weight": target_weight,
            }
        },
        target_base,
    )
    assert all(order.quantity > 0 for order in orders)
```

- [ ] **Step 2: Run the focused generated tests**

Run:

```bash
venv/bin/pytest -q tests/raoeo/test_properties.py
```

Expected: PASS without network or credential access. If Hypothesis finds a
counterexample, preserve it as a conventional regression test before changing
production behavior.

### Task 3: Offline Response Replay

**Files:**
- Create: `tests/fixtures/kis/ws_records.json`
- Create: `tests/fixtures/toss/holdings_responses.json`
- Create: `tests/kis/test_kis_replay.py`
- Create: `tests/toss/test_toss_replay.py`

- [ ] **Step 1: Add sanitized replay fixtures**

The KIS fixture contains:

```json
{
  "columns": ["SYMBOL", "PRICE", "QUANTITY"],
  "records": [
    {"name": "normal", "values": ["SOXL", "25.10", "3"]},
    {"name": "missing", "values": ["SOXL", "25.10"]},
    {"name": "extended", "values": ["SOXL", "25.10", "3", "EXTRA"]}
  ]
}
```

The Toss fixture contains:

```json
{
  "normal": {"result": {"items": [{"symbol": "AAPL", "quantity": "2"}]}},
  "empty": {"result": {"items": []}},
  "null_items": {"result": {"items": null}}
}
```

- [ ] **Step 2: Write KIS replay tests**

Load each fixture record, call `normalize_record(values, columns)`, and assert
that every normalized result has exactly the configured column count. Assert
that missing and extended records produce `padded` and `truncated` notes.

- [ ] **Step 3: Write Toss replay tests**

Feed fixture payloads through the existing injected `urlopen` seam used by
`tests/toss/test_api_helpers.py`. Assert that normal and empty responses parse
without network access. For `null_items`, assert the current documented parser
behavior rather than adding a generic replay abstraction.

- [ ] **Step 4: Run replay tests**

Run:

```bash
venv/bin/pytest -q tests/kis/test_kis_replay.py tests/toss/test_toss_replay.py
```

Expected: PASS with no DNS or credential access.

### Task 4: CI Coverage, Audit, and Docker Smoke

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Replace the pytest CI command with coverage reporting**

Use:

```yaml
- name: Run pytest with coverage
  run: pytest --cov=src --cov-report=term-missing tests
```

- [ ] **Step 2: Add dependency auditing**

Use:

```yaml
- name: Audit dependencies
  run: pip-audit -r requirements.txt
```

- [ ] **Step 3: Add an isolated Docker smoke job**

Add:

```yaml
docker-smoke:
  runs-on: ubuntu-latest
  timeout-minutes: 20
  steps:
    - uses: actions/checkout@v4
    - name: Build runtime image
      run: docker build -t trading-bot:test .
    - name: Run tests in runtime image
      run: docker run --rm --entrypoint python trading-bot:test -m pytest tests
```

This overrides the image entrypoint and therefore never starts `src/main.py`.

- [ ] **Step 4: Validate workflow syntax and local equivalents**

Run:

```bash
venv/bin/pytest --cov=src --cov-report=term-missing tests
venv/bin/pip-audit -r requirements.txt
docker build -t trading-bot:test .
docker run --rm --entrypoint python trading-bot:test -m pytest tests
```

Expected: all commands pass; the Docker command exits after tests and never
starts the trading runtime.

### Task 5: Mutation Diagnostic and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run a bounded mutation smoke check**

Run:

```bash
venv/bin/mutmut run --max-children 1
venv/bin/mutmut results
```

Expected: mutmut can collect and execute mutations only in the configured
application-owned paths. Surviving mutants are diagnostic and do not fail CI.

- [ ] **Step 2: Document commands and enforcement**

Add commands for coverage, Hypothesis tests, dependency auditing, mutation
testing, and Docker smoke verification. State that Ruff, mypy, pytest, and
pip-audit are blocking; coverage percentage and mutation score are diagnostic.

- [ ] **Step 3: Run all verification**

Run:

```bash
venv/bin/ruff check src tests
venv/bin/mypy
venv/bin/pytest --cov=src --cov-report=term-missing tests
venv/bin/pip-audit -r requirements.txt
git diff --check
```

Expected: all commands exit zero and the test count is greater than 186.
