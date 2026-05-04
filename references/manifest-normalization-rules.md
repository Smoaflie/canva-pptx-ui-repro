# Manifest Normalization Rules

This document is a reference spec for authors and implementers of `canva-ui-implementation`.

The goal is to normalize PPT or Canva extraction output into browser-ready layout semantics so downstream Web implementations do less guessing and more direct rendering.

## Scope

This spec applies to:

- single-page manifests extracted from Canva-exported PPTX
- Web targets
- standalone reconstruction output when the user explicitly asks for a dedicated page or artboard
- adaptation work in mature projects where manifest data informs existing UI changes

This spec does not require:

- standalone previews by default
- screenshots by default
- framework components first
- interaction first
- cross-framework abstraction first

For mature project adaptation, the default output should be:

- targeted edits in the existing UI and component system

For dedicated standalone reconstruction only, the first output can be:

- `HTML + CSS + SVG`

The default input should be:

- `PPTX` structure

Optional reference PNG metadata may appear in manifests produced by the extractor, but Web renderers must not use it to rescale extracted layout output or browser geometry.

## Contract

A browser-ready normalized result should satisfy these rules.

The extractor or normalizer owns predictable PPTX-to-browser differences. A renderer must consume the normalized manifest fields and must not independently rediscover coordinate scaling, text metrics, crop math, stroke units, or transform semantics. If a renderer needs data that is not in the manifest, treat it as a manifest contract gap: report the missing data, affected elements, fidelity risk, and proposed fallback, then wait for user confirmation before using that fallback.

The default artifact contract is:

- `manifest.json`: agent/render-friendly browser contract for normal Web reconstruction
- no raw/debug extraction record by default

Renderers should consume `manifest.json`. If extractor debugging needs full OOXML
provenance, generate a deliberately named debug artifact through an explicit
option and keep it outside normal Web reconstruction.

### Page

- `page.outputWidth` and `page.outputHeight` MUST be browser canvas pixels
- `page.coordinateSpace` SHOULD make browser-consumption semantics explicit after normalization
- page background MUST map directly to CSS background output

### Element Box Model

- each element `x / y / width / height` MUST be browser pixels
- `rotation` MUST map directly to browser transform usage
- `zIndex` MUST be preserved

### Graphics

- `fills` MUST carry direct render semantics
- `strokes` MUST carry explicit unit semantics
- `geometry` MUST make it clear whether output is a CSS box shape or SVG-internal geometry
- image fills SHOULD include `browserCrop` when `crop` is present
- CSS box strokes SHOULD include `widthPx`

### Text

- browser-usable font size MUST be available in browser pixels
- browser-usable letter spacing MUST be available in browser pixels
- paragraph `lineSpacing / spaceBefore / spaceAfter` MUST be preserved
- paragraph spacing SHOULD include browser-ready `cssPx` values where possible
- `anchor / autoFit / insets` MUST not be dropped

If a field cannot yet be expressed in direct browser semantics:

- keep the original field
- mark that it is still raw semantics
- do not silently discard it

## Coordinate Normalization

Current extractor output SHOULD use:

- `browserPixels`

Legacy manifests may still use:

- `referencePixels`
- `pptxEmu`

### `browserPixels`

If `page.coordinateSpace = "browserPixels"`:

- `x / y / width / height` MUST already be treated as browser pixels
- the renderer MUST NOT apply extra scaling by default

### `referencePixels`

If `page.coordinateSpace = "referencePixels"`:

- `x / y / width / height` MUST be treated as browser pixels
- the renderer MUST NOT apply extra scaling by default

### `pptxEmu`

If `page.coordinateSpace = "pptxEmu"`:

- the consumer MUST normalize coordinates before rendering

Formula:

- `scaleX = sourceCanvasWidthPxAt96Dpi / pptxWidth`
- `scaleY = sourceCanvasHeightPxAt96Dpi / pptxHeight`
- `xPx = x * scaleX`
- `yPx = y * scaleY`
- `widthPx = width * scaleX`
- `heightPx = height * scaleY`

Equivalent slide shortcut:

- `EMU * 96 / 914400`

### Non-Uniform Risk

If:

