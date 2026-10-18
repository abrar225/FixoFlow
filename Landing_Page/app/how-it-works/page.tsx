import type { Metadata } from "next";
import { ArrowUpRight, ClipboardCheck, Keyboard, Mic } from "lucide-react";
import Link from "next/link";
import { GettingStarted, ClosingCta } from "@/components/product-sections";
import { MotionScene } from "@/components/motion-scene";
export const metadata: Metadata = { title: "How it works" };
export default function HowItWorksPage() {
  return (
    <MotionScene>
      <section className="page-intro shell">
        <p className="section-caption">An easier way from thought to text</p>
        <h1>
          A small shortcut.
          <br />A little more freedom.
        </h1>
        <p>
          Stay in the app you’re using. Fixo Flow listens when you start
          dictation and writes when you finish.
        </p>
      </section>
      <GettingStarted setup />
      <section className="help-section shell">
        <h2>
          A few helpful
          <br />
          little details.
        </h2>
        <div className="help-grid">
          <article>
            <Keyboard />
            <h3>Hold or tap. Your choice.</h3>
            <p>
              Hold the shortcut for push-to-talk. For a longer thought, tap to
              start and tap again to stop. Press Escape to cancel.
            </p>
          </article>
          <article>
            <Mic />
            <h3>A bar that stays close.</h3>
            <p>
              The floating bar shows when you’re recording. Click it to toggle
              dictation, or drag it to a more comfortable spot on your screen.
            </p>
          </article>
          <article>
            <ClipboardCheck />
            <h3>Your words have a backup.</h3>
            <p>
              Fixo Flow copies the transcript before attempting to paste. If the
              app doesn’t accept it, use your clipboard or local history.
            </p>
          </article>
        </div>
        <Link className="text-link" href="/download/#permissions">
          Set up the Mac permissions <ArrowUpRight size={17} />
        </Link>
      </section>
      <ClosingCta />
    </MotionScene>
  );
}
