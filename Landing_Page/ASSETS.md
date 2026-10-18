# Design assets and implementation

The website uses Geist Sans, Lucide UI icons, Radix Accordion, GSAP, and a reduced-motion adaptation of Magic UI Blur Fade. The Apple silhouette comes from Simple Icons (CC0); brand marks identify compatibility and do not imply endorsement.

- The user selected option A, Flow Fold. The canonical website icon is `public/images/logo-options/flow-fold.png`; all active site identity is defined in `lib/product.ts`. Retired comparisons were removed after selection. The native app, Dock, Windows icon and installers use the same Flow Fold source.
- [Magic UI Blur Fade](https://magicui.design/r/blur-fade.json) is adapted in `components/magicui/blur-fade.tsx`. The adaptation uses the existing Framer Motion package, respects reduced motion, and keeps its content visible during server rendering.
- [Neutomni](https://neutomni.com/) informed the expressive scale, whitespace, scroll-linked composition, and oversized closing typography. Its shipped page declares GSAP, ScrollTrigger, MorphSVG, SplitText, and Lenis.
- [Santioni Spirits](https://santionispirits.com/) informed the immersive art direction. Its public shipped HTML declares HydraX, custom display fonts, and a dynamically loaded application. Static bundle inspection found tween, interpolation, scroll-trigger, and animation-frame mechanisms. Browser inspection stopped at the age gate, so the full interactive experience was not reproduced or verified.
- [Wispr Flow](https://wisprflow.ai/) and [WisprType](https://wisprtype.com/) informed the use of familiar writing examples. Fixo Flow's capabilities, shortcut, retention, and experimental status are grounded in its own source and README. Competitor performance or capability claims are not carried into this site.

The layout, voice ribbon, writing scenes, and laptop illustration are original HTML/CSS/SVG. Reference sites' proprietary fonts, illustrations, photography, and source code are not redistributed.

## Magic UI license

MIT License

Copyright (c) Magic UI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Logo concepts

Three transparent PNG concepts were originally generated with the built-in image generation tool on 2026-10-18 and copied into `public/images/logo-options/`. They are raster assets, not vector masters. Option A, Flow Fold, is the approved website identity; retired comparisons are not part of the current site.

- A: `flow-fold.png`, Flow Fold.
- B: Voice Loop (retired).
- C: Sound to Script (retired).

### Generation prompt set

Shared brief, used for each concept:

> Use case: logo-brand. Create ONE production-quality standalone app-icon concept for Fixo Flow, a friendly free private Mac voice-to-text companion. Style: expertly art-directed flat vector-like logo, crisp smooth curves, optical balance, strong original silhouette, no gradients, no lighting, no gloss, no 3D, no mockup. Composition: exactly ONE centered charcoal (#29262f) rounded-square macOS-style tile with generous soft corners, occupying 82% of the square canvas, transparent outside the tile. The logo symbol is centered inside with generous breathing room and occupies about 58% of the tile. Palette only charcoal #29262f, ivory #fffefb, soft mint #badbc4, muted lilac #d7c9f1. Symbol must be recognizable in one color and when small. No words, letters as labels, captions, watermarks, comparison board, additional tiles, tiny details, microphone stock icon, or decorative background. This is one of three different logo concepts for the user to choose; do not reproduce any existing brand.

A direction:

> A bold custom F monogram made of two broad softly folded ribbons. An ivory main vertical-to-horizontal folded ribbon and a smaller mint horizontal ribbon create an unmistakable lower-case f / flowing path silhouette. A small precisely positioned mint circle terminates the upper ribbon to suggest a spoken thought reaching its destination. Asymmetric, distinctive and extremely simple. Not three generic parallel wavy lines.

B direction:

> One thick continuous mint ribbon folds into an open rounded speech-loop, with a precise ivory negative-space typing caret in its center. The flowing open loop subtly suggests a lowercase f without becoming a literal letter. One small ivory terminal at the opening. A memorable compact silhouette, calm and confident, recognisable at 24 pixels. No microphone clip art.

C direction:

> A striking custom geometric icon: three rounded ivory vertical voice strokes of different heights bend together to the right into a single mint writing stroke, forming a subtle forward-moving F. Deliberate generous negative space between the strokes, a single lilac accent on the shortest stroke. Looks like sound becoming handwriting, a compact expressive app identity, not an equalizer badge.
