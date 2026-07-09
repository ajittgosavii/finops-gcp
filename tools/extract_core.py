"""Lift the Streamlit app's proven core into an installable `finops_core` package.

This is a mechanical, re-runnable transform, not a hand edit. The source modules
(`focus`, `kpi`, the five engines, 17 connectors) import each other by top-level
name because they lived side by side in a flat Streamlit app. Inside a package
those imports have to be absolute.

The only judgement calls encoded here:

* `finops_core.py` becomes `finops_core/config.py`, because a module cannot share
  a name with the package that contains it.
* The engines move under `finops_core/engines/`, because "forecast" is far too
  generic a top-level name to claim in a shared package.
* Nothing Streamlit-shaped comes across. `data.py` (the Streamlit loader) and
  `store.py` (which reads `st.secrets`) stay behind; the backend supplies its own.

Run:  python tools/extract_core.py --src ../multicloud-finops
Then: pytest packages/finops-core
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys
from typing import Dict, Iterable, List, Tuple

PKG = "finops_core"

# Flat module -> destination inside the package.
TOP_LEVEL = {
    "focus.py": "focus.py",
    "kpi.py": "kpi.py",
    "finops_core.py": "config.py",  # cannot shadow the package name
}
ENGINES = ["forecast.py", "budget.py", "anomaly.py", "allocation.py", "optimize.py"]

# `import X` / `from X import ...` rewrites applied to every copied file.
#
# ORDER MATTERS. `from finops_core import ...` must be rewritten BEFORE
# `import finops_core`, or the latter's output (`from finops_core import config
# as finops_core`) is itself matched by the former and mangled into
# `from finops_core.config import config as finops_core`.
# `(?m)^(\s*)` captures indentation: several modules import a sibling INSIDE a
# function to keep the import lazy, and a rule anchored to column zero silently
# skips those. One such import (`import focus`, inside a test helper) survived
# the first pass and only surfaced when the ported tests ran.
REWRITES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^(\s*)from finops_core import (.+)$", re.M), rf"\1from {PKG}.config import \2"),
    (re.compile(r"^(\s*)import finops_core$", re.M), rf"\1from {PKG} import config as finops_core"),
    # sibling leaf modules
    (re.compile(r"^(\s*)import focus$", re.M), rf"\1from {PKG} import focus"),
    (re.compile(r"^(\s*)import kpi$", re.M), rf"\1from {PKG} import kpi"),
    # engines importing each other
    (re.compile(r"^(\s*)import (forecast|budget|anomaly|allocation|optimize)$", re.M),
     rf"\1from {PKG}.engines import \2"),
    (re.compile(r"^(\s*)from (forecast|budget|anomaly|allocation|optimize) import (.+)$", re.M),
     rf"\1from {PKG}.engines.\2 import \3"),
    # connectors
    (re.compile(r"^(\s*)import connectors$", re.M), rf"\1from {PKG} import connectors"),
    (re.compile(r"^(\s*)from connectors\.base import (.+)$", re.M), rf"\1from {PKG}.connectors.base import \2"),
    (re.compile(r"^(\s*)from connectors\.vendors\._http import (.+)$", re.M),
     rf"\1from {PKG}.connectors.vendors._http import \2"),
    (re.compile(r"^(\s*)from connectors\.demo import (.+)$", re.M), rf"\1from {PKG}.connectors.demo import \2"),
    (re.compile(r"^(\s*)from connectors import (.+)$", re.M), rf"\1from {PKG}.connectors import \2"),
    (re.compile(r"^(\s*)import connectors as (\w+)$", re.M), rf"\1from {PKG} import connectors as \2"),
    # the registry's lazy "module:Class" strings
    (re.compile(r'"connectors\.'), f'"{PKG}.connectors.'),
]

# The test files need the same treatment; the indentation-aware rules cover them.
TEST_REWRITES: List[Tuple[re.Pattern, str]] = REWRITES

# Anything matching this in the output means a rewrite rule missed. A silent miss
# becomes an ImportError inside a Cloud Run container, which is a bad place to
# discover it.
UNRESOLVED = re.compile(
    r"^(import|from) (focus|kpi|theme|ui|charts|brand|connectors|forecast|budget"
    r"|anomaly|allocation|optimize|streamlit)\b"
)


# ---------------------------------------------------------------------------
# `config.py` needs more than an import rewrite.
#
# The Streamlit app read secrets from `st.secrets`, falling back to the
# environment. A package cannot reach for a framework's secret store: the caller
# owns where secrets come from (Secret Manager, a .env file, a test dict). So
# `load_config` takes a Mapping. It also loses the OpenAI fields entirely --
# this package does not know that an LLM exists.
#
# Encoded here rather than hand-edited, so `extract_core.py` stays the single
# source of truth and re-running it does not silently undo the change.
# ---------------------------------------------------------------------------

CONFIG_PATCHES: List[Tuple[str, str]] = [
    (
        '''def _secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read from Streamlit secrets, then the environment."""
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)''',
        '''# Configuration arrives as a plain mapping. This package never reaches for a
# framework's secret store, so the same code serves Streamlit, FastAPI and a
# batch job. The caller decides whether that mapping is os.environ, Secret
# Manager, or a dict in a test.
Source = Mapping[str, str]


