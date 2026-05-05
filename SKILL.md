---
name: canva-ui-implementation
description: Use when Codex needs to implement or adapt UI from a Canva page or Canva export, especially when choosing between manifest-driven reconstruction and minimal edits to an existing UI.
---

# Canva UI Implementation

## Overview

Use this skill when a Canva page is the design reference for UI work.

It supports two modes:

- `reconstruction`: extract a Canva-exported `PPTX` into `manifest.json` plus reusable assets, then rebuild the same screen from that manifest
- `adaptation`: inspect an existing UI and move it toward the Canva reference while preserving the current component tree, design system, and product constraints where appropriate

By default, this skill should go from `PPTX` to layout code directly.

## Tool

Bundled extractor for reconstruction mode or for asset/layout discovery during adaptation:

```powershell
python .\scripts\extract_pptx_manifest.py .\work\input\design.pptx `
  --output-dir .\work\extracted `
  --slide-index 1
```

Reads:

- `design.pptx`

Writes:

- `extracted/manifest.json`
- `extracted/assets/*`

Target output contract:

- `manifest.json` is the agent/render-friendly manifest. It should be compact, browser-ready, and safe to consume directly in Web reconstruction.
- Do not produce or read `manifest.raw.json` in the default workflow. If extractor debugging truly needs full OOXML provenance, generate a deliberately named debug artifact through an explicit option outside normal Web reconstruction.
- Treat `manifest.json` as the complete render contract. If browser-ready data is missing, do not invent hidden normalization logic or change the extractor/schema on your own. Report the missing field, fidelity impact, and proposed fallback, then wait for user confirmation before using that fallback.

Read [manifest-schema.md](references/manifest-schema.md) before generating UI code from extractor output.
For Web implementations that consume manifest data directly, also read [manifest-normalization-rules.md](references/manifest-normalization-rules.md) before writing browser layout code.

## How To Use

1. Check the local environment first.
2. Decide whether the task is `reconstruction` or `adaptation`.
3. In `reconstruction`, run the extractor before writing UI code.
4. In `adaptation`, inspect the existing UI and component boundaries before changing code.
5. Use the workflow for the selected mode; do not silently switch modes mid-run.
6. Use the PPTX-derived manifest as the only layout contract.
7. Pass the manifest coverage gate before writing UI code.
8. Pass the no-substitution gate before replacing PPTX geometry, fills, strokes, text boxes, or extracted assets with ordinary CSS or icon-library equivalents.
9. Do not generate a standalone preview, screenshot, or visual-review artifact by default. In mature projects, implement the change inside the existing UI surface and let the project's normal review path own previewing.
10. Only create preview artifacts when the user explicitly asks for a dedicated reconstruction output, standalone artboard, or visual review.
11. Do not assume every project environment can run a local preview, browser automation, screenshots, or vision inspection. Treat preview capture and vision review as optional follow-up paths, not default requirements.
12. If a needed browser-ready field is missing from the manifest, stop before implementing a guessed fallback. Report: the missing field, affected element IDs, fidelity risk, and the fallback you would use if approved. Wait for user confirmation before proceeding.

Environment rules:

- Prefer existing tools first.
- Ask before installing missing packages.
- Do not assume browser tooling, local preview servers, screenshot tooling, or vision inspection are available.
- Do not create a new `web/`, static preview, or screenshot artifact inside an existing app unless the user explicitly asks for that output.

Scope rules:

- Use `reconstruction` when the job is to build the same Canva page as a dedicated screen or artboard.
- Use `adaptation` when the job is to adjust an existing codebase or screen toward the Canva reference with minimal, intentional edits.
- Do not silently switch from one mode to the other mid-run.

## Mandatory Gates

### Manifest element coverage gate

Before writing UI code from a manifest, list every visible manifest element and assign exactly one handling mode:

| Manifest element | Type/role | Handling mode | Implementation target | Notes |
|---|---|---|---|---|
| `element.id` | background/card/text/icon/etc. | `direct asset` / `SVG geometry` / `CSS equivalent` / `intentionally omitted` | file/component/selector | reason, risk, or user-approved omission |

No table means no UI code. Do not combine multiple visible elements into one vague row unless the manifest itself represents them as a group and each child is already accounted for elsewhere.

Allowed handling modes:

- `direct asset`: copy or reference the extracted asset from `extracted/assets/*`.
- `SVG geometry`: render manifest `geometry`, `fills`, `strokes`, `transform`, and dimensions with SVG or a shape renderer.
- `CSS equivalent`: allowed only after the no-substitution gate below passes.
- `intentionally omitted`: allowed only when the element is invisible, redundant because another manifest element supersedes it, or the user explicitly approves omission.

### No CSS substitute without manifest justification

If a PPTX element has `geometry`, `fills`, or `strokes`, do not replace it with an ordinary CSS card, rounded rectangle, border, shadow, or icon-library primitive unless all of this is stated first:

