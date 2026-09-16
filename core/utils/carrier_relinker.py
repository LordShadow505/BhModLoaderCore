"""
Brawlhalla Carrier & Mod Symbol Relinker
=======================================
Dynamically detects and updates obfuscated symbols (Color schemes & CustomArt/Hands)
between BrawlhallaAir.swf and mod files (.bmod / UI_MainMenu.swf / carrier assets).

Supports:
- .bmod (SWF files containing MetadataTag / JSON / ActionScript)
- .zip / .7z mod archives
- Raw ActionScript / pcode scripts
"""

import os
import re
import json
import zlib
import struct
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


# ---------------------------------------------------------------------------
# In-memory & disk cache for resolved symbols keyed by BrawlhallaAir.swf mtime/size
# ---------------------------------------------------------------------------
_SYMBOLS_CACHE: Dict[str, Any] = {}


def find_brawlhalla_air_swf(custom_path: Optional[str] = None) -> Optional[str]:
    """Finds BrawlhallaAir.swf in custom path, Steam libraries, or default Windows locations."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file() and p.name.lower() == "brawlhallaair.swf":
            return str(p)
        candidate = p / "BrawlhallaAir.swf"
        if candidate.is_file():
            return str(candidate)

    try:
        from ..worker.brawlhalla import BRAWLHALLA_PATH
        if BRAWLHALLA_PATH and os.path.exists(BRAWLHALLA_PATH):
            cand = os.path.join(BRAWLHALLA_PATH, "BrawlhallaAir.swf")
            if os.path.isfile(cand):
                return cand
    except Exception:
        pass

    candidates = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Brawlhalla\BrawlhallaAir.swf"),
        Path(r"C:\Program Files\Steam\steamapps\common\Brawlhalla\BrawlhallaAir.swf"),
        Path(r"C:\Program Files\Epic Games\Brawlhalla\BrawlhallaAir.swf"),
        Path(r"C:\Program Files (x86)\Epic Games\Brawlhalla\BrawlhallaAir.swf"),
        Path(r"D:\Games\Steam\Steamapps\common\Brawlhalla\BrawlhallaAir.swf"),
        Path(r"X:\SteamLibrary\steamapps\common\Brawlhalla\BrawlhallaAir.swf"),
        Path(r"D:\SteamLibrary\steamapps\common\Brawlhalla\BrawlhallaAir.swf"),
        Path(r"E:\SteamLibrary\steamapps\common\Brawlhalla\BrawlhallaAir.swf"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)

    # Check steam libraryfolders.vdf
    vdf_paths = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf"),
        Path(r"C:\Program Files\Steam\steamapps\libraryfolders.vdf"),
    ]
    for vdf in vdf_paths:
        if vdf.is_file():
            try:
                text = vdf.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'"path"\s*"([^"]+)"', text):
                    raw = m.group(1).replace("\\\\", "\\")
                    c = Path(raw) / "steamapps" / "common" / "Brawlhalla" / "BrawlhallaAir.swf"
                    if c.is_file():
                        return str(c)
            except Exception:
                pass

    return None


def _extract_abc_blocks_from_swf(swf_bytes: bytes) -> List[bytes]:
    """Extracts all DoABC bytecode blocks from an uncompressed or compressed SWF."""
    sig = swf_bytes[:3]
    if sig == b'CWS':
        body = zlib.decompress(swf_bytes[8:])
    elif sig == b'FWS':
        body = swf_bytes[8:]
    elif sig == b'ZWS':
        import lzma
        body = lzma.decompress(swf_bytes[12:])
    else:
        return []

    nbits = body[0] >> 3
    rect_bits = 5 + nbits * 4
    rect_bytes = (rect_bits + 7) // 8
    pos = rect_bytes + 4

    abc_blocks = []
    while pos < len(body) - 2:
        tag_header = struct.unpack('<H', body[pos:pos+2])[0]
        pos += 2
        tag_code = tag_header >> 6
        tag_len = tag_header & 0x3F
        if tag_len == 0x3F:
            tag_len = struct.unpack('<I', body[pos:pos+4])[0]
            pos += 4

        if tag_code in (82, 72):
            name_end = body.find(b'\x00', pos + 4)
            if name_end != -1 and name_end < pos + tag_len:
                abc_data = body[name_end + 1 : pos + tag_len]
                abc_blocks.append(abc_data)
        elif tag_code == 0:
            break

        pos += tag_len

    return abc_blocks


class _SimpleABCReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.length = len(data)

    def read_u8(self) -> int:
        if self.pos >= self.length:
            return 0
        v = self.data[self.pos]
        self.pos += 1
        return v

    def read_u16(self) -> int:
        if self.pos + 2 > self.length:
            self.pos = self.length
            return 0
        v = struct.unpack('<H', self.data[self.pos:self.pos+2])[0]
        self.pos += 2
        return v

    def read_u30(self) -> int:
        result = 0
        shift = 0
        while self.pos < self.length:
            b = self.read_u8()
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        return result


def extract_strings_and_multinames(abc_data: bytes) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Parses string constant pool and multinames from ABC bytecode."""
    reader = _SimpleABCReader(abc_data)
    _ = reader.read_u16() # minor
    _ = reader.read_u16() # major

    # Ints
    n_ints = reader.read_u30()
    for _ in range(1, n_ints):
        reader.read_u30()

    # Uints
    n_uints = reader.read_u30()
    for _ in range(1, n_uints):
        reader.read_u30()

    # Doubles
    n_doubles = reader.read_u30()
    for _ in range(1, n_doubles):
        reader.pos += 8

    # Strings
    n_strings = reader.read_u30()
    strings = ['']
    for i in range(1, n_strings):
        s_len = reader.read_u30()
        if reader.pos + s_len > reader.length:
            break
        s_bytes = reader.data[reader.pos : reader.pos + s_len]
        reader.pos += s_len
        strings.append(s_bytes.decode('utf-8', errors='replace'))

    # Namespaces
    n_ns = reader.read_u30()
    namespaces = [('', 0)]
    for _ in range(1, n_ns):
        kind = reader.read_u8()
        name_idx = reader.read_u30()
        namespaces.append((strings[name_idx] if name_idx < len(strings) else '', kind))

    # Namespace sets
    n_nss = reader.read_u30()
    ns_sets = [[]]
    for _ in range(1, n_nss):
        cnt = reader.read_u30()
        ns_sets.append([reader.read_u30() for _ in range(cnt)])

    # Multinames
    n_mn = reader.read_u30()
    multinames = [('EMPTY', '')]
    for _ in range(1, n_mn):
        kind = reader.read_u8()
        if kind in (0x07, 0x0D):
            ns_idx = reader.read_u30()
            name_idx = reader.read_u30()
            ns_name = namespaces[ns_idx][0] if ns_idx < len(namespaces) else ''
            s_name = strings[name_idx] if name_idx < len(strings) else ''
            multinames.append((ns_name, s_name))
        elif kind in (0x0F, 0x10):
            name_idx = reader.read_u30()
            multinames.append(('', strings[name_idx] if name_idx < len(strings) else ''))
        elif kind in (0x11, 0x12):
            multinames.append(('', 'RTQNameL'))
        elif kind in (0x09, 0x0E):
            name_idx = reader.read_u30()
            ns_set_idx = reader.read_u30()
            multinames.append(('', strings[name_idx] if name_idx < len(strings) else ''))
        elif kind in (0x1B, 0x1C):
            ns_set_idx = reader.read_u30()
            multinames.append(('', 'MultinameL'))
        elif kind == 0x1D:
            qname_idx = reader.read_u30()
            param_count = reader.read_u30()
            for _ in range(param_count):
                reader.read_u30()
            multinames.append(multinames[qname_idx] if qname_idx < len(multinames) else ('', 'TypeName'))
        else:
            multinames.append(('', f'Kind_{kind}'))

    return strings, multinames


