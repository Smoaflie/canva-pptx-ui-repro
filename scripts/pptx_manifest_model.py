NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def rel_attr(name):
    return f"{{{NS['r']}}}{name}"


def raw_geometry(xfrm):
    attrs = xfrm.attrib if xfrm is not None else {}
    off = xfrm.find("a:off", NS) if xfrm is not None else None
    ext = xfrm.find("a:ext", NS) if xfrm is not None else None
    return (
        float(off.attrib.get("x", "0")) if off is not None else 0.0,
        float(off.attrib.get("y", "0")) if off is not None else 0.0,
        float(ext.attrib.get("cx", "0")) if ext is not None else 0.0,
        float(ext.attrib.get("cy", "0")) if ext is not None else 0.0,
        float(attrs.get("rot", "0")) / 60000.0,
    )


def transform_flags(xfrm):
    attrs = xfrm.attrib if xfrm is not None else {}
    return {"flipH": attrs.get("flipH") in {"1", "true", "True"}, "flipV": attrs.get("flipV") in {"1", "true", "True"}}


def compose_transform(ctx, xfrm):
    flags = transform_flags(xfrm)
    return {"flipH": ctx["flipH"] ^ flags["flipH"], "flipV": ctx["flipV"] ^ flags["flipV"]}


def apply_context(ctx, x, y, width, height):
    local_x, local_y = x - ctx["localX"], y - ctx["localY"]
    if ctx["flipH"]:
        local_x = ctx["localWidth"] - local_x - width
    if ctx["flipV"]:
        local_y = ctx["localHeight"] - local_y - height
    return (
        ctx["originX"] + local_x * ctx["scaleX"],
        ctx["originY"] + local_y * ctx["scaleY"],
        width * ctx["scaleX"],
        height * ctx["scaleY"],
    )


def scale_box(page, x, y, width, height):
    return round(x * page["scaleX"], 3), round(y * page["scaleY"], 3), round(width * page["scaleX"], 3), round(height * page["scaleY"], 3)


def scaled_geometry(ctx, page, xfrm):
    x, y, width, height, rotation = raw_geometry(xfrm)
    return scale_box(page, *apply_context(ctx, x, y, width, height)), rotation


def next_z(counter):
    value = counter["value"]
    counter["value"] += 1
    return value


def cnvpr(node, path):
    meta = node.find(path, NS)
    return meta.attrib if meta is not None else {}


def child_context(ctx, xfrm):
    x, y, width, height, _rot = raw_geometry(xfrm)
    transform = transform_flags(xfrm)
    group_x, group_y, _scaled_w, _scaled_h = apply_context(ctx, x, y, width, height)
    ch_off = xfrm.find("a:chOff", NS) if xfrm is not None else None
    ch_ext = xfrm.find("a:chExt", NS) if xfrm is not None else None
    child_width = float(ch_ext.attrib.get("cx", "0")) if ch_ext is not None else width
    child_height = float(ch_ext.attrib.get("cy", "0")) if ch_ext is not None else height
    return {
        "originX": group_x,
        "originY": group_y,
        "localX": float(ch_off.attrib.get("x", "0")) if ch_off is not None else 0.0,
        "localY": float(ch_off.attrib.get("y", "0")) if ch_off is not None else 0.0,
        "localWidth": child_width,
        "localHeight": child_height,
        "scaleX": ctx["scaleX"] * (width / child_width if child_width else 1.0),
        "scaleY": ctx["scaleY"] * (height / child_height if child_height else 1.0),
        "flipH": ctx["flipH"] ^ transform["flipH"],
        "flipV": ctx["flipV"] ^ transform["flipV"],
    }


def element_base(meta, kind, counter, box, rotation, transform, fills, strokes, notes):
    x, y, width, height = box
    return {
        "id": meta.get("id"),
        "name": meta.get("name"),
        "type": kind,
        "zIndex": next_z(counter),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "rotation": rotation,
        "transform": transform,
        "opacity": 1.0,
        "fills": fills,
        "strokes": strokes,
        "shadow": None,
        "radius": None,
        "notes": notes,
    }


def has_visible_text(element):
    return bool(element.get("text", {}).get("plainText", "").strip())


def is_visible(element):
    if element.get("type") == "group":
        return bool(element.get("children"))
    if has_visible_text(element):
        return True
    if element.get("image", {}).get("source"):
        return True
    fills = element.get("fills") or []
    if any(fill.get("type") == "solid" and fill.get("color") for fill in fills):
        return True
    if any(fill.get("type") == "image" and (fill.get("source") or fill.get("svgSource")) for fill in fills):
        return True
    if element.get("strokes"):
        return True
    return False


def flatten_visible(elements):
    flattened = []
    for element in elements:
        if element.get("type") == "group":
            flattened.extend(flatten_visible(element.get("children", [])))
        elif is_visible(element):
            flattened.append(element)
    return flattened


def count_groups(elements):
    count = 0
    for element in elements:
        if element.get("type") == "group":
            count += 1 + count_groups(element.get("children", []))
    return count


def manifest_summary(page, fonts, assets, elements):
    flat = flatten_visible(elements)
    type_counts = {}
    for element in flat:
        type_counts[element["type"]] = type_counts.get(element["type"], 0) + 1
    return {
        "output": {"width": page["outputWidth"], "height": page["outputHeight"], "coordinateSpace": page["coordinateSpace"]},
        "topLevelElementCount": len(elements),
        "renderableElementCount": len(flat),
        "groupCount": count_groups(elements),
        "elementCount": len(flat),
        "elementTypes": type_counts,
        "assetCount": len(assets),
        "fontCount": len(fonts),
        "warnings": page.get("warnings", []),
    }
