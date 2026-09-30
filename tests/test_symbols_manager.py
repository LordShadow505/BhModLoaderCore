import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.utils import symbols_manager


class SymbolsManagerTests(unittest.TestCase):
    def test_unchanged_air_swf_skips_expensive_resolver(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            air_path = Path(temp_dir) / "BrawlhallaAir.swf"
            air_path.write_bytes(b"test")
            cached = {"meta": {"air_swf_mtime": air_path.stat().st_mtime}}

            with patch.object(symbols_manager, "load_symbols", return_value=cached), \
                    patch(
                        "core.utils.brawlhalla_symbol_resolver.resolve_brawlhalla_symbols",
                        side_effect=AssertionError("resolver must not run for an unchanged SWF"),
                    ):
                result = symbols_manager.resolve_and_update_symbols(temp_dir, force=False)

            self.assertIs(result, cached)


if __name__ == "__main__":
    unittest.main()