def _secret(key: str, default: Optional[str] = None, source: Optional[Source] = None) -> Optional[str]:
    src = os.environ if source is None else source
    value = src.get(key, default)
    return None if value is None else str(value)''',
    ),
    (
        '''    try:
        import streamlit as st

        raw = st.secrets.get("accounts")
    except Exception:
        raw = None
    if not raw:
        return []''',
        '''    src = os.environ if source is None else source
    raw = src.get("FINOPS_ACCOUNTS")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not raw:
        return []''',
    ),
    (
        "def _load_account_bindings() -> List[AccountBinding]:",
        "def _load_account_bindings(source: Optional[Source] = None) -> List[AccountBinding]:",
    ),
    (
        '''def load_config(mode: Optional[Mode] = None) -> AppConfig:
    cfg = AppConfig()
    cfg.mode = mode or resolve_mode(_secret("FINOPS_MODE"))
    cfg.organisation = _secret("ORGANISATION", "Con Edison") or "Con Edison"
    cfg.openai_api_key = _secret("OPENAI_API_KEY")
    cfg.openai_model = _secret("OPENAI_MODEL", "gpt-5") or "gpt-5"
    cfg.openai_model_fast = _secret("OPENAI_MODEL_FAST", "gpt-5-mini") or "gpt-5-mini"
    cfg.database_url = _secret("DATABASE_URL")
    cfg.accounts = _load_account_bindings()
    return cfg''',
        '''def load_config(mode: Optional[Mode] = None, source: Optional[Source] = None) -> AppConfig:
    """Build an AppConfig from any mapping. Defaults to the process environment."""
    cfg = AppConfig()
    cfg.mode = mode or resolve_mode(_secret("FINOPS_MODE", source=source))
    cfg.organisation = _secret("ORGANISATION", "Con Edison", source) or "Con Edison"
    cfg.database_url = _secret("DATABASE_URL", source=source)
    cfg.accounts = _load_account_bindings(source)
    return cfg''',
    ),
    (
        '''    openai_api_key: Optional[str] = None
    # gpt-5 is the workhorse; gpt-5-mini backs the cheap routing tier so the
    # platform practises the small-model-first lever it recommends.
    openai_model: str = "gpt-5"
    openai_model_fast: str = "gpt-5-mini"

''',
        "",
    ),
    (
        '''    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)

''',
        "",
    ),
    (
        """from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional""",
        """import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional""",
    ),
]


def patch_config(text: str) -> str:
    for old, new in CONFIG_PATCHES:
        if old not in text:
            raise SystemExit(f"config.py patch no longer applies:\n---\n{old[:120]}...\n---")
        text = text.replace(old, new, 1)
    assert "streamlit" not in text, "config.py still references streamlit"
    return text


def rewrite(text: str, rules: Iterable[Tuple[re.Pattern, str]]) -> str:
    for pattern, repl in rules:
        text = pattern.sub(repl, text)
    # The rules are anchored to line starts, so a second pass over an
    # already-rewritten file is a no-op -- except that `import focus` inside
    # `from finops_core import focus` would match again if a rule ever loses its
    # anchor. Assert idempotence rather than trust it.
    assert "from finops_core from" not in text, "import rewrite applied twice"
    return text


def copy(src: pathlib.Path, dst: pathlib.Path, rules) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(rewrite(src.read_text(encoding="utf-8"), rules), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="../multicloud-finops")
    args = ap.parse_args()

    src = pathlib.Path(args.src).resolve()
    root = pathlib.Path(__file__).resolve().parent.parent
    pkg = root / "packages" / "finops-core" / "src" / PKG
    tests = root / "packages" / "finops-core" / "tests"

    if not (src / "focus.py").exists():
        print(f"error: {src} does not look like the Streamlit app", file=sys.stderr)
        return 1

    for name, dest in TOP_LEVEL.items():
        copy(src / name, pkg / dest, REWRITES)

    # config.py additionally sheds Streamlit and the LLM provider fields.
    cfg_path = pkg / "config.py"
    cfg_path.write_text(patch_config(cfg_path.read_text(encoding="utf-8")), encoding="utf-8")

    for name in ENGINES:
        copy(src / name, pkg / "engines" / name, REWRITES)

    for p in (src / "connectors").rglob("*.py"):
        rel = p.relative_to(src / "connectors")
        copy(p, pkg / "connectors" / rel, REWRITES)

    for name in ["test_engines.py", "test_optimize.py"]:
        copy(src / "tests" / name, tests / name, TEST_REWRITES)

    (pkg / "engines" / "__init__.py").write_text(
        '"""Analytics engines. Pure pandas/numpy -- no Streamlit, no cloud SDK."""\n\n'
        "from finops_core.engines import allocation, anomaly, budget, forecast, optimize  # noqa: F401\n",
        encoding="utf-8",
    )

    bad: List[str] = []
    for f in list(pkg.rglob("*.py")) + list(tests.rglob("*.py")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if UNRESOLVED.match(line.strip()):
                bad.append(f"{f.relative_to(root)}:{i}: {line.strip()}")
    if bad:
        print("unresolved imports -- a rewrite rule missed:", file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        return 1

    n = len(list(pkg.rglob("*.py")))
    print(f"copied {n} modules into {pkg.relative_to(root)}; no unresolved imports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