- Original manifest element `id`.
- Why direct asset or `SVG geometry` rendering cannot be used.
- What fidelity will be lost by the CSS substitute.
- Confirmation from the user to use the substitute.

This gate also applies in adaptation mode. Existing UI constraints may explain a proposed CSS substitute, but they do not remove the need to identify the manifest element and the expected visual loss.

### Text box is a first-class element

Treat every manifest text box as its own renderable element. Do not merely place approximate text into a nearby container. Map, at minimum:

- `x`, `y`, `width`, and `height`
- `text.fontSizePx` or the manifest's browser-ready font size field
- horizontal/vertical alignment when present
- `text.renderHints` for single-line, auto-fit, badge, label, or baseline-sensitive text

If any required text field is missing, report the affected element ID, the visible risk, and the fallback before implementing.

### Extracted asset priority

For cameras, speech bubbles, icons, illustrations, masks, and product-specific visuals present in the PPTX, use copied or referenced extracted assets first. Do not replace them with `lucide`, emoji, CSS art, or another icon library unless the manifest lacks a usable asset or the user explicitly asks for a redesign.

## Reconstruction Workflow

1. Treat `PPTX` as the structural source of truth for layout code generation.
2. Extract one slide into `manifest.json` and assets.
3. Before writing Web layout code, read [manifest-schema.md](references/manifest-schema.md) and [manifest-normalization-rules.md](references/manifest-normalization-rules.md).
4. Read `manifest.summary` first to understand output size, `renderableElementCount`, `topLevelElementCount`, `groupCount`, asset count, font count, and warnings before inspecting the full element tree. `elementCount` remains a backward-compatible alias for flattened visible renderable elements.
5. Create the manifest element coverage table before writing layout code.
6. In Web `reconstruction`, the first implementation must read browser-ready fields from `manifest.json`: `page.outputWidth/outputHeight` define the canvas; each element's `x/y/width/height/zIndex/rotation/transform` drives placement; `fills`, `strokes.widthPx`, `text.*Px`, paragraph spacing `cssPx`, `image.source`, `fills.browserCrop`, `geometry`, and `fonts` drive rendering.
7. Do not recalculate layout, text metrics, crop math, stroke units, or transforms from screenshots, viewport size, raw PPTX values, or subjective visual judgment.
8. For a dedicated standalone reconstruction only, if no renderer exists, create the minimal static baseline first: `HTML + CSS`, with inline `SVG` only when needed for shapes.
9. That standalone static baseline exists only to prove manifest-to-browser rendering semantics; do not add React component splitting, design-system wrappers, state management, complex responsiveness, or visual repair loops in this pass.
10. For standalone reconstruction, move into React/Vite or the existing framework only after the static baseline correctly consumes the manifest. In mature project adaptation, edit the existing framework directly after mapping Canva regions to current components.
11. Build the screen from `elements`, `fonts`, `page.background`, `fills`, `geometry`, and `transform`.
12. For custom SVG strokes, prefer `stroke.widthPx` with `vector-effect="non-scaling-stroke"` unless the manifest explicitly requires SVG-internal stroke units.
13. For single-line `spAutoFit` or tightly packed labels, prefer manifest `text.renderHints.baselineY` with `text.renderHints.dominantBaseline` over ordinary HTML line boxes.
14. When visual review is explicitly requested and the implemented result lives inside a fixed-ratio target canvas or composition container, capture that container artifact only.
15. If visual gaps cannot be explained by manifest elements, extracted assets, or normalized browser semantics, report the unexplained gap and proposed fallback instead of inventing layout.

Web reconstruction hard contract:

- `fallbackRasterSkipped` means an SVG source superseded a raster fallback; render `svgSource`.
- `text.renderHints.baselineY` and `text.renderHints.dominantBaseline` are authoritative for baseline-sensitive single-line SVG text.
- `stroke.widthPx` is authoritative for browser-pixel stroke thickness; do not recompute it from raw PPTX stroke width.

## Adaptation Workflow

1. Inspect the existing codebase before editing.
2. Identify the current screen, component tree, reusable components, tokens, spacing system, and layout constraints.
3. Map Canva regions to the current UI before editing.
4. Extract manifest/assets from `PPTX` when the reference is available, and use that data as evidence for spacing, assets, typography, and visual ownership; do not generate a standalone preview as part of this default path.
5. Create the manifest element coverage table for the Canva-derived visible elements that will affect the adaptation.
6. Preserve the existing component structure and design-system constraints unless the user explicitly wants a rebuilt screen.
7. Make the smallest coherent UI changes that move the current screen toward the Canva reference.
8. Do not force a full absolute-position rebuild unless that is the explicitly chosen strategy.
9. When visual review is explicitly requested, use the platform-appropriate artifact if available; otherwise state that no preview artifact was produced.
10. If visual gaps cannot be explained by component constraints, asset choice, missing extraction data, or the chosen component mapping, revisit the mapping before making more edits.

