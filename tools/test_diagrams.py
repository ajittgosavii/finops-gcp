"""The architecture diagrams must not lie.

They name React routes, Python modules and counts. A rename or a deleted
connector leaves the diagram quietly wrong, which is worse than having no
diagram -- a client reads it as documentation. These tests are cheap and catch
exactly that drift.

    pytest tools
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "packages", "finops-core", "src"))

pytest.importorskip("matplotlib")
import diagrams as dg  # noqa: E402

EXPECTED = {"hld", "end_user_view", "lld", "cloud_onboarding"}


def test_the_four_views_render_to_svg_and_png(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(dg, "OUT_DIR", str(tmp_path))
    built = dg.build_all()
    assert set(built) == EXPECTED
    for paths in built.values():
        assert len(paths) == 2  # svg + png
        for p in paths:
            assert os.path.exists(p) and os.path.getsize(p) > 5_000


def test_svg_keeps_text_as_text(tmp_path, monkeypatch) -> None:
    """`svg.fonttype='none'` keeps labels editable and searchable rather than
    outlining them to paths. That is the whole reason we ship SVG alongside PNG:
    the client can open it in Illustrator or Figma and retype a label."""
    monkeypatch.setattr(dg, "OUT_DIR", str(tmp_path))
    svg = open(dg.hld()[0], encoding="utf-8").read()
    assert "<text" in svg
    assert "viewBox" in svg
    assert "BigQuery" in svg  # a real label, not an outlined path
    assert "OCI" in svg


def test_every_module_named_on_the_low_level_diagram_imports() -> None:
    for name in dg.LLD_MODULES:
        assert importlib.import_module(name), name


def test_every_page_named_on_the_end_user_view_exists() -> None:
    """The persona -> page mapping is only meaningful if the pages are real."""
    pages_dir = os.path.join(ROOT, "web", "src", "pages")
    on_disk = {f[:-4] for f in os.listdir(pages_dir) if f.endswith(".tsx")}
    assert set(dg.PAGES) == on_disk, f"diagram: {sorted(dg.PAGES)}  disk: {sorted(on_disk)}"


def test_connector_count_on_the_diagram_matches_the_registry() -> None:
    from finops_core.connectors import REGISTRY

    src = open(os.path.join(ROOT, "tools", "diagrams.py"), encoding="utf-8").read()
    assert f"{len(REGISTRY)} connectors" in src


def test_lever_count_on_the_diagram_matches_the_catalog() -> None:
    from finops_core.engines import optimize

    src = open(os.path.join(ROOT, "tools", "diagrams.py"), encoding="utf-8").read()
    assert f"{len(optimize.LEVERS)}-lever" in src


def test_agent_tool_count_on_the_low_level_diagram_is_real() -> None:
    """The LLD advertises how many typed tools the agents get. If someone adds a
    tool and forgets the diagram, the client is told a wrong number."""
    from app.agents.tools import build_tools  # noqa: WPS433
    from app.repository import DemoRepository  # noqa: WPS433
    from app.settings import Settings  # noqa: WPS433

    tools_by_agent = build_tools(DemoRepository(Settings(data_source="demo")))
    distinct = {t.__name__ for tools in tools_by_agent.values() for t in tools}

    src = open(os.path.join(ROOT, "tools", "diagrams.py"), encoding="utf-8").read()
    assert f"{len(distinct)} typed tools" in src, f"the LLD names a tool count; there are {len(distinct)}"
