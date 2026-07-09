# Strategy Core Mypy Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `raoeo.py` and `execution_service.py` to the enforced mypy scope without changing runtime trading behavior.

**Architecture:** Treat mypy failures as the red test and correct only inaccurate or incomplete type declarations. Add each source file to `tool.mypy.files` only after its focused mypy and RAOEO regression tests pass; keep `src/kis/kis_api/**` excluded.

**Tech Stack:** Python 3.11 typing, mypy, Ruff, pytest, Docker Compose

---

### Task 1: Type-check RAOEO calculations

**Files:**
- Modify: `src/strategy/raoeo.py`
- Modify: `pyproject.toml`
- Test: `tests/raoeo/test_strategy.py`

- [x] **Step 1: Confirm the focused mypy failure**

Run: `venv/bin/mypy src/strategy/raoeo.py`

Expected: failures for the `NamedTuple` field named `index` and the unannotated nested `info` dictionary.

- [x] **Step 2: Correct the internal types**

Rename the private `BuyPlan.index` field to `rule_index` and update its two internal reads. Annotate the result accumulator as:

```python
info: Dict[str, Dict[str, Any]] = {
    "ticker_info": {},
    "skipped_buy_budgets": {},
}
```

Import `Any` from `typing`. These changes preserve order calculation and returned values.

- [x] **Step 3: Verify the focused unit**

Run: `venv/bin/mypy src/strategy/raoeo.py`

Expected: success with no issues.

Run: `venv/bin/pytest tests/raoeo/test_strategy.py`

Expected: all RAOEO tests pass.

- [x] **Step 4: Enforce the new file**

Add `src/strategy/raoeo.py` to `tool.mypy.files`, then run `venv/bin/mypy`.

Expected: the configured mypy scope passes.

### Task 2: Type-check strategy execution orchestration

**Files:**
- Modify: `requirements-dev.txt`
- Modify: `src/strategy/execution_service.py`
- Modify: `pyproject.toml`
- Test: `tests/raoeo/test_strategy.py`

- [x] **Step 1: Supply the requests typing dependency**

Add a Python-3.11-compatible `types-requests` development dependency to `requirements-dev.txt` and install the updated development requirements in the repository virtualenv.

Run: `venv/bin/mypy src/strategy/execution_service.py`

Expected: the `requests` stub error is gone; local annotation errors remain red.

- [x] **Step 2: Correct nullable contracts and local inference**

Use `Optional[...]` for parameters whose default is `None`, and declare `_get_today_entry` as returning `Optional[Dict]`. Rename the two local history payload variables in `run_raoeo_strategy` from `hist_data` to `save_data` so the earlier history-list type is not reused for a dictionary.

- [x] **Step 3: Verify the focused unit**

Run: `venv/bin/mypy src/strategy/execution_service.py`

Expected: success with no issues.

Run: `venv/bin/pytest tests/raoeo/test_strategy.py`

Expected: all RAOEO and execution-service tests pass.

- [x] **Step 4: Enforce the new file**

Add `src/strategy/execution_service.py` to `tool.mypy.files`, then run `venv/bin/mypy`.

Expected: the configured mypy scope passes.

### Task 3: Verify the repository and report remaining debt

**Files:**
- No additional source changes expected

- [x] **Step 1: Run host verification**

Run:

```bash
venv/bin/ruff check src tests
venv/bin/mypy
venv/bin/pytest tests
```

Expected: all commands exit successfully.

- [x] **Step 2: Run Docker verification**

Run: `docker compose exec -T trading-bot python -m pytest tests`

Expected: the full container test suite passes.

- [x] **Step 3: Re-run the broader mypy audit**

Run: `venv/bin/mypy src/strategy src/broker src/state`

Expected: failures remain only outside the newly enforced files. Group them by module and error code in the completion report; do not add those files to `tool.mypy.files`.
