"""
langfiles.py  –  tracks which mod modified which key in which language .bin file.

Stored as JSON in MODLOADER_CACHE_PATH:
  {
    "language.1.bin": {
      "SomeKey": {
        "modHash": "abc123",
        "originalValue": "original text"
      },
      ...
    },
    ...
  }
"""

import os
import json

from .variables import MODLOADER_CACHE_PATH


_LANG_CACHE_FILE = "lang_modifications.json"


class LangFilesClass:
    """Tracks per-key language modifications so multiple mods can patch the same .bin safely."""

    def __init__(self):
        self._path = os.path.join(MODLOADER_CACHE_PATH, _LANG_CACHE_FILE)
        self._data: dict = {}   # {binName: {key: {"modHash": str, "originalValue": str}}}
        self._load()

    # ── persistence ────────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── public API ─────────────────────────────────────────────────────────────

    def record_install(self, bin_name: str, key: str,
                       original_value: str, mod_hash: str):
        """Record that mod_hash changed `key` in `bin_name`.
        If another mod already owns this key we keep the first original value."""
        bin_data = self._data.setdefault(bin_name, {})
        if key not in bin_data:
            bin_data[key] = {"modHash": mod_hash, "originalValue": original_value}
        else:
            # Key already patched by another mod — update owner
            bin_data[key]["modHash"] = mod_hash
        self._save()

    def get_original_value(self, bin_name: str, key: str):
        """Return the original (pre-mod) value for this key, or None."""
        return self._data.get(bin_name, {}).get(key, {}).get("originalValue", None)

    def uninstall_mod(self, mod_hash: str) -> dict:
        """Return {bin_name: {key: original_value}} for all keys owned by mod_hash,
        and remove them from the tracker."""
        to_restore = {}
        for bin_name, keys in self._data.items():
            for key, info in list(keys.items()):
                if info.get("modHash") == mod_hash:
                    to_restore.setdefault(bin_name, {})[key] = info["originalValue"]
                    del keys[key]
        # Clean up empty bins
        for bin_name in list(self._data.keys()):
            if not self._data[bin_name]:
                del self._data[bin_name]
        self._save()
        return to_restore

    def is_key_modified(self, bin_name: str, key: str) -> bool:
        return key in self._data.get(bin_name, {})

    def get_mod_bins(self, mod_hash: str) -> list:
        """Return list of bin names this mod has modified."""
        result = []
        for bin_name, keys in self._data.items():
            if any(info.get("modHash") == mod_hash for info in keys.values()):
                result.append(bin_name)
        return result


LangFiles = LangFilesClass()
