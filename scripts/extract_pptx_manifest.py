#!/usr/bin/env python3
import argparse
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from pptx_manifest_style import fill_list, notes_for, parse_text, stroke_list, text_render_hints, theme_colors_from_archive
from pptx_manifest_shape import browser_crop, parse_geometry, parse_image_fill
from pptx_manifest_package import copy_asset, copy_font_asset, parse_rels, read_png_size, resolve_target
from pptx_manifest_model import NS, child_context, cnvpr, compose_transform, element_base, is_visible, manifest_summary, rel_attr, scaled_geometry


def embedded_fonts(presentation, presentation_rels, archive, assets_dir, seen_assets):
    fonts = []
    for embedded in presentation.findall("p:embeddedFontLst/p:embeddedFont", NS):
        font = embedded.find("p:font", NS)
        family = font.attrib.get("typeface") if font is not None else None
        if not family:
            continue
        for style in ("regular", "bold", "italic", "boldItalic"):
            style_node = embedded.find(f"p:{style}", NS)
            rel_id = style_node.attrib.get(rel_attr("id")) if style_node is not None else None
            if not rel_id or rel_id not in presentation_rels:
                continue
            target = resolve_target("ppt/presentation.xml", presentation_rels[rel_id])
            info = copy_font_asset(archive, target, family, style, assets_dir, seen_assets)
            if info is not None:
                fonts.append(info)
    return fonts


def shape_element(node, ctx, page, slide_path, rels, archive, assets_dir, seen_assets, theme_colors, counter):
    meta = cnvpr(node, "p:nvSpPr/p:cNvPr")
    sp_pr = node.find("p:spPr", NS)
    xfrm = sp_pr.find("a:xfrm", NS) if sp_pr is not None else None
    box, rotation = scaled_geometry(ctx, page, xfrm)
    tx_body = node.find("p:txBody", NS)
    image_fill = parse_image_fill(sp_pr, slide_path, rels, lambda target: copy_asset(archive, target, assets_dir, seen_assets))
    fills = fill_list(sp_pr, theme_colors)
    if image_fill is not None:
        fills.append(image_fill)
    if image_fill is not None and image_fill.get("crop") is not None:
        image_fill["browserCrop"] = browser_crop(image_fill["crop"], box[2], box[3])
    element = element_base(meta, "text" if tx_body is not None else "shape", counter, box, rotation, compose_transform(ctx, xfrm), fills, stroke_list(sp_pr, theme_colors, page["scaleX"]), notes_for(sp_pr))
    element["geometry"] = parse_geometry(sp_pr)
    if tx_body is not None:
        element["text"] = parse_text(tx_body, theme_colors, page["scaleX"], page["scaleY"], page["typographyScale"])
        element["text"]["renderHints"] = text_render_hints(element["text"], box)
    return element


def picture_element(node, ctx, page, slide_path, rels, archive, assets_dir, seen_assets, counter):
    meta = cnvpr(node, "p:nvPicPr/p:cNvPr")
    sp_pr = node.find("p:spPr", NS)
    xfrm = sp_pr.find("a:xfrm", NS) if sp_pr is not None else None
    box, rotation = scaled_geometry(ctx, page, xfrm)
    blip = node.find("p:blipFill/a:blip", NS)
    embed = blip.attrib.get(rel_attr("embed")) if blip is not None else None
    target = resolve_target(slide_path, rels[embed]) if embed and embed in rels else None
    asset = copy_asset(archive, target, assets_dir, seen_assets) if target else None
    element = element_base(meta, "image", counter, box, rotation, compose_transform(ctx, xfrm), [], stroke_list(sp_pr, {}, page["scaleX"]), notes_for(sp_pr))
    element["image"] = {"source": asset["extractedPath"] if asset else None, "pptxPath": target}
    return element


def group_element(node, ctx, page, slide_path, rels, archive, assets_dir, seen_assets, theme_colors, counter):
    meta = cnvpr(node, "p:nvGrpSpPr/p:cNvPr")
    grp_pr = node.find("p:grpSpPr", NS)
    xfrm = grp_pr.find("a:xfrm", NS) if grp_pr is not None else None
    box, rotation = scaled_geometry(ctx, page, xfrm)
    children = []
    nested_ctx = child_context(ctx, xfrm) if xfrm is not None else ctx
    for child in list(node):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag in {"nvGrpSpPr", "grpSpPr"}:
            continue
        parsed = parse_node(child, nested_ctx, page, slide_path, rels, archive, assets_dir, seen_assets, theme_colors, counter)
        if parsed is not None and is_visible(parsed):
            children.append(parsed)
    element = element_base(meta, "group", counter, box, rotation, compose_transform(ctx, xfrm), [], [], [])
    element["children"] = children
    return element


def parse_node(node, ctx, page, slide_path, rels, archive, assets_dir, seen_assets, theme_colors, counter):
    tag = node.tag.rsplit("}", 1)[-1]
    if tag == "sp":
        return shape_element(node, ctx, page, slide_path, rels, archive, assets_dir, seen_assets, theme_colors, counter)
    if tag == "pic":
        return picture_element(node, ctx, page, slide_path, rels, archive, assets_dir, seen_assets, counter)
    if tag == "grpSp":
        return group_element(node, ctx, page, slide_path, rels, archive, assets_dir, seen_assets, theme_colors, counter)
    return None


