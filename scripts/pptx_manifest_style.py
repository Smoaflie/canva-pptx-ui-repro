from xml.etree import ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
EMU_PER_POINT = 12700


def q(prefix, name):
    return f"{{{NS[prefix]}}}{name}"


def theme_colors_from_archive(archive):
    theme_path = next((name for name in archive.namelist() if name.startswith("ppt/theme/") and name.endswith(".xml")), None)
    if not theme_path:
        return {}
    root = ET.fromstring(archive.read(theme_path))
    scheme = root.find(".//a:clrScheme", NS)
    if scheme is None:
        return {}
    colors = {}
    for child in list(scheme):
        srgb = child.find("a:srgbClr", NS)
        if srgb is not None and srgb.attrib.get("val"):
            colors[child.tag.rsplit("}", 1)[-1]] = f"#{srgb.attrib['val'].upper()}"
    return colors


def pick_color(node, theme_colors):
    if node is None:
        return None
    srgb = node.find("a:srgbClr", NS)
    if srgb is not None and srgb.attrib.get("val"):
        return f"#{srgb.attrib['val'].upper()}"
    scheme = node.find("a:schemeClr", NS)
    if scheme is not None and scheme.attrib.get("val"):
        name = scheme.attrib["val"]
        return theme_colors.get(name, f"theme:{name}")
    return None


def fill_list(sp_pr, theme_colors):
    solid = sp_pr.find("a:solidFill", NS) if sp_pr is not None else None
    color = pick_color(solid, theme_colors)
    return [{"type": "solid", "color": color}] if color else []


def stroke_list(sp_pr, theme_colors, scale_x=1.0):
    line = sp_pr.find("a:ln", NS) if sp_pr is not None else None
    if line is None:
        return []
    solid = line.find("a:solidFill", NS)
    color = pick_color(solid, theme_colors)
    width = float(line.attrib.get("w", "0"))
    return [{"type": "solid", "color": color, "width": width, "unit": "pptxEmu", "widthPx": round(width * scale_x, 3)}] if color else []


def notes_for(sp_pr):
    effect_list = sp_pr.find("a:effectLst", NS) if sp_pr is not None else None
    if effect_list is None:
        return []
    return [child.tag.rsplit("}", 1)[-1] for child in list(effect_list)]


def run_color(run_props, theme_colors):
    solid = run_props.find("a:solidFill", NS) if run_props is not None else None
    return pick_color(solid, theme_colors)


def run_font(run_props):
    for tag in ("latin", "ea", "cs"):
        node = run_props.find(f"a:{tag}", NS) if run_props is not None else None
        if node is not None and node.attrib.get("typeface"):
            return node.attrib["typeface"]
    return None


def paragraph_line_spacing(paragraph_props):
    if paragraph_props is None:
        return None
    spacing = paragraph_props.find("a:lnSpc", NS)
    return spacing_value(spacing)


def spacing_value(node):
    if node is None or not list(node):
        return None
    child = list(node)[0]
    kind = child.tag.rsplit("}", 1)[-1]
    value = float(child.attrib.get("val", "0"))
    result = {"type": kind, "value": value}
    if kind == "spcPts":
        result["cssPx"] = round(value / 100 * 96 / 72, 3)
    return result


def body_layout(body_pr, scale_x, scale_y):
    if body_pr is None:
        return None
    auto_fit = next((child.tag.rsplit("}", 1)[-1] for child in list(body_pr)), None)
    return {
        "anchor": body_pr.attrib.get("anchor"),
        "autoFit": auto_fit,
        "insets": {
            "top": round(float(body_pr.attrib.get("tIns", "0")) * scale_y, 3),
            "left": round(float(body_pr.attrib.get("lIns", "0")) * scale_x, 3),
            "bottom": round(float(body_pr.attrib.get("bIns", "0")) * scale_y, 3),
            "right": round(float(body_pr.attrib.get("rIns", "0")) * scale_x, 3),
        },
    }


def point_pixels(points, typography_scale):
    if points is None:
        return None
    return round(points * typography_scale * EMU_PER_POINT, 3)


def parse_text(tx_body, theme_colors, scale_x=1.0, scale_y=1.0, typography_scale=1.0):
    body_pr = tx_body.find("a:bodyPr", NS)
    paragraphs = []
    plain = []
    for paragraph in tx_body.findall("a:p", NS):
        p_props = paragraph.find("a:pPr", NS)
        runs = []
        chunks = []
        for child in list(paragraph):
            if child.tag == q("a", "r"):
                text = child.findtext("a:t", default="", namespaces=NS)
                run_props = child.find("a:rPr", NS)
                chunks.append(text)
                font_size = float(run_props.attrib["sz"]) / 100 if run_props is not None and run_props.attrib.get("sz") else None
                letter_spacing = float(run_props.attrib["spc"]) if run_props is not None and run_props.attrib.get("spc") else None
                runs.append(
                    {
                        "text": text,
                        "fontFamily": run_font(run_props),
                        "fontSize": font_size,
                        "fontSizePx": point_pixels(font_size, typography_scale),
                        "fontWeight": 700 if run_props is not None and run_props.attrib.get("b") == "1" else 400,
                        "color": run_color(run_props, theme_colors),
                        "letterSpacing": letter_spacing,
                        "letterSpacingPx": point_pixels(letter_spacing / 100, typography_scale) if letter_spacing is not None else None,
                    }
                )
            elif child.tag == q("a", "br"):
                chunks.append("\n")
        paragraph_text = "".join(chunks)
        plain.append(paragraph_text)
        paragraphs.append(
            {
                "text": paragraph_text,
                "alignment": p_props.attrib.get("algn") if p_props is not None else None,
                "lineSpacing": paragraph_line_spacing(p_props),
                "spaceBefore": spacing_value(p_props.find("a:spcBef", NS) if p_props is not None else None),
                "spaceAfter": spacing_value(p_props.find("a:spcAft", NS) if p_props is not None else None),
                "runs": runs,
            }
        )
    return {
        "body": body_layout(body_pr, scale_x, scale_y),
        "plainText": "\n".join(plain),
        "paragraphs": paragraphs,
    }


def text_render_hints(text, box):
    paragraphs = text.get("paragraphs", []) if text else []
    visible_paragraphs = [paragraph for paragraph in paragraphs if paragraph.get("text")]
    single_line = len(visible_paragraphs) == 1 and "\n" not in visible_paragraphs[0].get("text", "")
    body = text.get("body") if text else None
    if not single_line:
        return {"renderMode": "htmlText"}
    return {
        "renderMode": "svgText",
        "baselineY": round(box[3] / 2, 3),
        "dominantBaseline": "central",
        "baselineSource": "singleLineVisualCenter",
        "anchor": body.get("anchor") if body else None,
    }
