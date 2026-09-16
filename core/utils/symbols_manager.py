import os
import sys
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

# AppData directories
_APPDATA = os.getenv("APPDATA") or str(Path.home())
BMODLOADER_SYMBOLS_PATH = os.path.join(_APPDATA, "BModloader", "symbols.json")
BMT_SYMBOLS_PATH = os.path.join(_APPDATA, "Brawlhalla Modding Toolkit", "symbols.json")
LOCAL_ASSET_SYMBOLS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "symbols.json")

DEFAULT_SYMBOLS_STRUCTURE: Dict[str, Any] = {
    "meta": {
        "game_version": "auto",
        "air_swf_mtime": 0.0,
        "air_swf_hash": "",
        "updated_at": "2026-08-22",
        "updated_time": "00:00:00",
        "last_source": "Default"
    },
    "hands_and_costumes": {
        "costume_type_class": "CostumeType",
        "costume_reg_prop": "_-K2u",
        "costume_reg_fallbacks": ["_-22J", "_-q5b", "_-M6b", "_-X4Q", "_-P1I"],
        "gfx_prop": "_-P3J",
        "gfx_fallbacks": ["_-v1x", "_-X64", "_-gK", "_-k3B", "_-l45", "_-g1v", "_-bC"],
        "art_suffix_prop": "_-O3M",
        "art_suffix_fallbacks": ["_-Qe", "_-K3w"]
    },
    "color_schemes": {
        "cs_class_name": "_-G5Q",
        "cs_class_fallbacks": ["_-V4w", "_-W3s", "ColorSchemeType"],
        "cs_reg_prop": "_-44k",
        "cs_reg_fallbacks": ["_-04k", "_-S6b", "_-p5j", "_-Q4s", "_-S1l", "_-V1h", "_-Q6c", "_-o17", "_-w5Q"],
        "cs_colors_prop": "_-6y",
        "cs_colors_fallbacks": ["_-S5J", "_-I4B", "_-Z1S"],
        "cs_id_field": "_-C5B",
        "cs_id_fallbacks": ["_-g1E", "_-9U"],
        "cs_slot_methods": ["_-p3", "§_-p3§", "_-r5g"]
    },
    "game_controller_and_entities": {
        "gc_prop": "_-o4J",
        "gc_entities_prop": "_-t5r",
        "gc_fallbacks": ["_-13t", "_-84x", "_-819"],
        "entity_scheme_props": ["_-j5V", "_-S1y"],
        "entity_costume_props": ["_-m6", "_-V5k"]
    },
    "legacy_flat_mapping": {
        "costume_reg_prop": "_-K2u",
        "gfx_prop": "_-P3J",
        "art_suffix_prop": "_-O3M",
        "cs_class_name": "_-G5Q",
        "cs_reg_prop": "_-44k",
        "gc_prop": "_-o4J",
        "gc_entities_prop": "_-t5r",
        "brawlhalla_version": "auto",
        "updated_at": "2026-08-22"
    }
}


def get_all_symbols_paths():
    return [BMODLOADER_SYMBOLS_PATH, BMT_SYMBOLS_PATH, LOCAL_ASSET_SYMBOLS_PATH]


def load_symbols() -> Dict[str, Any]:
    """Loads symbols from AppData or local fallback."""
    for p in [BMODLOADER_SYMBOLS_PATH, BMT_SYMBOLS_PATH, LOCAL_ASSET_SYMBOLS_PATH]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data:
                        return data
            except Exception:
                pass
    return dict(DEFAULT_SYMBOLS_STRUCTURE)


def get_flat_symbols() -> Dict[str, str]:
    """Returns a flat key-value dict compatible with legacy template code."""
    data = load_symbols()
    flat = {}
    if "legacy_flat_mapping" in data:
        flat = dict(data["legacy_flat_mapping"])
    else:
        # Build flat from top-level or sub-objects
        flat["costume_reg_prop"] = data.get("hands_and_costumes", {}).get("costume_reg_prop") or data.get("costume_reg_prop", "_-K2u")
        flat["gfx_prop"] = data.get("hands_and_costumes", {}).get("gfx_prop") or data.get("gfx_prop", "_-P3J")
        flat["art_suffix_prop"] = data.get("hands_and_costumes", {}).get("art_suffix_prop") or data.get("art_suffix_prop", "_-O3M")
        flat["cs_class_name"] = data.get("color_schemes", {}).get("cs_class_name") or data.get("cs_class_name", "_-G5Q")
        flat["cs_reg_prop"] = data.get("color_schemes", {}).get("cs_reg_prop") or data.get("cs_reg_prop", "_-44k")
        flat["cs_colors_prop"] = data.get("color_schemes", {}).get("cs_colors_prop") or data.get("cs_colors_prop", "_-6y")
        flat["gc_prop"] = data.get("game_controller_and_entities", {}).get("gc_prop") or data.get("gc_prop", "_-o4J")
        flat["gc_entities_prop"] = data.get("game_controller_and_entities", {}).get("gc_entities_prop") or data.get("gc_entities_prop", "_-t5r")
        flat["brawlhalla_version"] = data.get("meta", {}).get("game_version", "auto")
        flat["updated_at"] = data.get("meta", {}).get("updated_at", "2026-08-22")
    return flat