def resolve_current_game_symbols(brawlhalla_air_path: Optional[str] = None) -> Dict[str, str]:
    """
    Extracts the current live obfuscated symbols for Colors and Hands from BrawlhallaAir.swf.
    """
    air_swf = brawlhalla_air_path or find_brawlhalla_air_swf()
    if not air_swf or not os.path.isfile(air_swf):
        return {
            "color_class": "_-V4w",
            "color_vector": "_-S5J",
            "color_array": "_-6y",
            "customart_suffix": "_-O3M"
        }

    try:
        stat = os.stat(air_swf)
        cache_key = f"{air_swf}_{stat.st_mtime}_{stat.st_size}"
        if cache_key in _SYMBOLS_CACHE:
            return _SYMBOLS_CACHE[cache_key]
    except Exception:
        cache_key = ""

    result = {
        "color_class": "_-V4w",
        "color_vector": "_-S5J",
        "color_array": "_-6y",
        "customart_suffix": "_-O3M"
    }

    # 1. Advanced AST/Bytecode symbol resolver
    try:
        from .brawlhalla_symbol_resolver import resolve_brawlhalla_symbols
        sym = resolve_brawlhalla_symbols(os.path.dirname(air_swf) if os.path.isfile(air_swf) else None)
        if sym:
            if sym.get("color_scheme_classes"):
                result["color_class"] = sym["color_scheme_classes"][0]
            if sym.get("color_scheme_colors_arrays"):
                result["color_vector"] = sym["color_scheme_colors_arrays"][0]
                result["color_array"] = sym["color_scheme_colors_arrays"][-1]
            if sym.get("custom_art_hand_props"):
                result["customart_suffix"] = sym["custom_art_hand_props"][0]
            if cache_key:
                _SYMBOLS_CACHE[cache_key] = result
            return result
    except Exception as e:
        print(f"[SymbolResolver] Advanced resolver exception: {e}")

    try:
        with open(air_swf, "rb") as f:
            swf_bytes = f.read()

        abc_blocks = _extract_abc_blocks_from_swf(swf_bytes)
        for abc in abc_blocks:
            strings, multinames = extract_strings_and_multinames(abc)
            str_set = set(strings)

            # Check if this ABC block contains ColorScheme constants
            if "NO_COLOR_SCHEME" in str_set:
                obf_candidates = [s for s in strings if re.match(r'^_-[A-Za-z0-9]{2,5}$', s)]
                if obf_candidates:
                    result["color_class"] = obf_candidates[0]
                    if len(obf_candidates) > 1:
                        result["color_vector"] = obf_candidates[1]
                    if len(obf_candidates) > 2:
                        result["color_array"] = obf_candidates[2]

            # Check for CustomArt symbol suffix
            if "CustomArt" in str_set:
                for s in strings:
                    if re.match(r'^_-[A-Za-z0-9]{2,5}$', s) and s != result.get("color_class"):
                        result["customart_suffix"] = s
                        break

        if cache_key:
            _SYMBOLS_CACHE[cache_key] = result

    except Exception as e:
        print(f"[SymbolResolver] Error resolving symbols from {air_swf}: {e}")

    return result


