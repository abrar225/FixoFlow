# Open-source release — 0.3.4

Fixo Flow is free and open source under the MIT License. The public project is
https://github.com/abrar225/FixoFlow and its production website is
https://fixoflow.tech. This supersedes the temporary private-product notice for
0.3.3; third-party component and speech-model licenses remain in effect.

## Distribution

Native installers are versioned assets on public GitHub Releases. The website
links to those exact assets rather than storing a second installer copy. Only
compiled/verified installers are published; do not rename old binaries as a new
version. Windows and Linux build on native CI; macOS builds locally on Apple
Silicon. Include checksums and the actual build source in release notes.

The bounded public website update feed remains compatible with 0.3.3 clients.
It announces a version and opens the download page, which links to GitHub.
Signed automatic installation is not enabled. Publishing source or a GitHub
release does not grant an Apple Developer ID, notarization, a Microsoft
publisher signature or SmartScreen reputation.

macOS packages are locally signed and unnotarized. Windows setup packages are
unsigned. Treat these as experimental previews. If macOS offers to move a build
to Trash, leave platform protection enabled and report the exact dialog. A
verified local signature is not public Gatekeeper acceptance. Linux currently
targets Ubuntu 24.04 x64/X11; Wayland global inputs are not supported.

## Publishing checklist

1. Run the test suite and relevant native UI/model checks.
2. Build all three packages from the release source. Verify the packaged MIT
   notice, version, native smoke reports and installer formats/hashes.
3. Create a GitHub draft release for `v<version>` and attach the three installers
   plus `SHA256SUMS.txt`. Review notes and asset hashes, then publish it.
4. Run `python scripts/stage_website_downloads.py --artifacts <verified-directory>`.
   It derives GitHub asset links and a compatible website feed; unavailable
   platforms must not get download links.
5. Build/audit the static site and deploy only its exported files to Hostinger.
   Verify anonymous GitHub asset downloads, website copy and update discovery.
6. Keep the default branch, README version, repository homepage and release
   notes aligned. Collect real-device reports without claiming universal support.

## Publication verified — 26 October 2026

The public default branch includes the MIT license, contribution guide and two
screenshots captured from the actual 0.3.4 macOS application. GitHub's repository
homepage points to fixoflow.tech. The obsolete private-transfer draft for 0.3.3
was removed; the earlier public preview is preserved.

All three complete anonymous downloads from the 0.3.4 GitHub release matched the
verified build lengths and SHA-256 values. Windows/Linux native build and
installed UI/model checks passed in run `39393701388`; the hash-gated attachment
workflow passed in run `39397895434`. Local tests passed (228, with 3 skips), and
the native Cocoa/WebKit six-panel checks passed. These results do not establish
physical-device compatibility or public publisher trust.

Hostinger MCP `hosting_deploy` successfully published the static export to
fixoflow.tech on 26 October. All five live product pages were checked for 0.3.4,
MIT wording and public GitHub links, without the superseded proprietary notice.
The compatible JSON update feed announces 0.3.4 and returns cache revalidation
headers. Signed automatic installation remains disabled.

Maintainers can use `publish-verified-preview.yml` to attach Windows/Linux
artifacts server-side: it requires an exact successful native build, matching
draft target, supplied file hashes and passing native UI/inference reports. It
does not publish the draft or overwrite existing assets. Review the complete
release separately before publishing.