- `scaleX !== scaleY`
- or `referenceAspectRatioMismatch` is present

then consumers MUST treat that as extraction or mapping risk, not as a normal frontend tuning pass.

## Image Fill Normalization

### Asset Priority

When `fills[*].type = "image"`:

- consumers MUST prefer `svgSource`
- fall back to `source` only when `svgSource` is absent

### Uncropped Image Fill

When:

- `mode = "stretch"`
- `crop = null`

the browser baseline SHOULD map to:

- outer box uses normalized `x / y / width / height`
- inner image uses `width: 100%`
- inner image uses `height: 100%`
- inner image uses `object-fit: fill`

### Cropped Image Fill

`srcRect` uses OOXML percentage units and should be converted first:

- `leftRatio = crop.left / 100000`
- `topRatio = crop.top / 100000`
- `rightRatio = crop.right / 100000`
- `bottomRatio = crop.bottom / 100000`

Visible ratios:

- `visibleWidthRatio = 1 - leftRatio - rightRatio`
- `visibleHeightRatio = 1 - topRatio - bottomRatio`

Draw size:

- `drawWidth = targetWidth / visibleWidthRatio`
- `drawHeight = targetHeight / visibleHeightRatio`

Offsets:

- `offsetLeft = -drawWidth * leftRatio`
- `offsetTop = -drawHeight * topRatio`

The HTML baseline SHOULD use:

- clipped outer box with `overflow: hidden`
- absolutely positioned inner image
- `browserCrop.drawWidth / drawHeight / offsetLeft / offsetTop` when those fields are present

Consumers MUST NOT reimplement crop conversion when `browserCrop` exists.

## Stroke And Geometry Units

### CSS Box Rendering

If an element renders as a normal HTML or CSS box:

- use `stroke.widthPx`

If `stroke.widthPx` is absent in a legacy manifest:

- `strokeWidthPx = stroke.width * scaleX`

### Custom SVG Rendering

If:

- `geometry.kind = "custom"`
- the element uses `<svg viewBox>` and `<path>`

then these MUST share one coordinate system:

- `path`
- `viewBox`
- `stroke.width`, only when rendering in SVG-internal units

For Web visual parity, renderers SHOULD prefer:

- `stroke.widthPx`
- `vector-effect="non-scaling-stroke"`

This avoids over-thick strokes when Canva custom geometry uses a `viewBox` that
does not scale 1:1 with the element box.

Consumers MUST NOT:

- scale only `stroke.width`
- or scale only `path` while leaving `stroke.width` unadjusted
- reinterpret `geometry.unit = "svgInternal"` as CSS pixels

### Structural Recommendation

The extractor or normalizer SHOULD distinguish:

- outer box units
- SVG internal geometry units

so downstream code does not guess unit semantics.

## Font And Text Metrics

### Font Size

In current browser-ready output, fields such as `fontSizePx` SHOULD already be browser pixels.

Legacy or raw `pptxEmu` manifests may still require conversion.

Browser-ready font size MUST be derived with:

- `textScale = sourceCanvasWidthPxAt96Dpi / pptxWidth`
- `fontSizeBrowserPx = rawFontSizePx * textScale`

Equivalent form:

- `fontSizeBrowserPx = fontSizePt * 96 / 72`

### Letter Spacing

For legacy or raw `pptxEmu` manifests, `letterSpacingPx` follows the same rule:

- in `pptxEmu` mode it MUST be multiplied by `textScale` before browser use

### Naming Risk

If a field is named with a `Px` suffix but is not yet browser-ready in every coordinate space, the schema SHOULD either:

- emit the true browser-ready px field
- or split the field, for example:
  - `fontSizeRaw`
  - `fontSizeBrowserPx`

## Paragraph Spacing

The schema MUST preserve:

- `lineSpacing`
- `spaceBefore`
- `spaceAfter`

### `spcPts`

If spacing uses:

- `type = "spcPts"`

then:

- `points = value / 100`
- `cssPx = points * 96 / 72`

Current manifests SHOULD emit `cssPx` directly. Consumers SHOULD use the emitted value instead of recalculating.

### `spcPct`

If spacing uses:

- `type = "spcPct"`

