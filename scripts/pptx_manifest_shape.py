import posixpath


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def rel_attr(name):
    return f"{{{NS['r']}}}{name}"


def resolve_target(base_part, target):
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def point_data(point):
    return {
        "x": float(point.attrib.get("x", "0")),
        "y": float(point.attrib.get("y", "0")),
    }


def command_data(node):
    tag = node.tag.rsplit("}", 1)[-1]
    points = [point_data(point) for point in list(node)]
    if tag == "moveTo" and points:
        return {"type": "M", **points[0]}
    if tag == "lnTo" and points:
        return {"type": "L", **points[0]}
    if tag == "quadBezTo" and len(points) == 2:
        return {"type": "Q", "x1": points[0]["x"], "y1": points[0]["y"], **points[1]}
    if tag == "cubicBezTo" and len(points) == 3:
        return {
            "type": "C",
            "x1": points[0]["x"],
            "y1": points[0]["y"],
            "x2": points[1]["x"],
            "y2": points[1]["y"],
            **points[2],
        }
    if tag == "arcTo":
        return {
            "type": "A",
            "wR": float(node.attrib.get("wR", "0")),
            "hR": float(node.attrib.get("hR", "0")),
            "startAngle": float(node.attrib.get("stAng", "0")),
            "sweepAngle": float(node.attrib.get("swAng", "0")),
        }
    if tag == "close":
        return {"type": "Z"}
    return None


def svg_path(commands):
    pieces = []
    for command in commands:
        cmd = command["type"]
        if cmd == "M":
            pieces.append(f"M {command['x']} {command['y']}")
        elif cmd == "L":
            pieces.append(f"L {command['x']} {command['y']}")
        elif cmd == "Q":
            pieces.append(f"Q {command['x1']} {command['y1']} {command['x']} {command['y']}")
        elif cmd == "C":
            pieces.append(
                f"C {command['x1']} {command['y1']} {command['x2']} {command['y2']} {command['x']} {command['y']}"
            )
        elif cmd == "Z":
            pieces.append("Z")
        else:
            return None
    return " ".join(pieces) if pieces else None


def parse_geometry(sp_pr):
    preset = sp_pr.find("a:prstGeom", NS) if sp_pr is not None else None
    if preset is not None:
        return {"kind": "preset", "preset": preset.attrib.get("prst"), "adjustments": [dict(item.attrib) for item in preset.findall("a:avLst/a:gd", NS)]}

    custom = sp_pr.find("a:custGeom", NS) if sp_pr is not None else None
    if custom is None:
        return None

    paths = []
    max_width = 0.0
    max_height = 0.0
    for path in custom.findall("a:pathLst/a:path", NS):
        commands = [command for child in list(path) if (command := command_data(child))]
        max_width = max(max_width, float(path.attrib.get("w", "0")))
        max_height = max(max_height, float(path.attrib.get("h", "0")))
        entry = {
            "width": float(path.attrib.get("w", "0")),
            "height": float(path.attrib.get("h", "0")),
        }
        path_d = svg_path(commands)
        if path_d:
            entry["d"] = path_d
        else:
            entry["commands"] = commands
        paths.append(entry)
    return {"kind": "custom", "unit": "svgInternal", "viewBox": {"width": max_width, "height": max_height}, "paths": paths}


def browser_crop(crop, target_width, target_height):
    if crop is None:
        return None
    left_ratio = crop["left"] / 100000
    top_ratio = crop["top"] / 100000
    right_ratio = crop["right"] / 100000
    bottom_ratio = crop["bottom"] / 100000
    visible_width = 1 - left_ratio - right_ratio
    visible_height = 1 - top_ratio - bottom_ratio
    if visible_width <= 0 or visible_height <= 0:
        return {"warning": "invalidCropVisibleArea"}
    draw_width = target_width / visible_width
    draw_height = target_height / visible_height
    return {
        "leftRatio": round(left_ratio, 6),
        "topRatio": round(top_ratio, 6),
        "rightRatio": round(right_ratio, 6),
        "bottomRatio": round(bottom_ratio, 6),
        "visibleWidthRatio": round(visible_width, 6),
        "visibleHeightRatio": round(visible_height, 6),
        "drawWidth": round(draw_width, 3),
        "drawHeight": round(draw_height, 3),
        "offsetLeft": round(-draw_width * left_ratio, 3),
        "offsetTop": round(-draw_height * top_ratio, 3),
    }


def parse_image_fill(sp_pr, slide_path, rels, asset_loader):
    blip_fill = sp_pr.find("a:blipFill", NS) if sp_pr is not None else None
    if blip_fill is None:
        return None

    blip = blip_fill.find("a:blip", NS)
    raster_target = None
    svg_target = None
    if blip is not None:
        embed = blip.attrib.get(rel_attr("embed"))
        if embed and embed in rels:
            raster_target = resolve_target(slide_path, rels[embed])
        svg_blip = blip.find(".//asvg:svgBlip", NS)
        if svg_blip is not None:
            svg_embed = svg_blip.attrib.get(rel_attr("embed"))
            if svg_embed and svg_embed in rels:
                svg_target = resolve_target(slide_path, rels[svg_embed])

    svg_asset = asset_loader(svg_target) if svg_target else None
    raster_asset = asset_loader(raster_target) if raster_target and svg_asset is None else None
    src_rect = blip_fill.find("a:srcRect", NS)
    tile = blip_fill.find("a:tile", NS)
    return {
        "type": "image",
        "source": raster_asset["extractedPath"] if raster_asset else None,
        "pptxPath": raster_target,
        "svgSource": svg_asset["extractedPath"] if svg_asset else None,
        "svgPptxPath": svg_target,
        "fallbackRasterSkipped": bool(raster_target and svg_asset is not None),
        "mode": "tile" if tile is not None else "stretch",
        "crop": (
            {
                "left": int(src_rect.attrib.get("l", "0")),
                "top": int(src_rect.attrib.get("t", "0")),
                "right": int(src_rect.attrib.get("r", "0")),
                "bottom": int(src_rect.attrib.get("b", "0")),
            }
            if src_rect is not None
            else None
        ),
        "tile": dict(tile.attrib) if tile is not None else None,
    }
