# fixoflow.tech deployment and update status

19 October 2026.

## Website migration

The latest English-only 0.3.2 preview website was deployed through Hostinger MCP
to `fixoflow.tech`, hosting account `u824682847`. Before deployment the website
contained only `default.php`; its served content was backed up locally.

The site origin, canonical/social metadata, sitemap, robots and copy audit now
use `https://fixoflow.tech`. The former subdomain is absent from the generated
site. Mac/Windows/Linux buttons continue to use the verified GitHub 0.3.2 release
files; the application binaries were not rebuilt or changed during migration.

Verification: TypeScript, optimized export and copy/link audit passed (101 local
links). Seven root-domain HTTPS routes were checked through addresses returned
by Cloudflare DNS, with certificate validation enabled. Published asset states,
sizes and SHA-256 digests matched the website manifest. The www download page
rendered correctly in a browser. Local deployment evidence, screenshot and the
previous default page are under `dist/fixoflow-tech-deployment/` (not committed).

At verification time both authoritative nameservers and Google/Cloudflare
resolved the root domain. This Mac's ISP resolver intermittently returned
NOERROR with no A record, and normal root-domain browsing failed locally while
www worked. Thus universal/local DNS resolution is not claimed. Existing DNS
records were inspected through Hostinger MCP and left unchanged; the root ALIAS
and www CNAME already target Hostinger CDN. Mail records were not modified.

## What installed 0.3.2 applications do

The shared `UpdateService` requests GitHub's public `/releases/latest` endpoint.
Windows/Linux start a check after the hub loads when `check_updates_on_launch`
is enabled (default true). Settings also provides a manual check. Mac uses the
same service unless a separately configured signed updater is present.

If a newer stable release is returned, the UI shows an in-app banner and a
**View update** button. The button opens that GitHub release page. This is not
a native Windows desktop toast. A quiet-starting app can check in the background,
but the banner is seen when the main window is opened. There is no periodic
polling of an already-running app or push notification service.

Automatic download/installation is not configured in this preview. Its control
is disabled; Windows rejects enabling it. Mac has optional Sparkle integration
hooks, but this build has no signed feed. The user installs a downloaded update
manually. The website domain is not used for update discovery, so this migration
does not change existing clients' update endpoint.

## Publishing a future 0.3.3

1. Change the application release version to 0.3.3; build/test each installer,
   including native upgrade and user-data retention checks. Complete publisher
   signing/notarization and the required acceptance before calling it stable.
2. Publish the matching `v0.3.3` GitHub release with its installers and notes as
   the latest **stable** release (not a draft or prerelease).
3. Regenerate the website download manifest for those exact files, update the
   release copy, then deploy the website. Merely editing the website does not
   notify installed applications.
4. A 0.3.2 user with internet access and checks enabled receives the in-app
   availability banner on the next app start, or after a manual Settings check.
   They open the release page and manually install their platform's package.

Current `v0.3.2` is a prerelease, and the live stable endpoint returns no release.
The installed parser explicitly rejects draft/prerelease metadata. Publishing
0.3.3 as another preview therefore will not notify these existing clients.
A preview-update channel, native notifications, periodic checks and signed
automatic installers require additional implementation; they were not added by
this website migration.

## Executed update verification

All 19 existing update tests passed. An isolated service check supplied simulated
stable 0.3.3 metadata to the real `UpdateService` and observed `state=available`,
`latest_version=0.3.3`, the correct release link and automatic installation false.
No real 0.3.3 release was published and no update was offered to production users
by this test. Real Windows UI/installer upgrade behavior was not executed here.

GitHub documents that the latest endpoint excludes drafts and prereleases:
https://docs.github.com/en/rest/releases/releases#get-the-latest-release

**VERDICT: PASS** for website deployment, updated origin and the existing update
service check. Local root-domain DNS resolution remains inconsistent, and full
automatic software updating is not delivered.