def relink_pcode_text(pcode_text: str, new_cls: str, new_vec: str, new_arr: str, new_customart_suffix: Optional[str] = None) -> Tuple[str, int]:
    """
    Applies the exact BrawlForge relinking replacements to decompiled pcode/ActionScript text.
    """
    text = pcode_text
    total = 0

    # 1. ColorSwapClass (header pushstring)
    text, n = re.subn(
        r'(pushstring\s+")([^"]*)(")',
        lambda m: m.group(1) + new_cls + m.group(3),
        text,
        count=1
    )
    total += n

    # 2. ColorSwapVector (header getproperty)
    text, n = re.subn(
        r'(getlocal 5\s*\n\s*getproperty QName\(PackageNamespace\("","4"\),")([^"]*)("\))',
        lambda m: m.group(1) + new_vec + m.group(3),
        text,
        count=1
    )
    total += n

    # 3. ColorSwapClass (per color block coerce)
    text, n = re.subn(
        r'(getproperty MultinameL\(\[PackageNamespace\("","3"\)\]\)\s*\n\s*'
        r'coerce QName\(PackageNamespace\("","4"\),")([^"]*)("\)\s*\n\s*setlocal 13)',
        lambda m: m.group(1) + new_cls + m.group(3),
        text
    )
    total += n

    # 4. ColorSwapArray (per color block initproperty)
    text, n = re.subn(
        r'(coerce QName\(PackageNamespace\("","4"\),"Array"\)\s*\n\s*'
        r'initproperty QName\(PackageNamespace\("","4"\),")([^"]*)("\))',
        lambda m: m.group(1) + new_arr + m.group(3),
        text
    )
    total += n

    # 5. CustomArt suffix property in hand blocks
    if new_customart_suffix:
        text, n = re.subn(
            r'(initproperty QName\(PackageNamespace\("","4"\),")(_-[A-Za-z0-9]{2,5})("\)\s*\n\s*.*Gfx_Hands)',
            lambda m: m.group(1) + new_customart_suffix + m.group(3),
            text
        )
        total += n

    # 6. ActionScript 3 high-level patterns
    if new_cls:
        text, n = re.subn(r'(\bColorSchemeType\.)(_-[A-Za-z0-9]{2,5})\b', rf'\g<1>{new_cls}', text)
        total += n
    if new_customart_suffix:
        text, n = re.subn(r'(\bcustomArt\.)(_-[A-Za-z0-9]{2,5})\b', rf'\g<1>{new_customart_suffix}', text)
        total += n

    return text, total