def extract_manifest(pptx_path, output_dir, slide_index=1, reference_png=None):
    pptx_path = Path(pptx_path)
    output_dir = Path(output_dir)
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pptx_path) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        size = presentation.find("p:sldSz", NS)
        slide_ids = presentation.findall("p:sldIdLst/p:sldId", NS)
        if not 1 <= slide_index <= len(slide_ids):
            raise IndexError(f"slide_index {slide_index} is out of range for {len(slide_ids)} slide(s)")
        presentation_rels = parse_rels(archive, "ppt/presentation.xml")
        slide_rel_id = slide_ids[slide_index - 1].attrib[rel_attr("id")]
        slide_path = resolve_target("ppt/presentation.xml", presentation_rels[slide_rel_id])
        slide_root = ET.fromstring(archive.read(slide_path))
        source_width_px = float(size.attrib["cx"]) / 914400.0 * 96.0
        source_height_px = float(size.attrib["cy"]) / 914400.0 * 96.0
        reference_width = reference_height = None
        scale_x = source_width_px / float(size.attrib["cx"])
        scale_y = source_height_px / float(size.attrib["cy"])
        if reference_png:
            reference_width, reference_height = read_png_size(reference_png)
        theme_colors = theme_colors_from_archive(archive)
        bg_pr = slide_root.find("p:cSld/p:bg/p:bgPr", NS)
        background_fills = fill_list(bg_pr, theme_colors)
        warnings = []
        if reference_png and max(reference_width / source_width_px, reference_height / source_height_px):
            reference_scale_x = reference_width / source_width_px
            reference_scale_y = reference_height / source_height_px
            if abs(reference_scale_x - reference_scale_y) / max(reference_scale_x, reference_scale_y) > 0.02:
                warnings.append("referenceAspectRatioMismatch")
        page = {
            "name": slide_root.find("p:cSld", NS).attrib.get("name", f"Slide {slide_index}"),
            "pptxWidth": float(size.attrib["cx"]),
            "pptxHeight": float(size.attrib["cy"]),
            "referenceWidth": reference_width,
            "referenceHeight": reference_height,
            "scaleX": scale_x,
            "scaleY": scale_y,
            "sourceCanvasWidthPxAt96Dpi": source_width_px,
            "sourceCanvasHeightPxAt96Dpi": source_height_px,
            "typographyScale": scale_x,
            "coordinateSpace": "browserPixels",
            "outputWidth": source_width_px,
            "outputHeight": source_height_px,
            "background": {"fills": background_fills} if background_fills else None,
            "warnings": warnings,
        }
        rels = parse_rels(archive, slide_path)
        seen_assets = {}
        fonts = embedded_fonts(presentation, presentation_rels, archive, assets_dir, seen_assets)
        handled_font_paths = {font["pptxPath"] for font in fonts}
        for font_target in [name for name in archive.namelist() if name.startswith("ppt/fonts/")]:
            if font_target not in handled_font_paths:
                copy_asset(archive, font_target, assets_dir, seen_assets)
        root_ctx = {"originX": 0.0, "originY": 0.0, "localX": 0.0, "localY": 0.0, "localWidth": float(size.attrib["cx"]), "localHeight": float(size.attrib["cy"]), "scaleX": 1.0, "scaleY": 1.0, "flipH": False, "flipV": False}
        counter = {"value": 0}
        elements = []
        for child in list(slide_root.find("p:cSld/p:spTree", NS)):
            if child.tag.rsplit("}", 1)[-1] in {"nvGrpSpPr", "grpSpPr"}:
                continue
            parsed = parse_node(child, root_ctx, page, slide_path, rels, archive, assets_dir, seen_assets, theme_colors, counter)
            if parsed is not None and is_visible(parsed):
                elements.append(parsed)
    assets = [asset for key, asset in seen_assets.items() if key[0] != "content"]
    unique_assets = list({asset["extractedPath"]: asset for asset in assets}.values())
    manifest = {
        "summary": manifest_summary(page, fonts, unique_assets, elements),
        "page": page,
        "fonts": fonts,
        "assets": unique_assets,
        "elements": elements,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Extract a browser-ready manifest from a Canva-exported PPTX.")
    parser.add_argument("pptx_path", help="Path to the source .pptx file")
    parser.add_argument("--output-dir", required=True, help="Directory for manifest.json and copied assets")
    parser.add_argument("--slide-index", type=int, default=1, help="1-based slide index to extract")
    parser.add_argument("--reference-png", help="Optional reference PNG used only for validation metadata and mismatch warnings")
    args = parser.parse_args()
    manifest = extract_manifest(args.pptx_path, args.output_dir, args.slide_index, args.reference_png)
    print(json.dumps({"manifest": str(Path(args.output_dir) / "manifest.json"), "assetCount": len(manifest["assets"])}, indent=2))


if __name__ == "__main__":
    main()
