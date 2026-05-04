# Canva PPTX UI Repro

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![运行时依赖](https://img.shields.io/badge/runtime%20deps-stdlib%20only-brightgreen)
![输出](https://img.shields.io/badge/output-manifest.json-orange)
![许可证](https://img.shields.io/badge/license-MIT-blue)

> 将 Canva 导出的 PowerPoint 文件提取为适合浏览器重建 UI 的 `manifest.json` 和可复用资源。

Canva PPTX UI Repro 是一个面向 Codex 技能和 UI 复刻流程的提取工具。它读取 Canva 导出的 `.pptx`，提取指定幻灯片，并输出紧凑的 `manifest.json` 与图片、SVG、字体等 assets，供后续 agent 或渲染器直接消费。

语言：[English](README.md) | [简体中文](README.zh-CN.md)

> [!WARNING]
> 本项目由 AI 生成，未经人工优化。在 agent 工作流中可能导致 token 消耗增多，请审阅实现后谨慎使用。

## 功能特性

- **PPTX 到 manifest 提取** - 将 Canva 导出的单页幻灯片转换为结构化 JSON。
- **浏览器坐标输出** - 使用 `browserPixels` 输出布局盒和页面尺寸。
- **资源提取** - 复制被引用的图片、SVG、栅格媒体和可用的嵌入字体。
- **文本归一化** - 保留文本 run、字号、字距、段落间距、内边距和渲染提示。
- **形状支持** - 捕获预设几何、自定义 SVG path、填充、描边、裁剪数据和翻转变换。
- **Agent 友好合约** - 默认以 `manifest.json` 作为重建合约，不要求读取 raw OOXML 调试输出。

## 仓库结构

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── manifest-normalization-rules.md
│   └── manifest-schema.md
└── scripts/
    ├── extract_pptx_manifest.py
    ├── pptx_manifest_model.py
    ├── pptx_manifest_package.py
    ├── pptx_manifest_shape.py
    └── pptx_manifest_style.py
```

## 环境要求

- Python 3.8 或更新版本
- 一个从 Canva 导出的 `.pptx` 文件
- 可选：一张用于校验元数据的参考 `.png` 导出图

提取器只使用 Python 标准库。

## 安装

克隆或复制本仓库后，直接用 Python 运行提取器：

```powershell
cd .\canva-pptx-ui-repro
python .\scripts\extract_pptx_manifest.py --help
```

当前提取器不需要额外安装第三方包。

## 安装为 Codex Skill

本仓库根目录包含 `SKILL.md`，因此整个目录可以作为 Codex skill 安装。把目录放到 `$CODEX_HOME/skills` 下即可。

从本仓库的父目录运行：

```powershell
$skillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills" } else { Join-Path $HOME ".codex\skills" }
$dest = Join-Path $skillsRoot "canva-pptx-ui-repro"
New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Get-ChildItem -Path .\canva-pptx-ui-repro -Force | Copy-Item -Destination $dest -Recurse -Force
```

如果你当前已经在仓库根目录里，可以直接用这个更简单的版本：

```powershell
$skillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills" } else { Join-Path $HOME ".codex\skills" }
$dest = Join-Path $skillsRoot "canva-pptx-ui-repro"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Get-ChildItem -Force | Copy-Item -Destination $dest -Recurse -Force
```

安装后重启 Codex，让新 skill 被发现。之后可以让 Codex 使用 `$canva-ui-implementation`，也可以按 `SKILL.md` 中的 skill 名称 `canva-ui-implementation` 引用它。

## 快速开始

在仓库根目录运行：

```powershell
python .\scripts\extract_pptx_manifest.py .\work\input\design.pptx `
  --output-dir .\work\extracted `
  --slide-index 1
```

命令会写入：

```text
work/
└── extracted/
    ├── manifest.json
    └── assets/
        └── ...
```

示例 CLI 输出：

```json
{
  "manifest": "work/extracted/manifest.json",
  "assetCount": 3
}
```

## 使用方法

### 提取指定幻灯片

`--slide-index` 从 1 开始计数。

```powershell
python .\scripts\extract_pptx_manifest.py .\work\input\deck.pptx `
  --output-dir .\work\slide-2 `
  --slide-index 2
```

### 添加可选 PNG 校验元数据

参考 PNG 只用于生成元数据和不匹配警告，不会重新缩放提取出来的布局。

```powershell
python .\scripts\extract_pptx_manifest.py .\work\input\design.pptx `
  --output-dir .\work\extracted `
  --slide-index 1 `
  --reference-png .\work\input\design.png
```

### 在 UI 实现中消费 manifest

编写渲染器或 UI 实现代码前，请先阅读：

- [Manifest Schema](references/manifest-schema.md)
- [Manifest Normalization Rules](references/manifest-normalization-rules.md)

常规重建路径应只消费 `manifest.json`：

- `page.outputWidth` 和 `page.outputHeight` 定义目标画布。
- 元素的 `x`、`y`、`width`、`height`、`rotation`、`zIndex` 和 `transform` 负责定位。
- `fills`、`strokes.widthPx`、`geometry`、`image.source`、`fills.browserCrop` 和 `fonts` 负责渲染。
- 文本渲染应优先使用归一化后的 `fontSizePx`、`letterSpacingPx`、段落间距 `cssPx` 和可用的 `text.renderHints`。

## Manifest 输出

`manifest.json` 的顶层结构如下：

```json
{
  "summary": {},
  "page": {},
  "fonts": [],
  "assets": [],
  "elements": []
}
```

建议先读取 `summary`，确认输出尺寸、元素数量、资源数量、字体数量和警告，再展开完整元素树。

## 工作流建议

本仓库支持两种 UI 实现模式：

- **重建** - 先提取 Canva PPTX 幻灯片，再根据 manifest 复刻同一屏幕。
- **适配** - 先检查现有 UI，再把提取出的 manifest 作为间距、资源、字体和布局调整的依据。

在重建模式中，PPTX 生成的 manifest 是布局合约。如果缺少某个浏览器可直接使用的字段，应先说明缺失字段和保真风险，再决定是否添加 fallback 逻辑。

## 开发说明

- 默认工作流不会生成 `manifest.raw.json`。
- 如果未来确实需要 raw OOXML 溯源，应通过显式 debug 路径生成。
- 当前脚本按职责拆分为包读取、布局模型、样式解析、形状解析和 CLI 编排。

## 贡献

请让改动聚焦于需要改进的 manifest 合约或提取器行为。更新输出字段时，请同步更新 schema 和 normalization references，确保后续 UI 实现能依据清晰的合约工作。

## 许可证

本项目使用 MIT License。