def _relink_swf_file(swf_path: str, new_cls: str, new_vec: str, new_arr: str, new_suffix: str) -> int:
    """Relinks MetadataTag JSON inside a .bmod SWF file directly in pure Python."""
    with open(swf_path, "rb") as f:
        swf_bytes = f.read()

    sig = swf_bytes[:3]
    ver = swf_bytes[3]
    if sig == b'CWS':
        body = zlib.decompress(swf_bytes[8:])
    elif sig == b'FWS':
        body = swf_bytes[8:]
    else:
        return 0

    nbits = body[0] >> 3
    rect_bits = 5 + nbits * 4
    rect_bytes = (rect_bits + 7) // 8
    header_end = rect_bytes + 4

    pos = header_end
    out_body = bytearray(body[:header_end])
    total_changes = 0

    while pos < len(body) - 2:
        tag_header = struct.unpack('<H', body[pos:pos+2])[0]
        pos += 2
        tag_code = tag_header >> 6
        tag_len = tag_header & 0x3F
        is_long = (tag_len == 0x3F)
        if is_long:
            tag_len = struct.unpack('<I', body[pos:pos+4])[0]
            pos += 4

        tag_content = body[pos : pos + tag_len]
        pos += tag_len

        if tag_code == 77:  # MetadataTag
            try:
                meta_str = tag_content.rstrip(b'\x00').decode('utf-8')
                meta_json = json.loads(meta_str)

                def recurse_patch(d):
                    nonlocal total_changes
                    if isinstance(d, dict):
                        for k, v in list(d.items()):
                            if isinstance(v, str) and ("pushstring" in v or "QName" in v or "initproperty" in v or "getproperty" in v or "handMap" in v or "colorMap" in v or "paletteMap" in v):
                                updated, n = relink_pcode_text(v, new_cls, new_vec, new_arr, new_suffix)
                                if n > 0:
                                    d[k] = updated
                                    total_changes += n
                            elif isinstance(v, (dict, list)):
                                recurse_patch(v)
                    elif isinstance(d, list):
                        for item in d:
                            recurse_patch(item)

                recurse_patch(meta_json)

                new_meta_bytes = json.dumps(meta_json).encode('utf-8') + b'\x00'
                new_len = len(new_meta_bytes)
                if new_len >= 0x3F:
                    out_body.extend(struct.pack('<H', (77 << 6) | 0x3F))
                    out_body.extend(struct.pack('<I', new_len))
                else:
                    out_body.extend(struct.pack('<H', (77 << 6) | new_len))
                out_body.extend(new_meta_bytes)
                continue
            except Exception as e:
                print(f"[Relinker] Error patching SWF metadata: {e}")

        # Preserve tag as-is
        if is_long or tag_len >= 0x3F:
            out_body.extend(struct.pack('<H', (tag_code << 6) | 0x3F))
            out_body.extend(struct.pack('<I', tag_len))
        else:
            out_body.extend(struct.pack('<H', (tag_code << 6) | tag_len))
        out_body.extend(tag_content)

    # Avoid recompressing and rewriting a potentially huge bmod if no relevant
    # metadata string actually changed.
    if total_changes == 0:
        return 0

    new_file_len = 8 + len(out_body)
    if sig == b'CWS':
        compressed = zlib.compress(bytes(out_body))
        out_swf = b'CWS' + struct.pack('<B', ver) + struct.pack('<I', new_file_len) + compressed
    else:
        out_swf = b'FWS' + struct.pack('<B', ver) + struct.pack('<I', new_file_len) + bytes(out_body)

    with open(swf_path, "wb") as f:
        f.write(out_swf)

    return total_changes


