"""
ui/plugin_api.py
Plugin system for third-party custom widgets.
Related: app.py, ui/components.py

Plugins are Python modules in the `plugins/` directory
that export a `widget()` function receiving (toilets, t) dicts.
"""
import importlib
import logging
from collections.abc import Callable
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path("plugins")


def discover_plugins() -> list[str]:
    """Find all available plugin modules."""
    if not PLUGIN_DIR.exists():
        return []
    return sorted(
        p.stem for p in PLUGIN_DIR.glob("*.py")
        if p.stem != "__init__"
    )


def load_plugin(name: str) -> Callable | None:
    """Load a plugin module and return its widget function."""
    try:
        mod = importlib.import_module(f"plugins.{name}")
        if hasattr(mod, "widget") and callable(mod.widget):
            return mod.widget
        logger.warning("Plugin '%s' has no widget() function", name)
    except Exception as e:
        logger.exception("Failed to load plugin '%s': %s", name, e)
    return None


def render_plugins(toilets: list[dict], t: dict) -> None:
    """Render all enabled plugins."""
    available = discover_plugins()
    if not available:
        return

    enabled = st.session_state.get("enabled_plugins", [])
    for name in enabled:
        if name not in available:
            continue
        widget_fn = load_plugin(name)
        if widget_fn:
            try:
                widget_fn(toilets, t)
            except Exception as e:
                st.error(f"Plugin '{name}' error: {e}")
                logger.exception("Plugin '%s' runtime error", name)


def render_plugin_manager(t: dict) -> None:
    """Show plugin management UI in sidebar."""
    available = discover_plugins()
    if not available:
        return

    with st.expander(t.get("plugins", "🔌 プラグイン"), expanded=False):
        enabled = st.session_state.get("enabled_plugins", [])
        for name in available:
            is_enabled = st.checkbox(name, value=name in enabled, key=f"plugin_{name}")
            if is_enabled and name not in enabled:
                st.session_state.setdefault("enabled_plugins", []).append(name)
            elif not is_enabled and name in enabled:
                st.session_state["enabled_plugins"].remove(name)
