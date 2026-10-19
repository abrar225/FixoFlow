import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

const root = process.cwd();
const required = [
  "app/layout.tsx",
  "app/page.tsx",
  "app/features/page.tsx",
  "app/how-it-works/page.tsx",
  "app/download/page.tsx",
  "app/privacy/page.tsx",
  "app/globals.css",
  "components/brand.tsx",
  "components/voice-demo.tsx",
  "components/navbar.tsx",
  "components/footer.tsx",
  "components/faq-accordion.tsx",
  "components/magicui/blur-fade.tsx",
  "lib/product.ts",
  "components/how-it-works-demo.tsx",
  "components/use-demo-availability.ts",
  "public/images/logo-options/flow-fold.png",
  "lib/releases.generated.json",
  "components/platform-downloads.tsx",
];
for (const file of required)
  assert.ok(
    fs.statSync(path.join(root, file)).size > 0,
    `Missing or empty: ${file}`,
  );
const routes = [
  "",
  "features/",
  "how-it-works/",
  "download/",
  "privacy/",
];
const origin = "https://fixoflow.firehox.com";
assert.ok(fs.readFileSync(path.join(root,"out/robots.txt"),"utf8").includes(`${origin}/sitemap.xml`), "Missing deployed sitemap reference");
const sitemap = fs.readFileSync(path.join(root,"out/sitemap.xml"),"utf8");
for (const route of routes) assert.ok(sitemap.includes(`${origin}/${route}`), `Missing sitemap route ${route}`);
assert.ok(fs.existsSync(path.join(root,"out/.htaccess")), "Hosting configuration missing from export");
const release = JSON.parse(fs.readFileSync(path.join(root,"lib/releases.generated.json"),"utf8"));
for (const platform of release.platforms) {
  if (platform.available) {
    assert.ok([
      `/downloads/${platform.filename}`,
      `https://github.com/abrar225/FixoFlow/releases/download/v${release.version}/${platform.filename}`,
    ].includes(platform.downloadUrl), `Unexpected release URL: ${platform.id}`);
    const installer = path.join(root,"public/downloads",platform.filename);
    assert.equal(fs.statSync(installer).size,platform.bytes,`Stale installer: ${platform.id}`);
    assert.equal(createHash("sha256").update(fs.readFileSync(installer)).digest("hex"),platform.sha256,`Installer digest mismatch: ${platform.id}`);
  } else assert.equal(platform.filename,null,`Unavailable platform has a download: ${platform.id}`);
}
let linksChecked = 0;
for (const route of routes) {
  const file = path.join(root, "out", route, "index.html");
  assert.ok(fs.existsSync(file), `Build the site before auditing: ${file}`);
  const html = fs
    .readFileSync(file, "utf8")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "");
  const text = html.replace(/<[^>]+>/g, " ");
  assert.ok(html.includes(`rel="canonical" href="${origin}/${route}"`), `Wrong canonical /${route}`);
  assert.ok(!html.includes("https://fixoflow.app"), `Retired domain /${route}`);
  assert.ok(text.includes(`v${release.version} preview`), `Wrong app version /${route}`);
  assert.equal(
    (html.match(/<h1\b/g) || []).length,
    1,
    `Expected one h1: /${route}`,
  );
  assert.ok(
    html.includes("/images/logo-options/flow-fold.png"),
    `Selected Flow Fold icon missing: /${route}`,
  );
  assert.ok(!html.includes("/images/icon-master-1024.png"), `Superseded icon on /${route}`);
  assert.ok(
    html.includes("https://github.com/abrar225/FixoFlow"),
    `Project link missing: /${route}`,
  );
  assert.ok(
    !/\b(?:220\s*(?:WPM|words)|380\s*MB|SHA-?256|Measured speed|Real Benchmarks|Install via Terminal)\b/i.test(
      text,
    ),
    `Superseded technical claim on /${route}`,
  );
  for (const [, href] of html.matchAll(/href="(\/[^"?]*|#[^"]+)"/g)) {
    if (href.startsWith("/_next/")) continue;
    const [urlPath, anchor] = href.split("#");
    const target = urlPath
      ? path.join(root, "out", decodeURIComponent(urlPath))
      : file;
    const targetFile =
      fs.existsSync(target) && fs.statSync(target).isDirectory()
        ? path.join(target, "index.html")
        : target;
    assert.ok(
      fs.existsSync(targetFile),
      `Broken local link ${href} on /${route}`,
    );
    if (anchor)
      assert.ok(
        fs.readFileSync(targetFile, "utf8").includes(`id="${anchor}"`),
        `Missing anchor ${href} on /${route}`,
      );
    linksChecked++;
  }
  console.log(`PASS /${route}: heading, branding, copy, and local links`);
}
const downloadHtml = fs.readFileSync(path.join(root, "out/download/index.html"), "utf8").replace(/<!--[\s\S]*?-->/g, "");
assert.ok(downloadHtml.includes(`Fixo Flow ${release.version}`), "Download version missing");
assert.ok(downloadHtml.includes("Multilingual dictation is coming soon"), "Language availability missing");
assert.ok(downloadHtml.includes('id="release-notes"'), "Release notes missing");
assert.ok(!downloadHtml.includes("Fixoflow-0.2.0"), "Superseded installer advertised");
console.log(
  `PASS ${required.length} required files and ${linksChecked} exported links. Download resolves to a nonempty installer.`,
);
console.log("VERDICT: PASS");
