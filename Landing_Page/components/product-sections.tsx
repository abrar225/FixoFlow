import Link from "next/link";
import {
  ArrowUpRight,
  AudioLines,
  Check,
  Folder,
  LockKeyhole,
} from "lucide-react";
import { AppIcon, DownloadLink } from "./brand";
import { StylePreview } from "./style-preview";
import { PRODUCT } from "@/lib/product";
import { HowItWorksDemo } from "./how-it-works-demo";

export function FeatureStories() {
  return (
    <section className="features-section shell" id="features">
      <div className="section-heading">
        <div>
          <p className="section-caption">Little details. A more natural day.</p>
          <h2>
            Fits the way
            <br />
            you think.
          </h2>
        </div>
        <Link className="text-link" href="/features/">
          Meet your new companion <ArrowUpRight size={18} />
        </Link>
      </div>
      <div className="feature-stories">
        <article className="feature-story feature-style">
          <div className="feature-copy">
            <span className="feature-index">
              <AudioLines size={18} /> Your words
            </span>
            <h3>
              A voice that’s
              <br />
              still yours.
            </h3>
            <p>
              Keep it natural or choose a more formal style. Simple, on-device
              writing rules clean up fillers, punctuation, and spacing.
            </p>
          </div>
          <StylePreview />
        </article>
        <article className="feature-story feature-dictionary">
          <div
            className="dictionary-visual"
            aria-label="Example personal dictionary"
          >
            <span className="dictionary-title">
              Your dictionary <span>+ Add a word</span>
            </span>
            <div>
              <span className="dictionary-avatar">M</span>
              <span>
                Maya Desai<small>A name you use often</small>
              </span>
              <Check size={16} />
            </div>
            <div>
              <span className="dictionary-avatar mint">F</span>
              <span>
                Fixo Flow<small>Just the way you spell it</small>
              </span>
              <Check size={16} />
            </div>
            <div className="dictionary-tag">
              Familiar words. Familiar spelling.
            </div>
          </div>
          <div className="feature-copy">
            <h3>
              Your people.
              <br />
              Your vocabulary.
            </h3>
            <p>
              Add the names and terms that matter to you. Your personal
              dictionary helps Fixo Flow recognize and replace them.
            </p>
          </div>
        </article>
        <article className="feature-story feature-history">
          <div className="feature-copy">
            <h3>
              A thought worth
              <br />
              coming back to.
            </h3>
            <p>
              Past dictations stay in your local history. If a paste misses its
              mark, your words are also on the clipboard, ready to use.
            </p>
          </div>
          <div
            className="history-visual"
            aria-label="Illustrative local dictation history"
          >
            <span className="history-date">Your recent thoughts</span>
            <div>
              <span className="history-dot" />
              <p>
                An idea for the weekend…<small>Saved on this device</small>
              </p>
              <ArrowUpRight size={16} />
            </div>
            <div>
              <span className="history-dot lilac" />
              <p>
                Hey Maya, I loved your idea…<small>Saved on this device</small>
              </p>
              <ArrowUpRight size={16} />
            </div>
            <span className="history-bottom">
              <Folder size={14} /> A little peace of mind.
            </span>
          </div>
        </article>
      </div>
    </section>
  );
}

export function PrivacyStory() {
  return (
    <section className="privacy-story">
      <div className="shell privacy-story-inner">
        <div className="privacy-art" aria-hidden="true">
          <div className="privacy-orbit" data-scroll-art>
            <span />
            <span />
            <span />
          </div>
          <div className="privacy-device">
            <div>
              <AppIcon size={88} />
              <span>Your voice belongs here.</span>
              <LockKeyhole size={18} />
            </div>
            <i />
          </div>
          <span className="privacy-caption">
            <LockKeyhole size={14} /> Right at home, on your computer.
          </span>
        </div>
        <div className="privacy-copy">
          <p className="section-caption">Personal means personal</p>
          <h2>
            Some things
            <br />
            stay with you.
          </h2>
          <p>
            Your voice. Your writing. Your half-finished ideas. Fixo Flow
            processes speech on your computer, without sending it to a transcription
            service.
          </p>
          <p>
            Dictation works offline with the included model. No account, no
            subscription, no cloud polishing.
          </p>
          <Link href="/privacy/" className="text-link">
            A closer look at privacy <ArrowUpRight size={17} />
          </Link>
        </div>
      </div>
    </section>
  );
}

export function GettingStarted({ setup = false }: { setup?: boolean }) {
  return (
    <section className="getting-started shell" id="how-it-works">
      <div className="section-heading">
        <div>
          <p className="section-caption">Make yourself at home</p>
          <h2>
            {setup ? (
              <>
                A small habit.
                <br />A whole new flow.
              </>
            ) : (
              <>
                Three little steps.
                <br />
                Then it’s your turn.
              </>
            )}
          </h2>
        </div>
        <p>
          Once you’ve installed Fixo Flow and allowed the permissions for your system,
          you’re ready to go.
        </p>
      </div>
      <HowItWorksDemo />
      <div className="setup-link">
        <span>Your keyboard shortcut is yours to change in Settings.</span>
        <Link href="/download/#setup" className="text-link">
          Get the setup guide <ArrowUpRight size={17} />
        </Link>
      </div>
    </section>
  );
}

export function ClosingCta() {
  return (
    <section className="closing-cta">
      <div className="shell">
        <span className="closing-mark" aria-hidden="true">
          <AudioLines />
        </span>
        <p className="section-caption">Your next good idea is waiting</p>
        <h2>
          Give it
          <br />a voice.
        </h2>
        <p>
          Free to use. Open for everyone to build on.
          <br />A little more room to be you.
        </p>
        <DownloadLink />
        <a
          className="text-link"
          href={PRODUCT.repository}
          target="_blank"
          rel="noopener noreferrer"
        >
          Made in the open <ArrowUpRight size={17} />
        </a>
      </div>
    </section>
  );
}
