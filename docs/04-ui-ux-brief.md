# Fixo Flow product interface

The core Mac application shares the approved marketing identity: Flow Fold,
Geist Sans, lilac, mint, charcoal, and an ivory writing surface. The landing
page is a design reference; it is not a runtime dependency of the application.

## Design tokens

| Role | Value |
| --- | --- |
| Canvas / sidebar | `#eee9fb` |
| Writing surface | `#fffefb` |
| Text / primary button | `#29262f` |
| Secondary text | `#69636f` |
| Mint | `#badbc4` |
| Lilac | `#d7c9f1` |
| Plum / selected controls | `#5d4379` |

Geist is bundled as a variable WOFF2 under `fixoflow/ui/assets/` with its SIL
Open Font License. No remote font or UI dependency is requested. Navigation
uses locally embedded Lucide SVG paths with the ISC license alongside the font.
The chosen, unmodified Flow Fold PNG is the shared hub and floating-bar asset.
`scripts/make_icon.py` converts that source into the standard macOS ICNS sizes.
It does not redraw the mark. The app bundle references `resources/AppIcon.icns`.

## Layout and behavior

The hub opens at 1040 × 740 points, with a minimum outer window of 820 × 620.
A lilac sidebar keeps all six destinations visible. The content scrolls while
the live dictation status and floating-bar control remain at the top.

- **Overview:** expressive heading, branded dictation introduction, a three-step
  guide that follows the configured hold shortcut, local activity totals, five
  recent dictations with date groups and Copy, and apps used. Its primary action reveals the actual nonactivating dictation
  bar, preserving the destination application's cursor.
- **Insights:** mint streak, lilac daily activity, week history, and local
  statistics. Time saved is explicitly an estimate against typing at 40 WPM.
  Empty states invite the first dictation rather than imply recorded activity.
- **Style:** Natural, Concise, Professional, and Verbatim, with one shared spoken
  example. Preview output comes from the real local polisher in Python rather
  than independently authored examples in JavaScript. Changes require Save style.
- **History:** searchable transcripts, readable paragraphs, copy, delete, and
  explicit confirmation before clearing all history. User text is rendered with
  `textContent`, including strings that resemble HTML.
- **Dictionary:** spoken phrase, replacement, and category. Names and everyday
  vocabulary lead the examples; coding terms remain supported.
- **Settings:** switches, two independent shortcut recorders, floating-bar placement, formatting
  modes, model choice, and individual permission cards. Permission labels use
  the macOS adapter's actual states, including `authorized` and `not determined`.
  Preference changes retain the existing backend validation and save behavior.

All data and actions continue through the existing WebKit bridge and SQLite
owners. The redesign does not replace the speech engine, configuration format,
audio retention, clipboard fallback, or shortcut/control coordinator.

## Floating control and motion

The nonactivating glass capsule remains 116 × 30 points at rest, expanding on
hover and for recording, processing, success, and errors. Its tint is lilac,
its text charcoal, and its idle mark Flow Fold. Audio-reactive strokes represent
actual incoming levels; the timer, cancel control, processing lock, and four
snap positions retain their existing behavior.

View changes reveal content over 360 ms. Buttons and switches give short,
contextual feedback; real statistics and charts animate when updated. Refreshed
counts cancel prior count-up work. Reduced motion disables CSS transitions,
entrances, and pulsing, and presents statistics directly. No continuous hero
animation or promotional carousel runs in the product.

Controls have visible keyboard focus. View changes move assistive-technology
focus to the heading; headings suppress the browser's incidental focus outline.
Style and position radio groups support arrow keys, Home, and End with a single
Tab stop for the selected option. Errors name the recovery action. Microphone,
Accessibility, and Input Monitoring each explain their purpose and link to the
corresponding macOS settings.

## Verification on 2026-10-18

- Existing Python suite: 102 passed.
- `scripts/check_product_ui.py`: actual Cocoa/WebKit loading, all six panels,
  local font/logo loading, dictionary write, history search and literal text,
  style preview and keyboard selection, style/settings bridge, permission state
  labels, and minimum-width layout. Uses a temporary database and in-memory
  preferences; does not record, paste, or request permissions.
- Native packaged app inspected for home, style, and settings layout.
- App signed with the existing local identity; signature verified. DMG verified
  and its mounted UI/font/icon contents compared against source.
- Frozen self-check and packaging/inference checks executed outside the source
  checkout in a sanitized environment. Synthetic silence returned a short model
  hallucination; successful inference proves execution, not recognition quality.
- Live microphone capture, real destination insertion, recognition accuracy,
  native reduced-motion preference switching, cold/warm performance, CPU, and
  process-family peak memory were not measured in this design pass.
- Landing-page source/assets were hashed before the work and checked unchanged.

## Windows feasibility

A Windows product is feasible, but the current app cannot be repackaged directly
as an EXE. The installed engine is MLX Whisper with Metal resources; the shell,
floating window, permissions, focus handling, clipboard insertion, and global
shortcut integration use macOS APIs. A Windows build needs a supported local
inference runtime and model format, Windows system/UI adapters, packaging, and
verification on real Windows hardware. Local storage, formatting rules, audio
processing concepts, and most of the HTML design can be reused. No Windows port
is implemented by this Mac redesign.

## Shortcuts and releases follow-up

The timing-based single shortcut has been replaced by separate hold-to-talk and
hands-free bindings. The app owns its Dock policy and icon, and has standard
application/edit menus. Overview and History share a literal-text transcript
renderer and refresh after dictation completes. Version 0.1.0, bounded GitHub
release checks, optional signed Sparkle integration, and the Windows 11 x64
preparation are documented in [the platform and release plan](07-platform-and-release-plan.md).
The real signed-upgrade path and Windows hardware acceptance remain release gates.
