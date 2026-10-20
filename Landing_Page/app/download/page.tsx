import type { Metadata } from "next";
import {
  Check,
  FolderDown,
  Keyboard,
  Mic,
  MousePointer2,
} from "lucide-react";
import { AppIcon, DownloadLink } from "@/components/brand";
import { PlatformDownloads } from "@/components/platform-downloads";
import { PRODUCT } from "@/lib/product";
import releases from "@/lib/releases.generated.json";
export const metadata: Metadata = { alternates: { canonical: "/download/" }, title: "Download Fixo Flow" };
const permissions = [
  {
    title: "Microphone",
    text: "So Fixo Flow can hear you when you start dictation.",
    icon: Mic,
  },
  {
    title: "Accessibility",
    text: "So it can paste your words into the app you’re using.",
    icon: MousePointer2,
  },
  {
    title: "Input Monitoring",
    text: "So your shortcut works while another app is in front.",
    icon: Keyboard,
  },
];
export default function DownloadPage() {
  return (
    <>
      <section className="download-hero shell">
        <div className="download-copy">
          <p className="section-caption">Your words have places to be</p>
          <h1>
            Make room
            <br />
            for your voice.
          </h1>
          <p>
            Download Fixo Flow and give your keyboard a little breathing room.
            No account. No subscription.
          </p>
          <DownloadLink direct>Choose your download</DownloadLink>
          <p className="download-requirement">
            macOS · Windows · Linux<br />
            Check package availability and system requirements below.
          </p>
        </div>
        <div className="download-art">
          <span className="download-art-ring" aria-hidden="true" />
          <div className="download-icon-box">
            <AppIcon size={240} />
            <span>Fixo Flow</span>
            <span className="download-icon-caption">
              A little freedom, for your computer.
            </span>
          </div>
          <span className="download-free-note">
            Free.
            <br />
            And yours.
          </span>
        </div>
      </section>
      <PlatformDownloads />
      <section className="download-help shell" id="release-notes">
        <h2>What's new<br />in {releases.version}.</h2>
        <div>
          <p>Free and open source under the MIT License. <a href={PRODUCT.github + "/releases"}>Download verified build files from GitHub Releases ↗</a> or <a href={PRODUCT.github}>explore the source and contribute ↗</a>.</p>
          <p>Update checks remain compatible with the website feed. Updates are downloaded manually from the public GitHub release page.</p>
          <p>Start quietly when you sign in, choose separate hold-to-talk and hands-free shortcuts, and let Settings save automatically after a short pause.</p>
          <p>Clear spoken sequences become numbered lists in Writing mode and Automatic messaging mode. Your personal dictionary guides name spellings and corrects exact recurring mistakes. Strict Verbatim preserves the recognizer's text.</p>
          <p>This release focuses on English. Multilingual dictation is coming soon. No additional language models are bundled or downloaded for it.</p>
        </div>
      </section>
      <section className="install-section shell" id="setup">
        <div className="section-heading">
          <div>
            <p className="section-caption">Let’s get you settled</p>
            <h2>
              Mac setup: from download
              <br />
              to your first words.
            </h2>
          </div>
          <p>
            {releases.platforms.find(platform => platform.id === "macos")?.publicTrustVerified
              ? "This is an early release. Review the Mac permissions below before your first dictation."
              : "Fixo Flow is an experimental, locally signed app. The current build is not Apple notarized, so macOS may show a security notice."}
          </p>
        </div>
        <ol className="install-steps">
          <li>
            <span>1</span>
            <FolderDown />
            <h3>Open your download.</h3>
            <p>
              Open the Mac DMG from Downloads, then drag Fixo Flow into
              Applications.
            </p>
          </li>
          <li>
            <span>2</span>
            <AppIcon size={50} />
            <h3>Make yourself at home.</h3>
            <p>
              Launch Fixo Flow from Applications. Review the Mac permissions
              below and allow them in System Settings.
            </p>
          </li>
          <li>
            <span>3</span>
            <Mic />
            <h3>Say your first words.</h3>
            <p>
              Restart Fixo Flow after granting permissions. Click a text field,
              hold your configured hold-to-talk shortcut, speak, and release. Configure a separate hands-free shortcut in Settings.
            </p>
          </li>
        </ol>
      </section>
      <section className="permission-section" id="permissions">
        <div className="shell">
          <div className="section-heading">
            <div>
              <p className="section-caption">
                A little introduction to your Mac
              </p>
              <h2>
                Three permissions.
                <br />
                One clear purpose.
              </h2>
            </div>
            <p>
              Open System Settings → Privacy & Security, then find each
              permission. Fixo Flow’s Settings also shows their current status.
            </p>
          </div>
          <div className="permission-list">
            {permissions.map((item) => (
              <article key={item.title}>
                <item.icon size={24} />
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
                <span className="permission-label">
                  <Check size={14} /> Allow Fixo Flow
                </span>
              </article>
            ))}
          </div>
          <p className="permission-footnote">
            After allowing Input Monitoring, restart Fixo Flow so your shortcut
            can activate. If automatic pasting is unavailable, your transcript
            stays on the clipboard.
          </p>
        </div>
      </section>
      <section className="download-help shell">
        <h2>
          A note before
          <br />
          you begin.
        </h2>
        <div>
          <p>
            This is an early, experimental release. Recognition accuracy,
            response time, and memory use depend on your computer and your recording.
            Read through important text before sending it.
          </p>
          <p>
            Only download builds you trust. If macOS blocks the app or you need
            help with installation, review the platform requirements and installation steps above.
          </p>
        </div>
      </section>
    </>
  );
}
