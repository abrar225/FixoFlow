# Private product distribution — 0.3.3

Fixo Flow is privately developed and free for end users. The source repository is
private. First-party website copy, social metadata, navigation, download/help
links and application update copy must not advertise public source access or
direct customers to the repository. The first-party distribution notice is in
`LICENSE`; third-party component/model licenses and attribution remain separate
and are retained. Previously granted licenses for older releases are unchanged.

## Public delivery

The private repository remains an internal build system. Windows and Linux are
built and checked by native CI. Only the verified installer files and static
website export are deployed to Hostinger; source, credentials, user preferences,
dictation history and audio are not part of that upload.

Public installers use versioned same-origin paths under
`https://fixoflow.tech/downloads/`. Private GitHub release assets cannot serve
anonymous users and are no longer a public distribution dependency. The retired
preview-promotion workflow was removed to avoid reviving that path.

The shared app updater now reads the bounded public JSON document at
`https://fixoflow.tech/releases/latest.json`, with no authentication or user
content. Schema 1 requires an integer schema version, a valid semantic version,
`published: true`, a same-product download page URL and text notes. Foreign URLs,
malformed/legacy payloads and unexpected redirects fail closed. The feed exposes
only public product metadata. It is not an automatic installer or signature.

The staging script generates both the website's release manifest and public
update feed from the current product version. It marks the feed published only
when all three platform installers are present. Its existing native trust gate
still rejects missing signature/notarization evidence when requested. Website
copy continues to identify unsigned and unnotarized packages as previews.

After a release is verified, deploy the complete static export including its
installers, `.htaccess` and the `releases/` directory. Never upload the private
source repository as the website. Keep a rollback copy and verify public file
lengths/hashes after extraction. The update feed requests cache revalidation so
normal website caching does not indefinitely hide a new release.

## Existing installations

0.3.2 and earlier were compiled with the old GitHub update endpoint. A website
change cannot rewrite those installed programs, and the repository's privacy
change makes their old endpoint unsuitable for anonymous discovery. Those users
need one manual installation from the website. From 0.3.3 onward, startup/manual
checks use the public website feed. Availability appears inside the app, with a
link to the public download page; native desktop toasts, continuous polling and
signed automatic installation are still not delivered by this change.

## Scope and verification

No speech engine, model size, language availability, recording, dictation
formatting or history behavior changed. Existing local user data was preserved
when the verified 0.3.3 Mac bundle replaced the installed 0.3.2 app.

Runtime source `3ec948077ad74043b4a462f27b04556fe0eec981` passed 228 local tests
(3 native-platform skips), actual Cocoa/WebKit UI checks, portable CI and both
native installer jobs in run `39262018113`. Website origin remains fixoflow.tech.
Post-deployment verification is retained under `dist/proprietary-release/`.
Publisher signing, Apple notarization and physical-device acceptance remain
separate requirements; privately distributed does not mean publicly trusted.

## Published verification — 19 October 2026

Version 0.3.3 is deployed on fixoflow.tech. Anonymous HTTP checks passed for all
five product pages, robots.txt, sitemap.xml and the published update feed. All
three complete public installer downloads matched the staged byte lengths and
SHA-256 hashes. The installed Mac app's manual check displayed “Fixo Flow 0.3.3
is up to date.” The live navigation, download tabs and footer were also inspected
in the browser. Third-party notices remain bundled.

Hostinger's static deployment replaces the document root, including existing
downloads. For this transfer, the small static export was deployed first, then
the exact compiled installers were restored directly from private build storage
and verified on the server. The narrowly scoped authenticated transfer helper
was removed; a subsequent Hostinger file listing confirmed its absence. Cache
was cleared after the installers were restored. Future releases must include the
installers in the complete export, or restore and verify them after the static
deployment before announcing the release. Never assume an existing downloads
directory survives deployment.
