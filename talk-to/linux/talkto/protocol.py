"""Tel düzeyi çerçeveleme (PROTOKOL.md, "Çerçeve").

Her çerçeve: 1 bayt tür + 4 bayt uzunluk (big-endian) + gövde.
  'J' (0x4A): gövde UTF-8 JSON nesnesi, "type" alanı zorunlu.
  'B' (0x42): gövde = 4 bayt aktarım no + dosya verisi.
"""

import json
import struct

KIND_JSON = 0x4A
KIND_BINARY = 0x42

MAX_JSON = 4 * 1024 * 1024
MAX_BINARY = 1024 * 1024 + 4
CHUNK = 256 * 1024

_HEAD = struct.Struct(">BI")
_TID = struct.Struct(">I")


class ProtocolError(Exception):
    pass


def encode_json(msg: dict) -> bytes:
    body = json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_JSON:
        raise ProtocolError(f"JSON çerçevesi çok büyük: {len(body)} bayt")
    return _HEAD.pack(KIND_JSON, len(body)) + body


def encode_binary(transfer_id: int, data: bytes) -> bytes:
    if len(data) + 4 > MAX_BINARY:
        raise ProtocolError("ikili parça çok büyük")
    return _HEAD.pack(KIND_BINARY, len(data) + 4) + _TID.pack(transfer_id) + data


async def read_frame(reader):
    """('json', dict) ya da ('binary', (aktarım_no, bytes)) döndürür.

    Bağlantı kapanırsa asyncio.IncompleteReadError fırlar.
    """
    kind, length = _HEAD.unpack(await reader.readexactly(_HEAD.size))
    if kind == KIND_JSON:
        if length > MAX_JSON:
            raise ProtocolError("JSON çerçevesi sınırı aşıyor")
        try:
            msg = json.loads(await reader.readexactly(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ProtocolError(f"bozuk JSON: {e}") from None
        if not isinstance(msg, dict) or not isinstance(msg.get("type"), str):
            raise ProtocolError("JSON çerçevesinde 'type' yok")
        return "json", msg
    if kind == KIND_BINARY:
        if not 4 <= length <= MAX_BINARY:
            raise ProtocolError("ikili çerçeve uzunluğu geçersiz")
        body = await reader.readexactly(length)
        return "binary", (_TID.unpack_from(body)[0], body[4:])
    raise ProtocolError(f"bilinmeyen çerçeve türü: {kind:#x}")
