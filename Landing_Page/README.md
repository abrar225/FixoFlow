# Fixo Flow marketing site

Next.js static export using the approved Flow Fold identity, Geist, Lucide,
Radix Accordion and GSAP. The native product UI uses the same identity/palette.

```sh
npm ci
npm run lint
npm run build
npm run audit:copy
```

Stage current installers from the product root before building the site:

```sh
python3 scripts/stage_website_downloads.py
```

The generated release manifest controls the three operating-system choices.
Missing packages have no download link. Windows/Linux are labeled previews;
physical-device acceptance and signing requirements still apply. The `public`
download directory and exported `out` directory are build outputs, not Git files.
Publish the complete export including its staged installers. This task does not
deploy the site or create a public GitHub release.

Legacy static HTML/Astro implementations and retired logo comparisons were
removed. Flow Fold is the single current identity. See the product release
runbook for platform requirements, validation scope and release gates.
