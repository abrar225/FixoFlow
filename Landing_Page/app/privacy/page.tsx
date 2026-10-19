import type { Metadata } from "next";
import {
  ArrowUpRight,
  FileText,
  Folder,
  HardDrive,
  LockKeyhole,
} from "lucide-react";
import { PrivacyStory, ClosingCta } from "@/components/product-sections";
import { MotionScene } from "@/components/motion-scene";
import { PRODUCT } from "@/lib/product";
export const metadata: Metadata = { alternates: { canonical: "/privacy/" }, title: "Privacy" };
const storage = [
  {
    title: "Your preferences",
    path: "~/.fixoflow/config.json",
    text: "Your shortcut, writing style, and app preferences. Changes also create a backup file.",
    icon: FileText,
  },
  {
    title: "Your words & dictionary",
    path: "~/.fixoflow/fixoflow.sqlite",
    text: "Completed dictations, personal dictionary entries, and local usage counts.",
    icon: HardDrive,
  },
  {
    title: "Your recordings",
    path: "~/.fixoflow/audio_cache/",
    text: "Audio recordings and partial transcript recovery files. Cancelled recordings can also remain here.",
    icon: Folder,
  },
  {
    title: "Application logs",
    path: "Mac: ~/Library/Logs/Fixoflow/fixoflow.log; Windows/Linux: ~/.fixoflow/logs/fixoflow.log",
    text: "Rotating local logs used to diagnose app issues.",
    icon: FileText,
  },
];
export default function PrivacyPage() {
  return (
    <MotionScene>
      <section className="page-intro shell">
        <p className="section-caption">Your space to think out loud</p>
        <h1>
          Your voice.
          <br />
          Close to home.
        </h1>
        <p>
          Fixo Flow’s dictation runs on your computer. Your speech is processed
          locally with a bundled model, without an account or a cloud
          transcription service.
        </p>
      </section>
      <PrivacyStory />
      <section className="storage-section shell">
        <div className="section-heading">
          <div>
            <p className="section-caption">Local does not mean temporary</p>
            <h2>
              Where your
              <br />
              thoughts live.
            </h2>
          </div>
          <p>
            Recordings and transcripts are saved on your computer. Closing the app
            does not delete them. Manage local files with the care you’d give
            any personal document.
          </p>
        </div>
        <div className="storage-list">
          {storage.map((item) => (
            <article key={item.path}>
              <item.icon size={21} />
              <div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <code>{item.path}</code>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="shell"><p>On Windows, the home folder shown as ~ is your user profile. Optional startup and manual update checks request public release information from GitHub; audio and writing are not included. Turn off startup checks in Settings for an offline-only workflow.</p></section>
      <section className="privacy-details shell">
        <LockKeyhole size={30} />
        <h2>A clear boundary.</h2>
        <div>
          <p>
            Fixo Flow copies completed text to your system clipboard before trying
            to paste it. The receiving app and any clipboard history tools may
            store that text under their own settings and privacy policies.
          </p>
          <p>
            Offline dictation does not make the rest of your computer offline. If you
            paste into an online app, that app may send your writing to its
            servers.
          </p>
          <p>
            The source is available to inspect. This page describes the
            application’s local dictation design; it is not a claim of an
            independent security certification.
          </p>
          <a
            href={PRODUCT.repository}
            target="_blank"
            rel="noopener noreferrer"
            className="text-link"
          >
            Look inside the project <ArrowUpRight size={17} />
          </a>
        </div>
      </section>
      <ClosingCta />
    </MotionScene>
  );
}