def relink_mod_file(bmod_path: str, bh_air_path: Optional[str] = None) -> Tuple[bool, int, str]:
    """
    Inspects and relinks all ActionScript / pcode / carrier scripts inside a mod folder, .bmod, or zip/7z archive.
    Updates the file in-place and returns (success, changes_count, message).
    """
    if not os.path.exists(bmod_path):
        return False, 0, f"Mod path not found: {bmod_path}"

    symbols = resolve_current_game_symbols(bh_air_path)
    new_cls = symbols.get("color_class", "_-V4w")
    new_vec = symbols.get("color_vector", "_-S5J")
    new_arr = symbols.get("color_array", "_-6y")
    new_suffix = symbols.get("customart_suffix", "_-O3M")

    # 1. Check if mod is a directory
    if os.path.isdir(bmod_path):
        total_changes = 0
        # Update BrawlForgeSuite.as if present in mod folder
        bfs_path = os.path.join(bmod_path, "UI_MainMenu.swf", "scripts", "tier_b", "BrawlForgeSuite.as")
        if os.path.isfile(bfs_path):
            try:
                from ..worker.brawlforge_template import generate_brawlforge_suite_as
                from .brawlhalla_symbol_resolver import resolve_brawlhalla_symbols
                game_dir = os.path.dirname(bh_air_path) if bh_air_path else None
                full_symbols = resolve_brawlhalla_symbols(game_dir)
                new_bfs = generate_brawlforge_suite_as(full_symbols)
                with open(bfs_path, "w", encoding="utf-8") as f:
                    f.write(new_bfs)
                total_changes += 1
            except Exception as bfs_e:
                print(f"[Relinker] Warning updating BrawlForgeSuite.as in mod dir: {bfs_e}")

        for root, _, files in os.walk(bmod_path):
            for file_name in files:
                file_path = Path(root) / file_name
                ext = file_path.suffix.lower()
                if ext in ('.pcode', '.as', '.txt', '.json') and file_path.name != "BrawlForgeSuite.as":
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        updated, n = relink_pcode_text(content, new_cls, new_vec, new_arr, new_suffix)
                        if n > 0:
                            file_path.write_text(updated, encoding='utf-8')
                            total_changes += n
                    except Exception:
                        pass
                elif ext in ('.swf', '.bmod'):
                    try:
                        n = _relink_swf_file(str(file_path), new_cls, new_vec, new_arr, new_suffix)
                        total_changes += n
                    except Exception:
                        pass

        msg = f"Successfully updated {total_changes} identifier(s) in '{os.path.basename(bmod_path)}'."
        return True, total_changes, msg

    # 2. Check if file is a SWF/.bmod
    try:
        with open(bmod_path, "rb") as f:
            header = f.read(3)
        if header in (b'CWS', b'FWS', b'ZWS'):
            # It is a SWF container (.bmod)
            changes = _relink_swf_file(bmod_path, new_cls, new_vec, new_arr, new_suffix)
            msg = f"Successfully updated {changes} identifier(s) in '{os.path.basename(bmod_path)}'."
            return True, changes, msg
    except Exception as e:
        print(f"[Relinker] SWF relink attempt error: {e}")

    # 2. Otherwise, check if it is a 7z or Zip archive
    total_changes = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        is_7z = False
        try:
            import py7zr
            if py7zr.is_7zfile(bmod_path):
                is_7z = True
                with py7zr.SevenZipFile(bmod_path, mode='r') as z:
                    z.extractall(path=extract_dir)
        except Exception:
            is_7z = False

        if not is_7z:
            try:
                with zipfile.ZipFile(bmod_path, 'r') as z:
                    z.extractall(path=extract_dir)
            except Exception:
                return False, 0, f"Unsupported mod format: '{os.path.basename(bmod_path)}'"

        for root, _, files in os.walk(extract_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                ext = file_path.suffix.lower()

                if ext in ('.pcode', '.as', '.txt', '.json'):
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        updated, n = relink_pcode_text(content, new_cls, new_vec, new_arr, new_suffix)
                        if n > 0:
                            file_path.write_text(updated, encoding='utf-8')
                            total_changes += n
                    except Exception:
                        pass
                elif ext in ('.swf', '.bmod'):
                    try:
                        n = _relink_swf_file(str(file_path), new_cls, new_vec, new_arr, new_suffix)
                        total_changes += n
                    except Exception:
                        pass

        # Repack
        backup_path = bmod_path + ".bak"
        try:
            shutil.copy2(bmod_path, backup_path)
            if is_7z:
                import py7zr
                with py7zr.SevenZipFile(bmod_path, mode='w') as z:
                    z.writeall(extract_dir, arcname="")
            else:
                with zipfile.ZipFile(bmod_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                    for root, _, files in os.walk(extract_dir):
                        for file_name in files:
                            abs_file = os.path.join(root, file_name)
                            rel_file = os.path.relpath(abs_file, extract_dir)
                            z.write(abs_file, rel_file)

            if os.path.isfile(backup_path):
                os.remove(backup_path)

        except Exception as e:
            if os.path.isfile(backup_path):
                shutil.move(backup_path, bmod_path)
            return False, 0, f"Failed to repack archive: {e}"

    msg = f"Successfully updated {total_changes} identifier(s) in '{os.path.basename(bmod_path)}'."

    # Also automatically refresh BrawlForgeSuite symbols and patch live game SWF if carrier is present
    try:
        fix_ok, fix_cnt, fix_msg = fix_hand_mod_symbols(bh_air_path)
        if fix_ok:
            total_changes += fix_cnt
            msg += f" | {fix_msg}"
    except Exception as e:
        print(f"[Relinker] Auto-fix symbols notice: {e}", flush=True)

    return True, total_changes, msg


def fix_hand_mod_symbols(bh_dir: Optional[str] = None, ui_mainmenu_path: Optional[str] = None) -> Tuple[bool, int, str]:
    """
    Fix command helper: updates the hardcoded BrawlForgeSuite symbol constants
    to match the current Brawlhalla build.

    Steps:
    1. Find BrawlhallaAir.swf and extract current obfuscated prop names
    2. Save discovered symbols to core/assets/symbols.json
    3. Patch BrawlForgeSuite constants in the live UI_MainMenu.swf immediately (fast)
    4. Rebuild carrier_UI_MainMenu.swf in background (so next install uses new symbols too)

    Returns (success, changes_count, message)
    """
    changes = 0
    messages = []

    # ---- 1. Find BrawlhallaAir.swf ----------------------------------------
    air_swf = find_brawlhalla_air_swf(bh_dir)
    if not air_swf:
        return False, 0, "BrawlhallaAir.swf not found."

    # ---- 2. Extract and save symbols to AppData & local assets -------------
    try:
        from .symbols_manager import resolve_and_update_symbols, get_flat_symbols
        structured = resolve_and_update_symbols(brawlhalla_dir=os.path.dirname(air_swf), force=True, trigger="FixCommand")
        new_symbols = get_flat_symbols()
        changes += 1
        messages.append("symbols.json updated in AppData & local assets")
    except Exception as exc:
        return False, 0, f"Failed to extract symbols: {exc}"

    # ---- 3. Patch live UI_MainMenu.swf immediately -------------------------
    patched_game = False
    try:
        from ..worker.gameswf import GameSwf, _OBF_ANCHOR
        from ..worker.brawlhalla import BRAWLHALLA_PATH

        if ui_mainmenu_path is None and BRAWLHALLA_PATH:
            ui_mainmenu_path = os.path.join(BRAWLHALLA_PATH, "UI_MainMenu.swf")

        if ui_mainmenu_path and os.path.isfile(ui_mainmenu_path):
            game_swf_data = GameSwf(ui_mainmenu_path)
            game_swf_data.open()
            if game_swf_data.gameSwf.getAS3(_OBF_ANCHOR) is not None:
                ok = game_swf_data.patch_brawlforge_symbols(new_symbols)
                if ok:
                    changes += 1
                    patched_game = True
                    messages.append("BrawlForgeSuite patched in game UI_MainMenu.swf")
            game_swf_data.close()
    except Exception as exc:
        messages.append(f"WARNING game patch: {exc}")

    # ---- 4. Rebuild carrier in background ----------------------------------
    try:
        import threading
        from ..worker.brawlforge_template import sync_master_carrier_assets
        def _rebuild():
            try:
                ok = sync_master_carrier_assets()
                if ok:
                    print("[Fix] carrier_UI_MainMenu.swf rebuilt with new symbols in background.", flush=True)
            except Exception as e:
                print(f"[Fix] carrier rebuild notice: {e}", flush=True)
        threading.Thread(target=_rebuild, daemon=True).start()
    except Exception:
        pass

    success = changes > 0
    summary = " | ".join(messages)
    return success, changes, summary
