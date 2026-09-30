"""Small, dependency-free reader for the JSON Metadata tag in a .bmod SWF."""

import json
import io
import lzma
import os
import struct
import zlib
from typing import Optional, Dict, Any


_METADATA_TAG_CODE = 77


def _read_metadata_from_body(body_stream) -> Optional[Dict[str, Any]]:
    first_rect_byte = body_stream.read(1)
    if len(first_rect_byte) != 1:
        return None
    nbits = first_rect_byte[0] >> 3
    rect_size = (5 + (4 * nbits) + 7) // 8
    if len(body_stream.read(max(0, rect_size - 1))) != max(0, rect_size - 1):
        return None
    if len(body_stream.read(4)) != 4:  # FrameRate and FrameCount
        return None

    while True:
        raw_header = body_stream.read(2)
        if len(raw_header) != 2:
            return None
        tag_header = struct.unpack("<H", raw_header)[0]
        tag_code = tag_header >> 6
        tag_length = tag_header & 0x3F
        if tag_length == 0x3F:
            raw_length = body_stream.read(4)
            if len(raw_length) != 4:
                return None
            tag_length = struct.unpack("<I", raw_length)[0]

        if tag_code == _METADATA_TAG_CODE:
            payload = body_stream.read(tag_length)
            if len(payload) != tag_length:
                return None
            metadata = json.loads(payload.rstrip(b"\0").decode("utf-8"))
            return metadata if isinstance(metadata, dict) else None
        if tag_code == 0:  # End tag
            return None
        body_stream.seek(tag_length, os.SEEK_CUR)


def read_swf_metadata(path: str) -> Optional[Dict[str, Any]]:
    """Read a SWF Metadata tag without starting FFDec or the JVM.

    Supports the three SWF compression signatures so startup never needs to
    launch FFDec merely to discover a mod's metadata.
    """
    try:
        with open(path, "rb") as swf_file:
            header = swf_file.read(8)
            if len(header) != 8:
                return None
            signature = header[:3]
            if signature == b"FWS":
                # Seek over large image/sound tags rather than reading the
                # complete mod into memory merely to reach its metadata.
                return _read_metadata_from_body(swf_file)
            if signature == b"CWS":
                body = zlib.decompress(swf_file.read())
                return _read_metadata_from_body(io.BytesIO(body))
            if signature == b"ZWS":
                compressed_length = swf_file.read(4)
                properties = swf_file.read(5)
                if len(compressed_length) != 4 or len(properties) != 5:
                    return None
                prop = properties[0]
                if prop >= 9 * 5 * 5:
                    return None
                lc = prop % 9
                remainder = prop // 9
                lp = remainder % 5
                pb = remainder // 5
                dictionary_size = max(4096, struct.unpack("<I", properties[1:])[0])
                filters = [{
                    "id": lzma.FILTER_LZMA1,
                    "dict_size": dictionary_size,
                    "lc": lc,
                    "lp": lp,
                    "pb": pb,
                }]
                body = lzma.decompress(swf_file.read(), format=lzma.FORMAT_RAW, filters=filters)
                return _read_metadata_from_body(io.BytesIO(body))
            return None
    except (OSError, ValueError, TypeError, UnicodeDecodeError,
            zlib.error, lzma.LZMAError, struct.error):
        return None