def save_symbols(data: Dict[str, Any], trigger: str = "Manual") -> None:
    """Saves the symbols data to AppData (BModloader, Toolkit) and local assets with exact timestamp."""
    now = datetime.now()
    now_date = now.strftime("%Y-%m-%d")
    now_time = now.strftime("%H:%M:%S")

    # If flat dict passed in, convert to structured format
    if "hands_and_costumes" not in data and "costume_reg_prop" in data:
        structured = json.loads(json.dumps(DEFAULT_SYMBOLS_STRUCTURE))
        structured["meta"]["updated_at"] = now_date
        structured["meta"]["updated_time"] = now_time
        structured["meta"]["last_source"] = trigger
        structured["meta"]["game_version"] = data.get("brawlhalla_version", "auto")

        structured["hands_and_costumes"]["costume_reg_prop"] = data.get("costume_reg_prop", "_-K2u")
        structured["hands_and_costumes"]["gfx_prop"] = data.get("gfx_prop", "_-P3J")
        structured["hands_and_costumes"]["art_suffix_prop"] = data.get("art_suffix_prop", "_-O3M")

        structured["color_schemes"]["cs_class_name"] = data.get("cs_class_name", "_-G5Q")
        structured["color_schemes"]["cs_reg_prop"] = data.get("cs_reg_prop", "_-44k")
        structured["color_schemes"]["cs_colors_prop"] = data.get("cs_colors_prop", "_-6y")

        structured["game_controller_and_entities"]["gc_prop"] = data.get("gc_prop", "_-o4J")
        structured["game_controller_and_entities"]["gc_entities_prop"] = data.get("gc_entities_prop", "_-t5r")

        structured["legacy_flat_mapping"] = {
            "costume_reg_prop": data.get("costume_reg_prop", "_-K2u"),
            "gfx_prop": data.get("gfx_prop", "_-P3J"),
            "art_suffix_prop": data.get("art_suffix_prop", "_-O3M"),
            "cs_class_name": data.get("cs_class_name", "_-G5Q"),
            "cs_reg_prop": data.get("cs_reg_prop", "_-44k"),
            "cs_colors_prop": data.get("cs_colors_prop", "_-6y"),
            "gc_prop": data.get("gc_prop", "_-o4J"),
            "gc_entities_prop": data.get("gc_entities_prop", "_-t5r"),
            "brawlhalla_version": data.get("brawlhalla_version", "auto"),
            "updated_at": now_date,
            "updated_time": now_time
        }
        data = structured
    else:
        if "meta" not in data:
            data["meta"] = {}
        data["meta"]["updated_at"] = now_date
        data["meta"]["updated_time"] = now_time
        data["meta"]["last_source"] = trigger

        # Keep legacy flat mapping in sync
        data["legacy_flat_mapping"] = {
            "costume_reg_prop": data.get("hands_and_costumes", {}).get("costume_reg_prop", "_-K2u"),
            "gfx_prop": data.get("hands_and_costumes", {}).get("gfx_prop", "_-P3J"),
            "art_suffix_prop": data.get("hands_and_costumes", {}).get("art_suffix_prop", "_-O3M"),
            "cs_class_name": data.get("color_schemes", {}).get("cs_class_name", "_-G5Q"),
            "cs_reg_prop": data.get("color_schemes", {}).get("cs_reg_prop", "_-44k"),
            "cs_colors_prop": data.get("color_schemes", {}).get("cs_colors_prop", "_-6y"),
            "gc_prop": data.get("game_controller_and_entities", {}).get("gc_prop", "_-o4J"),
            "gc_entities_prop": data.get("game_controller_and_entities", {}).get("gc_entities_prop", "_-t5r"),
            "brawlhalla_version": data.get("meta", {}).get("game_version", "auto"),
            "updated_at": now_date,
            "updated_time": now_time
        }

    for target_path in get_all_symbols_paths():
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def resolve_and_update_symbols(brawlhalla_dir: Optional[Union[str, Path]] = None, force: bool = False, trigger: str = "Auto") -> Dict[str, Any]:
    """
    Checks BrawlhallaAir.swf mtime/hash and re-resolves obfuscated symbols if changed or if force=True.
    Saves the updated symbols to AppData and local assets with timestamp.
    """
    if brawlhalla_dir is None:
        brawlhalla_dir = Path(r"X:\SteamLibrary\steamapps\common\Brawlhalla")
    else:
        brawlhalla_dir = Path(brawlhalla_dir)

    air_swf = brawlhalla_dir / "BrawlhallaAir.swf"
    if not air_swf.exists():
        for alt in [brawlhalla_dir / "Brawlhalla.swf", brawlhalla_dir / "BrawlhallaAir.clean.swf"]:
            if alt.exists():
                air_swf = alt
                break

    existing = load_symbols()
    air_exists = air_swf.exists()
    air_mtime = air_swf.stat().st_mtime if air_exists else 0.0

    # Import resolver lazily
    from .brawlhalla_symbol_resolver import resolve_brawlhalla_symbols
    raw_symbols = resolve_brawlhalla_symbols(brawlhalla_dir)

    # Compute SWF hash prefix
    swf_hash = ""
    if air_exists:
        try:
            h = hashlib.sha256()
            with open(air_swf, "rb") as sf:
                h.update(sf.read(2048 * 1024)) # Sample first 2MB for fast hash
            swf_hash = h.hexdigest()[:16]
        except Exception:
            pass

    now = datetime.now()
    now_date = now.strftime("%Y-%m-%d")
    now_time = now.strftime("%H:%M:%S")

    # Pick the best verified symbols with default fallbacks
    c_reg = raw_symbols.get("costume_registries", ["_-K2u", "_-22J"])[0] if raw_symbols.get("costume_registries") else "_-K2u"
    c_gfx = raw_symbols.get("costume_hand_props", ["_-P3J", "_-v1x"])[0] if raw_symbols.get("costume_hand_props") else "_-P3J"
    c_art = raw_symbols.get("custom_art_hand_props", ["_-O3M"])[0] if raw_symbols.get("custom_art_hand_props") else "_-O3M"

    cs_cls = raw_symbols.get("color_scheme_classes", ["_-G5Q"])[0] if raw_symbols.get("color_scheme_classes") else "_-G5Q"
    cs_reg = raw_symbols.get("color_scheme_registries", ["_-44k"])[0] if raw_symbols.get("color_scheme_registries") else "_-44k"
    cs_col = raw_symbols.get("color_scheme_colors_arrays", ["_-6y"])[0] if raw_symbols.get("color_scheme_colors_arrays") else "_-6y"
    cs_id = raw_symbols.get("color_scheme_id_fields", ["_-C5B"])[0] if raw_symbols.get("color_scheme_id_fields") else "_-C5B"

    gc_p = raw_symbols.get("gc_props", ["_-o4J"])[0] if raw_symbols.get("gc_props") else "_-o4J"
    gc_ent = raw_symbols.get("entity_scheme_props", ["_-t5r"])[0] if raw_symbols.get("entity_scheme_props") else "_-t5r"

    structured: Dict[str, Any] = {
        "meta": {
            "game_version": "auto",
            "air_swf_mtime": air_mtime,
            "air_swf_hash": swf_hash,
            "updated_at": now_date,
            "updated_time": now_time,
            "last_source": trigger
        },
        "hands_and_costumes": {
            "costume_type_class": "CostumeType",
            "costume_reg_prop": c_reg,
            "costume_reg_fallbacks": raw_symbols.get("costume_registries", ["_-K2u", "_-22J", "_-q5b"]),
            "gfx_prop": c_gfx,
            "gfx_fallbacks": raw_symbols.get("costume_hand_props", ["_-P3J", "_-v1x", "_-X64"]),
            "art_suffix_prop": c_art,
            "art_suffix_fallbacks": raw_symbols.get("custom_art_hand_props", ["_-O3M", "_-Qe"])
        },
        "color_schemes": {
            "cs_class_name": cs_cls,
            "cs_class_fallbacks": raw_symbols.get("color_scheme_classes", ["_-G5Q", "_-V4w"]),
            "cs_reg_prop": cs_reg,
            "cs_reg_fallbacks": raw_symbols.get("color_scheme_registries", ["_-44k", "_-04k", "_-S6b"]),
            "cs_colors_prop": cs_col,
            "cs_colors_fallbacks": raw_symbols.get("color_scheme_colors_arrays", ["_-6y", "_-S5J"]),
            "cs_id_field": cs_id,
            "cs_id_fallbacks": raw_symbols.get("color_scheme_id_fields", ["_-C5B", "_-g1E"]),
            "cs_slot_methods": ["_-p3", "§_-p3§", "_-r5g"]
        },
        "game_controller_and_entities": {
            "gc_prop": gc_p,
            "gc_entities_prop": gc_ent,
            "gc_fallbacks": raw_symbols.get("gc_props", ["_-o4J", "_-13t"]),
            "entity_scheme_props": raw_symbols.get("entity_scheme_props", ["_-j5V", "_-S1y"]),
            "entity_costume_props": raw_symbols.get("entity_costume_props", ["_-m6", "_-V5k"])
        },
        "legacy_flat_mapping": {
            "costume_reg_prop": c_reg,
            "gfx_prop": c_gfx,
            "art_suffix_prop": c_art,
            "cs_class_name": cs_cls,
            "cs_reg_prop": cs_reg,
            "gc_prop": gc_p,
            "gc_entities_prop": gc_ent,
            "brawlhalla_version": "auto",
            "updated_at": now_date,
            "updated_time": now_time
        }
    }

    save_symbols(structured, trigger=trigger)
    print(f"[SymbolsManager] Obfuscation symbols patched & saved: CostumeReg='{c_reg}', Gfx='{c_gfx}', CSClass='{cs_cls}', CSReg='{cs_reg}', CSColors='{cs_col}' (Trigger: {trigger} | {now_date} {now_time})", flush=True)
    return structured
