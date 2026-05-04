# Manifest Schema

The render-friendly extractor output writes `manifest.json` with this top-level shape:

```json
{
  "summary": {},
  "page": {},
  "fonts": [],
  "assets": [],
  "elements": []
}
```

Normal Web reconstruction should consume only `manifest.json`; do not require
renderers or agents to scan raw OOXML detail for browser-ready fields.

Default artifact contract:

- `manifest.json`: compact render contract; includes `summary`, visible renderable elements, normalized browser fields, fonts, and assets.
- raw/debug extraction records are not default outputs. If extractor debugging truly needs full OOXML provenance, produce it through an explicit debug option and keep it outside the normal Web reconstruction contract.

## `summary`

First-read surface for agents before expanding the full element tree:

- `output`: browser canvas size and coordinate space
- `topLevelElementCount`: number of entries in top-level `elements`, including visible groups
- `renderableElementCount`: flattened visible non-group element count
- `groupCount`: visible group count across the element tree
- `elementCount`: backward-compatible alias for `renderableElementCount`
- `elementTypes`: flattened visible non-group element counts by type
- `assetCount`, `fontCount`, and `warnings`

## `page`

- `name`: Slide name from the PPTX package when available
- `pptxWidth`, `pptxHeight`: Original slide size in EMU
- `referenceWidth`, `referenceHeight`: optional reference PNG size when a validation image was provided to the extractor
- `scaleX`, `scaleY`: Conversion factors from EMU into browser pixel space derived from the PPT page size itself
- `sourceCanvasWidthPxAt96Dpi`, `sourceCanvasHeightPxAt96Dpi`: what the PPT page size means in a normal 96 DPI slide coordinate system
- `typographyScale`: browser text scale derived from the PPT page size
- `coordinateSpace`: current extractor output uses `browserPixels`
- `outputWidth`, `outputHeight`: Final browser canvas size to target first
- `background`: slide background fills when the PPTX declares them
- `warnings`: extraction-time or optional validation metadata warnings such as `referenceAspectRatioMismatch`

Example:

```json
{
  "sourceCanvasWidthPxAt96Dpi": 1920.0,
  "sourceCanvasHeightPxAt96Dpi": 1080.0,
  "typographyScale": 0.0000652887,
  "background": {
    "fills": [
      { "type": "solid", "color": "#FEF4E0" }
    ]
  },
  "warnings": ["referenceAspectRatioMismatch"]
}
```

The extractor keeps layout output anchored to the PPT page size. Supplying a reference PNG adds metadata and warnings only; it does not rescale element geometry or text metrics.

If `referenceAspectRatioMismatch` is present, do not blindly keep iterating on renderer code. The PPT slide size and optional PNG export no longer describe the same canvas cleanly, so you must first decide whether to re-export, crop, or add an explicit mapping step.

`typographyScale` is the browser text normalization factor emitted by the extractor. Renderers should consume it directly instead of re-deriving browser text size from an optional reference PNG.

Manifest output should absorb predictable PPTX-to-browser differences. Renderers should consume normalized fields from the manifest, not rediscover coordinate, typography, crop, stroke, or transform semantics. If a needed browser field is missing during downstream UI work, the agent should report the missing field, affected elements, fidelity risk, and proposed fallback, then wait for user confirmation before using that fallback.

## `fonts`

Browser-usable embedded fonts are surfaced separately from the raw asset list:

```json
[
  {
    "family": "可画手写风尚-简",
    "style": "regular",
    "source": "assets/font7.ttf",
    "format": "truetype",
    "pptxPath": "ppt/fonts/font7.fntdata"
  }
]
```

Use this mapping to register `@font-face` rules before rendering text.

## `assets`

Each entry describes an extracted media file:

```json
{
  "pptxPath": "ppt/media/image1.png",
  "extractedPath": "assets/image1.png"
}
```

## `elements`

Shared fields:

- `id`
- `name`
- `type`: `text` | `image` | `shape` | `group`
- `zIndex`
- `x`, `y`, `width`, `height`
- `rotation`
- `transform`: cumulative flip metadata in manifest space, for example `{ "flipH": true, "flipV": false }`
- `opacity`
- `fills`
- `strokes`
- `shadow`
- `radius`
- `notes`
- `geometry`: preset or custom vector geometry when available

### `text`

Text elements add:

```json
{
  "text": {
    "body": {
      "anchor": "t",
      "autoFit": "spAutoFit",
      "insets": {
        "top": 0.0,
        "left": 0.0,
        "bottom": 0.0,
        "right": 0.0
      }
    },
    "plainText": "Hello",
    "paragraphs": [
      {
        "text": "Hello",
        "alignment": "ctr",
                "lineSpacing": { "type": "spcPts", "value": 3000.0, "cssPx": 40.0 },
                "spaceBefore": { "type": "spcPts", "value": 100.0, "cssPx": 1.333 },
                "spaceAfter": { "type": "spcPts", "value": 200.0, "cssPx": 2.667 },
        "runs": [
          {
            "text": "Hello",
            "fontFamily": "Aptos",
            "fontSize": 24.0,
            "fontSizePx": 32.0,
            "fontWeight": 700,
            "color": "#112233",
            "letterSpacing": -120.0,
            "letterSpacingPx": -1.6
          }
        ]
      }
    ]
  }
}
```

Text boxes may still carry `geometry` when the PPT element declares a preset shape such as `rect`.

Renderer contract:

- Use `fontSizePx` and `letterSpacingPx` directly for browser text.
- Use `body.insets.*` directly as browser pixels.
- Use `lineSpacing.cssPx`, `spaceBefore.cssPx`, and `spaceAfter.cssPx` when present.
- Use `text.renderHints.baselineY` and `text.renderHints.dominantBaseline` for single-line auto-fit SVG text when present.
- Do not derive CSS text metrics from raw PPT values when normalized fields are present.

