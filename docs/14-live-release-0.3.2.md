# Fixo Flow 0.3.2 English preview deployment

19 October 2026.

## Published distribution

- Website: https://fixoflow.firehox.com/download/#choose-system
- Versioned installers: https://github.com/abrar225/FixoFlow/releases/tag/v0.3.2
- Runtime source: `9561054bc3329301cef19bfae0eec72c4aabcb46`.
- The Mac app was installed into `/Applications/Fixoflow.app` from the verified
  0.3.2 DMG after confirming the previous application had been removed. Bundle
  signature and offline packaging checks passed. The installed UI showed 0.3.2,
  automatic saving, enabled quiet startup, retained shortcuts, English recognition
  and the multilingual Coming soon notice. Existing local user data was retained.

This is an **English-only preview**, not a trusted stable release. No new language
engine, cloud processing or additional model pack was added. Multilingual and
Roman Hinglish remain accuracy research. The bundled English model is unchanged.

## Release files and platform limits

- Mac: `Fixoflow-0.3.2-macos-arm64.dmg`, 239,213,692 bytes; Apple Silicon,
  macOS 14+. Locally signed, not Apple-notarized.
- Windows: `Fixoflow-0.3.2-windows-x64-setup.exe`, 209,272,127 bytes; Windows 11
  x64 target. Unsigned. Windows 10 22H2 remains a compatibility target requiring
  separate physical-device acceptance. WebView2 and the Visual C++ runtime are
  prerequisites.
- Linux: `Fixoflow-0.3.2-linux-x64.deb`, 265,608,596 bytes; Ubuntu 24.04 x64 X11
  preview. Full Wayland global shortcuts/paste and other distributions are not
  supported by this acceptance evidence.

Installer digests and download URLs are owned by
`Landing_Page/lib/releases.generated.json`. These exact files were retained;
they were not recompiled or replaced during website publication. GitHub marks
`v0.3.2` as a prerelease. Signed automatic installation remains unavailable.
The app's stable-release discovery intentionally does not advertise prereleases.
Users should use the website or the preview release page for this version.

## Deployment approach

The complete 716 MB website export with installers exceeded the Hostinger MCP
client's five-minute call deadline. The old site was inspected after that error;
the new downloads were not reported as published. A separate longer-deadline
attempt was stopped after diagnosing concurrent upload to the same archive.

The successful distribution separates release assets from the website:

1. Windows/Linux artifacts were promoted inside GitHub Actions from successful
   native build `39211980222`, after checking its exact runtime SHA, native
   self-check reports and installer hashes. Promotion run:
   https://github.com/abrar225/FixoFlow/actions/runs/39240195717
2. The verified Mac DMG was uploaded to the same versioned GitHub preview release.
3. The three platform buttons link to those immutable versioned filenames.
   Release uploads intentionally omit `--clobber`; changing bytes requires a
   new version instead of silently replacing installers.
4. A 2,605,726-byte static website export was deployed using Hostinger MCP to
   `fixoflow.firehox.com`, account `u824682847`, then its cache was refreshed.
   This avoids re-uploading hundreds of megabytes for future website edits.

Before replacement, 43 public files totaling 717,184,289 bytes were saved in a
local rollback directory. The CDN transformed one PNG; the rollback manifest
records its served bytes separately from the origin-listed size. This backup
covers the prior public static site, not hidden hosting data or other domains.

To regenerate the download manifest from retained verified files:

```sh
.venv/bin/python scripts/stage_website_downloads.py --artifacts dist/release-0.3.2 --github-release-downloads
```

Build and audit the website before deploying its static output. For a lightweight
Hostinger export, omit the generated `downloads/` directory only when every
available platform has a verified versioned GitHub release URL. Keep `.htaccess`.
The optional `--require-public-trust` gate still rejects missing native signing
and notarization reports; a preview link does not confer public publisher trust.

## Verification

- Existing runtime validation: 226 passed, 3 skipped; real Cocoa/WebKit checks
  passed. Native Windows/Linux packaging and installed-package smoke checks
  passed in the matching source build. These do not establish microphone/input
  acceptance on every physical desktop.
- Publication checks: 22 release-trust/update tests passed; TypeScript checking,
  optimized static export and website audit passed, including 101 exported local
  links and all three locally staged installer digests.
- Seven live HTTP routes passed: home, features, how-it-works, download, privacy,
  robots and sitemap. Main pages displayed version 0.3.2 and did not advertise
  0.2.0 installers. The download page displayed Coming soon and the release URL.
- Browser review verified all three platform selections, their versioned URLs,
  platform requirements and trust notices. A fresh version query avoided an old
  browser-cached page. A screenshot was retained in local release evidence.
- GitHub's release asset digests matched the verified local installers. All three
  installers were then downloaded anonymously in full; their byte lengths and
  SHA-256 digests matched those local files. The complete check passed.

Local deployment records and rollback files are under
`dist/release-evidence-0.3.2/` and are intentionally not committed. Publisher
enrollment/signing, notarization and broader physical-device acceptance remain
required before describing this as a trusted stable launch.

**VERDICT: PASS** for Mac installation, preview publication, live website version
and all three public download identities. Trusted stable distribution and broad
physical-device acceptance are not established by this result.
