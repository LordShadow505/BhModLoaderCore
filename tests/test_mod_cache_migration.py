import hashlib
import json
import os
import struct
import tempfile
import unittest
from unittest.mock import patch

from core.worker.mod import ModCache, ModClass


class _HashCache:
    def __init__(self, fingerprint=None, mod_hash=None):
        self.hashes = {}
        if fingerprint is not None:
            self.hashes[fingerprint] = mod_hash
        self.saved = False

    def getHash(self, fingerprint):
        return self.hashes.get(fingerprint)

    def getHashSum(self, mod_hash):
        for fingerprint, cached_hash in self.hashes.items():
            if mod_hash == cached_hash:
                return fingerprint
        return None

    def removeHash(self, fingerprint):
        self.hashes.pop(fingerprint)

    def setHash(self, fingerprint, mod_hash):
        self.hashes[fingerprint] = mod_hash

    def save(self):
        self.saved = True


class _ClosedSwf:
    def __init__(self, path, autoload=False):
        self.path = path

    def isOpen(self):
        return False

    def open(self):
        raise AssertionError("listing a mod must not open it through FFDec")


class ModCacheStartupTests(unittest.TestCase):
    def _write_bmod(self, path, metadata):
        movie_header = b"\x08\x00" + b"\x00\x00\x00\x00"
        payload = json.dumps(metadata).encode("utf-8")
        metadata_tag = struct.pack("<HI", 0x137F, len(payload)) + payload
        body = movie_header + metadata_tag + b"\x00\x00"
        with open(path, "wb") as mod_file:
            mod_file.write(b"FWS\x0f" + struct.pack("<I", 8 + len(body)) + body)

    def _cache(self, mod_hash, fingerprint):
        return {
            "formatVersion": 1,
            "formatType": "cache_mod",
            "gameVersion": "All",
            "name": "Legacy mod",
            "author": "Tester",
            "version": "1.0",
            "description": "",
            "tags": [],
            "previewsIds": {},
            "hash": mod_hash,
            "swfs": {"Gfx_Test.swf": {"scripts": {}, "sounds": [], "sprites": ["a_Test"]}},
            "files": {},
            "hashSum": fingerprint,
            "installed": True,
            "currentVersion": False,
            "modFileExist": True,
        }

    def _embedded(self, mod_hash, name="Embedded mod"):
        data = self._cache(mod_hash, "unused")
        data["formatType"] = "mod"
        data["name"] = name
        for key in ("hashSum", "installed", "currentVersion", "modFileExist"):
            data.pop(key)
        return data

    def test_structurally_complete_pre_revision_cache_is_current(self):
        data = self._cache("abc", "10_20.0")
        self.assertEqual(ModCache.getCacheState(data, "abc", "10_20.0"), "current")

    def test_incomplete_cache_is_invalid(self):
        data = self._cache("abc", "10_20.0")
        data.pop("swfs")
        self.assertEqual(ModCache.getCacheState(data, "abc", "10_20.0"), "invalid")

    def test_startup_reuses_old_cache_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_path = os.path.join(temp_dir, "legacy.bmod")
            with open(mod_path, "wb") as mod_file:
                mod_file.write(b"legacy-mod-placeholder")

            stat = os.stat(mod_path)
            fingerprint = f"{stat.st_size}_{stat.st_mtime}"
            mod_hash = "legacy-hash"
            cache_dir = os.path.join(temp_dir, mod_hash)
            os.mkdir(cache_dir)
            cache_path = os.path.join(cache_dir, "mod.json")
            cache_bytes = json.dumps(self._cache(mod_hash, fingerprint)).encode("utf-8")
            with open(cache_path, "wb") as cache_file:
                cache_file.write(cache_bytes)

            hash_cache = _HashCache(fingerprint, mod_hash)
            with patch("core.worker.mod.Swf", _ClosedSwf):
                mod = ModClass(temp_dir, modPath=mod_path, sharedHashCache=hash_cache)

            self.assertEqual(mod.name, "Legacy mod")
            self.assertTrue(mod.installed)
            self.assertFalse(hash_cache.saved)
            with open(cache_path, "rb") as cache_file:
                self.assertEqual(cache_file.read(), cache_bytes)

    def test_old_sha_index_is_not_hashed_migrated_or_rewritten_at_startup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_path = os.path.join(temp_dir, "very-old.bmod")
            mod_hash = "very-old-hash"
            self._write_bmod(mod_path, self._embedded(mod_hash))
            with open(mod_path, "rb") as mod_file:
                legacy_fingerprint = hashlib.sha256(mod_file.read()).hexdigest()

            cache_dir = os.path.join(temp_dir, mod_hash)
            os.mkdir(cache_dir)
            cache_path = os.path.join(cache_dir, "mod.json")
            cache_bytes = json.dumps(self._cache(mod_hash, legacy_fingerprint)).encode("utf-8")
            with open(cache_path, "wb") as cache_file:
                cache_file.write(cache_bytes)

            hash_cache = _HashCache(legacy_fingerprint, mod_hash)
            original_mapping = dict(hash_cache.hashes)
            with patch("core.worker.mod.Swf", _ClosedSwf), \
                    patch("core.worker.mod.HashFile", create=True, side_effect=AssertionError("must not hash")):
                mod = ModClass(temp_dir, modPath=mod_path, sharedHashCache=hash_cache)

            self.assertEqual(mod.name, "Legacy mod")
            self.assertEqual(hash_cache.hashes, original_mapping)
            self.assertFalse(hash_cache.saved)
            with open(cache_path, "rb") as cache_file:
                self.assertEqual(cache_file.read(), cache_bytes)

    def test_incomplete_cache_uses_embedded_metadata_in_memory_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_path = os.path.join(temp_dir, "incomplete.bmod")
            mod_hash = "incomplete-hash"
            embedded = self._embedded(mod_hash, name="Recovered in memory")
            self._write_bmod(mod_path, embedded)

            stat = os.stat(mod_path)
            fingerprint = f"{stat.st_size}_{stat.st_mtime}"
            invalid_cache = self._cache(mod_hash, fingerprint)
            invalid_cache.pop("swfs")
            cache_dir = os.path.join(temp_dir, mod_hash)
            os.mkdir(cache_dir)
            cache_path = os.path.join(cache_dir, "mod.json")
            cache_bytes = json.dumps(invalid_cache).encode("utf-8")
            with open(cache_path, "wb") as cache_file:
                cache_file.write(cache_bytes)

            hash_cache = _HashCache(fingerprint, mod_hash)
            with patch("core.worker.mod.Swf", _ClosedSwf):
                mod = ModClass(temp_dir, modPath=mod_path, sharedHashCache=hash_cache)

            self.assertEqual(mod.name, "Recovered in memory")
            self.assertTrue(mod.installed)
            self.assertFalse(hash_cache.saved)
            with open(cache_path, "rb") as cache_file:
                self.assertEqual(cache_file.read(), cache_bytes)

    def test_explicit_save_persists_only_the_selected_mod(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_path = os.path.join(temp_dir, "selected.bmod")
            mod_hash = "selected-hash"
            self._write_bmod(mod_path, self._embedded(mod_hash, name="Selected mod"))
            hash_cache = _HashCache()

            with patch("core.worker.mod.Swf", _ClosedSwf):
                mod = ModClass(temp_dir, modPath=mod_path, sharedHashCache=hash_cache)
            self.assertFalse(os.path.exists(os.path.join(temp_dir, mod_hash)))
            self.assertFalse(hash_cache.saved)

            mod.saveCache()

            self.assertTrue(os.path.isfile(os.path.join(temp_dir, mod_hash, "mod.json")))
            self.assertEqual(hash_cache.hashes[mod.hashSum], mod_hash)
            self.assertTrue(hash_cache.saved)

    def test_unreadable_mod_never_falls_back_to_ffdec_during_startup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_path = os.path.join(temp_dir, "damaged.bmod")
            with open(mod_path, "wb") as mod_file:
                mod_file.write(b"not-a-valid-swf")

            with patch("core.worker.mod.Swf", _ClosedSwf):
                with self.assertRaisesRegex(ValueError, "Unable to read embedded metadata"):
                    ModClass(temp_dir, modPath=mod_path, sharedHashCache=_HashCache())


if __name__ == "__main__":
    unittest.main()