## Handling Cases

### When fonts are embedded

- Register `manifest.fonts` before rendering text.
- Prefer extracted browser-usable font files over fallback fonts.
- If no usable font is extracted, call out the fidelity risk before claiming parity.
- For single-line auto-fit text, consume `text.renderHints` when present; do not assume the element bottom edge or alphabetic baseline is the browser visual center.

### When a shape uses an image fill

- Prefer the extracted asset first.
- In Web rendering, prefer `svgSource` over `source` when both exist.
- If `fallbackRasterSkipped` is true, do not search for a missing fallback asset; render `svgSource`.
- Do not automatically clip every image-filled shape through SVG geometry.
- If the extracted asset already looks like the final region, render the asset directly.
- Compare the extracted asset's natural aspect ratio with the rendered target box.
- If the ratios diverge materially and no crop or mask explains it, treat that as distortion and do not claim parity.

### When Web rendering semantics still feel ambiguous

- Treat that as a normalization problem before treating it as a framework bug.
- Use [manifest-normalization-rules.md](references/manifest-normalization-rules.md) as the browser contract for coordinates, crop math, stroke units, text metrics, and validation order.
- Prefer normalized fields already present in manifest, such as `fontSizePx`, `letterSpacingPx`, paragraph spacing `cssPx`, `stroke.widthPx`, and `browserCrop`.
- Prefer proving the layout through a minimal static `HTML + CSS + SVG` baseline before adding React or other framework-specific abstractions.

### When text is baseline-sensitive

- Badge counters, icon-adjacent numbers, and tightly packed single-line labels are high-risk for ordinary HTML flow.
- In Web output, escalate those cases to SVG text or another explicitly baseline-controlled strategy when normal HTML line boxes drift.
- When `text.renderHints.baselineY` and `text.renderHints.dominantBaseline` exist, apply both to SVG text inside the element box.
- Check single-line text boxes against `renderHints` before claiming alignment parity.

### When an element carries `transform.flipH` or `transform.flipV`

- Treat those flags as authoritative PPTX transform data.
- Apply them in the renderer instead of guessing from an external image whether an asset should be mirrored.
- For grouped content, assume child coordinates are already resolved into manifest space and `transform` carries the effective flip state.

### When a visible region is missing

- Treat it as an extraction failure.
- Improve the extractor and regenerate the manifest.
- Do not add stickers, icons, textures, or spacing from an external image by eye.

### When an extracted asset exists

- Copy or reference the extracted asset before considering icon libraries or CSS approximations.
- Use asset filenames and manifest element IDs in the coverage table so the mapping is auditable.
- If replacing an asset is unavoidable, pass the no-substitution gate first.

### When the task is to adjust an existing UI rather than rebuild the page

- Stay in `adaptation` mode unless the user explicitly wants a rebuilt screen.
- Inspect the current component tree, spacing system, tokens, and layout constraints before editing.
- Prefer minimal changes that move the current UI toward the Canva reference while keeping the existing structure understandable.
- Use manifest data and extracted assets to inform changes, not to bulldoze the current UI into an unrelated absolute-position artboard.

### When visual review tooling differs by platform

- Only enter this branch when the user explicitly asks for visual review.
- Web UI: choose something like `Playwright` if available, and capture the fixed-ratio canvas or composition container directly.
- If that container screenshot exists, do not also capture a whole-page screenshot.
- Native or mobile UI: choose that platform's own screenshot path.
- If you cannot produce a real review artifact, say so clearly and do not claim visual parity.

## Guardrails

- Do not use an external image as an authoring input.
- Do not proactively start a visual repair loop from an external image.
- Do not silently rebuild from scratch when the task is to adapt an existing UI.
- Do not stay constrained by an existing UI when the user explicitly wants same-screen reconstruction.
- Do not report success without checking whether the output still matches the manifest.
- Do not make renderer code silently re-normalize values that the manifest already provides.
- Do not let a background-heavy page hide subject distortion behind a coarse whole-page screenshot.
- Check the dominant subject's silhouette, width-height proportion, and major negative spaces before claiming parity.
- Do not hide obvious drift behind vague wording like "close enough" without evidence.
- If the result is wrong because the manifest is incomplete, fix the manifest pipeline before polishing the renderer.

## Pre-Final Manifest Checklist

Before the final response, confirm each item against the manifest coverage table or explicitly state why it does not apply:

- Page size and aspect ratio.
- Background.
- Character/hero assets and animation.
- Speech bubbles.
- Card container shapes.
- Card borders and corner radii.
- Card text boxes.
- Icon assets and positions.
- Button shapes and text.
- Scroll regions.
