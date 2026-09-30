import json
import lzma
import os
import struct
import tempfile
import unittest
import zlib

from core.swf.metadatareader import read_swf_metadata


def _build_swf(metadata, compressed=False):
    # Minimal RECT with Nbits=1, then FrameRate and FrameCount.
    movie_header = b"\x08\x00" + b"\x00\x00\x00\x00"
    payload = json.dumps(metadata).encode("utf-8")
    metadata_tag = struct.pack("<HI", 0x137F, len(payload)) + payload
    body = movie_header + metadata_tag + b"\x00\x00"
    signature = b"CWS" if compressed else b"FWS"
    stored_body = zlib.compress(body) if compressed else body
    return signature + b"\x0f" + struct.pack("<I", 8 + len(body)) + stored_body


class SwfMetadataReaderTests(unittest.TestCase):
    def _read(self, compressed):
        expected = {
            "formatVersion": 1,
            "formatType": "mod",
            "name": "Legacy mod",
            "hash": "abc",
            "swfs": {},
            "files": {},
            "previewsIds": {},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "test.bmod")
            with open(path, "wb") as swf_file:
                swf_file.write(_build_swf(expected, compressed=compressed))
            self.assertEqual(read_swf_metadata(path), expected)

    def test_reads_uncompressed_fws_metadata(self):
        self._read(compressed=False)

    def test_reads_zlib_compressed_cws_metadata(self):
        self._read(compressed=True)

    def test_reads_lzma_compressed_zws_metadata(self):
        expected = {
            "formatVersion": 1,
            "formatType": "mod",
            "name": "LZMA mod",
            "hash": "zws-test",
            "swfs": {},
            "files": {},
            "previewsIds": {},
        }
        fws = _build_swf(expected)
        body = fws[8:]
        filters = [{"id": lzma.FILTER_LZMA1, "dict_size": 1 << 20,
                    "lc": 3, "lp": 0, "pb": 2}]
        compressed = lzma.compress(body, format=lzma.FORMAT_RAW, filters=filters)
        properties = bytes([(2 * 5 + 0) * 9 + 3]) + struct.pack("<I", 1 << 20)
        zws = (b"ZWS\x0f" + struct.pack("<I", len(fws)) +
               struct.pack("<I", len(properties) + len(compressed)) +
               properties + compressed)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "test-zws.bmod")
            with open(path, "wb") as swf_file:
                swf_file.write(zws)
            self.assertEqual(read_swf_metadata(path), expected)

    def test_rejects_invalid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".bmod") as mod_file:
            mod_file.write(b"not-a-swf")
            mod_file.flush()
            self.assertIsNone(read_swf_metadata(mod_file.name))


if __name__ == "__main__":
    unittest.main()
