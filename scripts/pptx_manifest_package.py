import posixpath
import hashlib
import struct
from pathlib import Path
from xml.etree import ElementTree as ET


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SFNT_HEADERS = {
    b"\x00\x01\x00\x00": ("ttf", "truetype"),
    b"OTTO": ("otf", "opentype"),
    b"true": ("ttf", "truetype"),
}


def read_png_size(path):
    with Path(path).open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Unsupported reference image format: {path}")
        _length = struct.unpack(">I", handle.read(4))[0]
        if handle.read(4) != b"IHDR":
            raise ValueError(f"Missing IHDR chunk in: {path}")
        width, height = struct.unpack(">II", handle.read(8))
    return width, height


def parse_rels(archive, part_path):
    rels_path = posixpath.join(posixpath.dirname(part_path), "_rels", f"{Path(part_path).name}.rels")
    if rels_path not in archive.namelist():
        return {}
    root = ET.fromstring(archive.read(rels_path))
    return {
        rel.attrib["Id"]: rel.attrib.get("Target", "")
        for rel in root.findall(f"{{{REL_NS}}}Relationship")
    }


def resolve_target(base_part, target):
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def _unique_asset_path(assets_dir, filename):
    candidate = assets_dir / filename
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while candidate.exists():
        candidate = assets_dir / f"{stem}-{index}{suffix}"
        index += 1
    return candidate


def _write_asset(data, filename, pptx_path, assets_dir, seen_assets, cache_key):
    if cache_key in seen_assets:
        return seen_assets[cache_key]
    content_key = ("content", hashlib.sha256(data).hexdigest())
    if content_key in seen_assets:
        info = seen_assets[content_key]
        seen_assets[cache_key] = info
        return info
    assets_dir.mkdir(parents=True, exist_ok=True)
    candidate = _unique_asset_path(assets_dir, filename)
    candidate.write_bytes(data)
    info = {
        "pptxPath": pptx_path,
        "extractedPath": f"assets/{candidate.name}",
    }
    seen_assets[cache_key] = info
    seen_assets[content_key] = info
    return info


def copy_asset(archive, target, assets_dir, seen_assets):
    return _write_asset(
        archive.read(target),
        Path(target).name,
        target,
        assets_dir,
        seen_assets,
        ("asset", target),
    )


def _embedded_font_payload(data):
    if data[:4] in SFNT_HEADERS:
        return data
    if len(data) < 36 or data[34:36] != b"LP":
        return None
    total_size = struct.unpack("<L", data[:4])[0]
    font_size = struct.unpack("<L", data[4:8])[0]
    if font_size <= 0 or total_size < font_size:
        return None
    start = total_size - font_size
    if start < 0 or start + font_size > len(data):
        return None
    payload = data[start : start + font_size]
    return payload if payload[:4] in SFNT_HEADERS else None


def copy_font_asset(archive, target, family, style, assets_dir, seen_assets):
    payload = _embedded_font_payload(archive.read(target))
    if payload is None:
        return None
    extension, font_format = SFNT_HEADERS[payload[:4]]
    asset = _write_asset(
        payload,
        f"{Path(target).stem}.{extension}",
        target,
        assets_dir,
        seen_assets,
        ("font", target),
    )
    return {
        "family": family,
        "style": style,
        "source": asset["extractedPath"],
        "format": font_format,
        "pptxPath": target,
    }
