# Change Log

A running record of non-obvious changes made to this repo, with reasoning, for team communication.

---

## 2026-03-21

### Added `trading_engine` as a Git Submodule

**What:** Added the [trading_engine](https://github.com/Quant-Backtester/trading_engine) repository as a git submodule located at `engine/`.

**Command run:**
```bash
git submodule add https://github.com/Quant-Backtester/trading_engine.git engine
```

**Why:** The backend needs the backtesting engine to execute user strategies. Using a submodule keeps both repos independently versioned while allowing them to be developed together. Teammates cloning this repo should run:
```bash
git submodule update --init --recursive
```

**Known issue — `pyproject.toml` misconfiguration in the engine repo:**
The engine's `pyproject.toml` declares a `src/` layout:
```toml
[tool.setuptools]
package-dir = { "" = "src" }
```
But the actual source code lives in the repo root (no `src/` directory exists). This means `pip install -e ./engine` will not work out of the box.

**Workaround (pending fix):** Until the engine's `pyproject.toml` is corrected, import the engine by adding its path to `sys.path` in the backend entry point, or fix the `pyproject.toml` in the submodule to remove the `src/` layout setting.
