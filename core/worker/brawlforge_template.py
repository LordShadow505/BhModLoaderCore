"""
BrawlForgeSuite AS3 template loader.

Loads BrawlForgeSuite.as from core/assets/ and fills in the hardcoded symbol
constants from symbols.json. The symbols are extracted from BrawlhallaAir.swf
by the symbol resolver and updated on each 'Fix' command.

Architecture:
- BrawlForgeSuite.as uses HARDCODED constants for all property access in its hot loop
  (no describeType() every frame) -> ~100+ FPS
- setHandArt() uses hardcoded ART_SUFFIX_PROP first, falls back to KNOWN_HAND_TYPES
  reflection only once to discover the correct prop, then caches it
- Fix command updates symbols.json + rebuilds the carrier with new constants
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path

_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_BRAWLFORGE_SUITE_AS_PATH = _ASSETS_DIR / "BrawlForgeSuite.as"
_SYMBOLS_JSON_PATH = _ASSETS_DIR / "symbols.json"

# Default symbol values (from probe on 2026-08-21, Brawlhalla build ~10.x)
_DEFAULT_SYMBOLS: Dict[str, str] = {
    "costume_reg_prop": "_-22J",
    "gfx_prop": "_-v1x",
    "art_suffix_prop": "_-O3M",
    "cs_class_name": "_-d14",
    "cs_reg_prop": "_-w5Q",
    "gc_prop": "_-o4J",
    "gc_entities_prop": "_-t5r",
}


def load_symbols() -> Dict[str, str]:
    """Load flat symbols from symbols_manager (AppData with local fallback)."""
    try:
        from ..utils.symbols_manager import get_flat_symbols
        return get_flat_symbols()
    except Exception:
        pass

    if _SYMBOLS_JSON_PATH.exists():
        try:
            data = json.loads(_SYMBOLS_JSON_PATH.read_text(encoding="utf-8"))
            merged = dict(_DEFAULT_SYMBOLS)
            for k in _DEFAULT_SYMBOLS:
                if k in data and isinstance(data[k], str) and data[k]:
                    merged[k] = data[k]
            return merged
        except Exception:
            pass
    return dict(_DEFAULT_SYMBOLS)


def save_symbols(symbols: Dict[str, Any], trigger: str = "TemplateUpdate") -> None:
    """Persist symbols using symbols_manager (AppData & local assets)."""
    try:
        from ..utils.symbols_manager import save_symbols as _sm_save
        _sm_save(symbols, trigger=trigger)
        return
    except Exception:
        pass

    from datetime import date
    existing: Dict[str, Any] = {}
    if _SYMBOLS_JSON_PATH.exists():
        try:
            existing = json.loads(_SYMBOLS_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing.update(symbols)
    existing["updated_at"] = str(date.today())
    _SYMBOLS_JSON_PATH.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _load_brawlforge_suite_as_raw() -> str:
    """Load the raw BrawlForgeSuite.as template text."""
    if _BRAWLFORGE_SUITE_AS_PATH.exists():
        return _BRAWLFORGE_SUITE_AS_PATH.read_text(encoding="utf-8")
    for candidate in [
        Path(__file__).parent.parent.parent / "BrawlhallaModLoader" / "core" / "assets" / "BrawlForgeSuite.as",
        Path(__file__).parent / "BrawlForgeSuite.as",
    ]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"BrawlForgeSuite.as not found. Expected at: {_BRAWLFORGE_SUITE_AS_PATH}"
    )


def generate_brawlforge_suite_as(symbols: Optional[Dict[str, Any]] = None) -> str:
    """
    Returns BrawlForgeSuite.as with hardcoded symbol constants filled in.

    The template uses %%SYMBOL_NAME%% placeholders that are replaced with the
    actual obfuscated property names. These are loaded from symbols.json or
    provided directly via the `symbols` parameter.

    Fast path: uses hardcoded props in the hot loop (no reflection every frame).
    Fix command: updates symbols.json -> call this again to get fresh AS3.
    """
    template = _load_brawlforge_suite_as_raw()

    if symbols is None:
        symbols = load_symbols()

    # Map template placeholders to resolved values
    replacements = {
        "%%COSTUME_REG_PROP%%": symbols.get("costume_reg_prop", _DEFAULT_SYMBOLS["costume_reg_prop"]),
        "%%GFX_PROP%%":         symbols.get("gfx_prop",         _DEFAULT_SYMBOLS["gfx_prop"]),
        "%%ART_SUFFIX_PROP%%":  symbols.get("art_suffix_prop",  _DEFAULT_SYMBOLS["art_suffix_prop"]),
        "%%CS_CLASS_NAME%%":    symbols.get("cs_class_name",    _DEFAULT_SYMBOLS["cs_class_name"]),
        "%%CS_REG_PROP%%":      symbols.get("cs_reg_prop",      _DEFAULT_SYMBOLS["cs_reg_prop"]),
        "%%CS_COLORS_PROP%%":   symbols.get("cs_colors_prop",   "_-6y"),
        "%%GC_PROP%%":          symbols.get("gc_prop",          _DEFAULT_SYMBOLS["gc_prop"]),
        "%%GC_ENTITIES_PROP%%": symbols.get("gc_entities_prop", _DEFAULT_SYMBOLS["gc_entities_prop"]),
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    return template


def sync_master_carrier_assets(bh_dir: Optional[str] = None) -> bool:
    """
    Synchronizes the BrawlForgeSuite script in the carrier SWF assets.
    Uses hardcoded symbols from symbols.json.
    The bh_dir parameter is accepted for API compatibility but no longer used here.
    """
    try:
        from ..swf.swf import Swf

        carrier_dir = Path(__file__).parent.parent / "assets"
        if not carrier_dir.exists():
            carrier_dir = Path(__file__).parent.parent.parent / "BrawlhallaModLoader" / "core" / "assets"

        carrier_swf = carrier_dir / "carrier_UI_MainMenu.swf"
        if not carrier_swf.exists():
            carrier_swf = carrier_dir / "UI_MainMenu.swf"
        if not carrier_swf.exists():
            return False

        as3_code = generate_brawlforge_suite_as()

        swf_obj = Swf(str(carrier_swf))
        swf_obj.setAS3("tier_b/BrawlForgeSuite", as3_code)
        swf_obj.save()

        print(f"[BrawlForge] Carrier updated with hardcoded symbols.")
        return True
    except Exception as exc:
        print(f"[BrawlForge] Error updating carrier: {exc}")
        return False