### `image`

Image elements add:

```json
{
  "image": {
    "source": "assets/image1.png",
    "pptxPath": "ppt/media/image1.png"
  }
}
```

### `shape`

Shape elements may now include enough information to recreate Canva-exported vector-or-image hybrids:

```json
{
  "geometry": {
    "kind": "custom",
    "unit": "svgInternal",
    "viewBox": {
      "width": 914400.0,
      "height": 914400.0
    },
    "paths": [
      {
        "width": 914400.0,
        "height": 914400.0,
        "d": "M 0.0 0.0 L 914400.0 0.0 L 914400.0 914400.0 L 0.0 914400.0 Z"
      }
    ]
  },
  "fills": [
    {
      "type": "image",
      "source": "assets/image2.png",
      "pptxPath": "ppt/media/image2.png",
      "svgSource": "assets/image3.svg",
      "svgPptxPath": "ppt/media/image3.svg",
      "fallbackRasterSkipped": false,
      "mode": "stretch",
      "crop": {
        "left": 1000,
        "top": 2000,
        "right": 3000,
        "bottom": 4000
      },
      "browserCrop": {
        "leftRatio": 0.01,
        "topRatio": 0.02,
        "rightRatio": 0.03,
        "bottomRatio": 0.04,
        "visibleWidthRatio": 0.96,
        "visibleHeightRatio": 0.94,
        "drawWidth": 100.0,
        "drawHeight": 102.128,
        "offsetLeft": -1.0,
        "offsetTop": -2.043
      },
      "tile": null
    }
  ]
}
```

Interpretation:

- `geometry.kind = "preset"` means the shape came from `a:prstGeom`; use the `preset` name and `adjustments` if present.
- `geometry.kind = "custom"` means the shape came from `a:custGeom`; use `paths[*].d` when present, and `paths[*].commands` only when no SVG path string could be emitted.
- `fills[*].type = "image"` means the element is visually driven by an extracted asset, even if the OOXML node was a shape instead of a picture.
- Prefer `svgSource` over `source` when both are present, because Canva often stores an SVG plus a raster fallback.
- If `fallbackRasterSkipped` is true, the PPTX had a raster fallback but the extractor intentionally did not copy it because `svgSource` is the preferred render asset.
- `crop` is copied from `a:srcRect` and uses OOXML percentage units.
- `browserCrop` is the browser-ready crop contract for clipped image rendering. Use it directly when present instead of recomputing crop math in renderer code.
- `transform.flipH` / `transform.flipV` come from OOXML `a:xfrm` and should be honored by the renderer instead of inferred from the reference PNG.
- `geometry.unit = "svgInternal"` means `paths`, `viewBox`, and SVG stroke handling must share the geometry's internal coordinate system.
- Large unexplained divergence between the extracted image asset ratio and the rendered target box ratio is a validation red flag, especially on background-heavy pages.

### `strokes`

Stroke entries preserve raw PPTX units and expose browser-ready values:

```json
{
  "type": "solid",
  "color": "#445566",
  "width": 12700.0,
  "unit": "pptxEmu",
  "widthPx": 1.333
}
```

Use `widthPx` for CSS box strokes. For custom SVG geometry in Web, prefer `widthPx` with SVG `vector-effect="non-scaling-stroke"` when the goal is browser-pixel visual parity.

### `group`

Group elements add:

```json
{
  "children": []
}
```

Treat child geometry as already resolved into the manifest's declared coordinate space. Child `transform` values are cumulative through parent groups, so a flipped group produces mirrored child coordinates plus the effective flip flags needed by a renderer.

## Supported Scope

The bundled extractor is intentionally narrow:

- slide size
- slide background fill
- embedded font extraction into browser-usable font files when possible
- browser-ready absolute positioning derived from the PPT page size
- browser-ready typography scaling derived from the PPT page size
- browser-ready text metrics such as `fontSizePx`, `letterSpacingPx`, paragraph spacing `cssPx`, and body insets
- browser-ready stroke width for CSS box rendering
- browser-ready single-line text hints such as `text.renderHints.baselineY` and `text.renderHints.dominantBaseline`
- browser-ready crop values for image fill rendering
- text runs, font names, sizes, colors, body anchor, insets, and basic spacing metadata
- raster and SVG image-fill relations
- SVG-preferred image fills where `fallbackRasterSkipped` marks intentionally omitted raster fallback assets
- simple shape fill and stroke colors
- preset and custom shape geometry
- horizontal and vertical flips from `a:xfrm`
- nested groups with scaled or mirrored child coordinates

## Web Reconstruction Hard Contract

These fields are authoritative in `manifest.json`:

- `fills[*].fallbackRasterSkipped`: when true, `svgSource` supersedes a raster fallback. Render `svgSource`; do not look for or recreate the skipped fallback asset.
- `text.renderHints.baselineY` plus `text.renderHints.dominantBaseline`: use both for baseline-sensitive single-line SVG text.
- `strokes[*].widthPx`: use this browser-pixel stroke width for Web output. Do not recompute visual stroke thickness from raw `width`.

## Known Gaps

Expect approximation or manual follow-up for:

- advanced Canva effects
- blend modes
- path-heavy vector shapes with unsupported OOXML commands
- exact crop masks
- full theme inheritance edge cases
- optional PNG-based validation flows beyond the `referenceAspectRatioMismatch` warning

When visual fidelity still matters after extraction, choose a UI-specific screenshot workflow only when the user explicitly asks for that review step and the project environment supports it. The screenshot is an optional output artifact, not a layout input or default skill output.