then it SHOULD be interpreted as a relative multiplier, not absolute pixels.

Consumers MUST NOT write `spcPct` directly into CSS pixels.

## Text Box And Text Placement

Text box `height` is layout area, not text content height.

Consumers SHOULD render text in two layers:

1. outer text box
   - consumes `x / y / width / height`
   - handles clipping, anchor, padding
2. inner content
   - handles font metrics, letter spacing, line height, paragraph spacing

### High-Sensitivity Text

These cases SHOULD be treated as high-sensitivity text:

- single-line badge numbers
- icon-adjacent numbers
- tightly packed single-line labels
- `autoFit = "spAutoFit"` regions

For those cases, the browser baseline SHOULD escalate to:

- SVG `<text>`
- or another explicitly baseline-controlled strategy

instead of ordinary HTML line boxes.

When the manifest provides `text.renderHints.dominantBaseline`, consumers SHOULD
apply it together with `text.renderHints.baselineY`. For single-line Canva
auto-fit text, `central` is usually a better visual-center contract than
`alphabetic`.

## Workflow

For dedicated standalone Web reconstruction, the first baseline SHOULD be:

- `manifest -> normalized browser manifest -> static HTML/CSS/SVG preview`

For mature project adaptation, the workflow SHOULD be:

- `manifest -> map Canva regions to existing components -> targeted UI edits`

not:

- framework component abstraction first
- standalone preview generation by default

Recommended order:

1. extract manifest
2. normalize manifest for browser semantics
3. if adapting a mature project, map regions to existing components and edit in place
4. if building a dedicated standalone reconstruction, generate static `HTML + CSS + SVG`
5. only when the user explicitly asks for visual review, capture the target container as an output artifact
6. only when the implementation still fails in unexplained ways, go back to extractor or renderer logic

## Validation

### Screenshot Scope

If the user explicitly asked for visual review and a target container exists:

- screenshots MUST use that container as the primary artifact

### Clean Inputs

When humans or agents review parity, they SHOULD compare:

- PPTX-derived manifest expectations
- current candidate output

and avoid mixing in old failed screenshots as if they were acceptance inputs.

### Severity Labels

Visual review SHOULD label severity explicitly, for example:

- `obvious mismatch`
- `visible but maybe acceptable`
- `minor difference`

## Anti-Patterns

These are high-risk mistakes:

- re-normalizing fields that are already browser-ready in the manifest
- treating `fontSizePx` as direct browser pixels in `pptxEmu`
- recalculating image crop when `browserCrop` is present
- recalculating CSS stroke width when `stroke.widthPx` is present
- scaling only `stroke.width` inside custom SVG output
- dropping `lineSpacing / spaceBefore / spaceAfter`
- forcing all sensitive text into ordinary HTML flow
- using whole-page screenshots as primary acceptance when a target container already exists
- treating an optional reference PNG as a layout scaling input
- continuing blind frontend tuning after `referenceAspectRatioMismatch`

## Acceptance Checklist

This spec is being followed when:

- `pptxEmu` boxes can be normalized into browser pixels without guessing
- image crop behavior is documented and reproducible
- custom SVG strokes do not disappear from unit drift
- text schema preserves paragraph spacing semantics
- renderers consume normalized fields instead of repeating extractor normalization
- standalone previews and screenshots are created only when explicitly requested

## Manifest Readability

The extractor SHOULD reduce manifest noise before writing output:

- include a compact top-level `summary`
- include separate summary fields for top-level elements, renderable elements, and groups
- avoid raw/debug extraction detail in normal output; generate it only through an explicit debug option
- do not copy raster fallbacks when an SVG blip is available and preferred
- omit invisible empty text boxes
- prefer `geometry.paths[*].d`; keep `commands` only when no SVG path string can be emitted

## Hard Fields

For Web reconstruction, consumers MUST treat these fields as authoritative:

- `fallbackRasterSkipped`: render `svgSource` and do not search for a skipped raster fallback asset
- `text.renderHints.baselineY` and `text.renderHints.dominantBaseline`: apply both for baseline-sensitive single-line SVG text
- `stroke.widthPx`: use this browser-pixel stroke width instead of recalculating from raw PPTX stroke units
