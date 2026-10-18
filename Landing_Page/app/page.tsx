import { ArrowDown, AudioLines } from "lucide-react";
import { DownloadLink } from "@/components/brand";
import { VoiceDemo } from "@/components/voice-demo";
import { MotionScene } from "@/components/motion-scene";
import {
  FeatureStories,
  GettingStarted,
  ClosingCta,
  PrivacyStory,
} from "@/components/product-sections";
import { FaqAccordion } from "@/components/faq-accordion";

export default function HomePage() {
  return (
    <MotionScene>
      <section className="hero shell" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="hero-intro" data-enter>
            <AudioLines size={18} /> A little freedom from your keyboard.
          </p>
          <h1 id="hero-title">
            <span className="title-line">
              <span data-title>Think it.</span>
            </span>
            <span className="title-line">
              <span data-title>Speak it.</span>
            </span>
            <span className="title-line">
              <span data-title>Make it flow.</span>
            </span>
          </h1>
          <p className="hero-description" data-enter>
            Turn your voice into writing, right where you’re working. Fixo Flow
            is your free dictation companion for your computer.
          </p>
          <div className="hero-actions" data-enter>
            <DownloadLink />
            <a className="text-link" href="#see-it-flow">
              See it in action <ArrowDown size={16} />
            </a>
          </div>
          <p className="quiet-note" data-enter>
            Free to use. No account. Just your voice.
          </p>
        </div>
        <div className="hero-stage" data-stage>
          <VoiceDemo variant="hero" />
        </div>
        <div className="hero-bottom">
          <span>Your ideas have places to be.</span>
          <a href="#everyday">
            Let’s get them there <ArrowDown size={16} />
          </a>
        </div>
      </section>
      <section className="everyday shell" id="everyday">
        <p className="section-caption">
          Less time at the keys. More room for your thoughts.
        </p>
        <div
          className="everyday-words"
          aria-label="Emails, messages, notes, and big ideas"
        >
          <span>Emails.</span>
          <span>Messages.</span>
          <span>Notes.</span>
          <span>Big ideas.</span>
          <AudioLines aria-hidden="true" />
        </div>
        <div className="intro-row">
          <h2>
            Same you.
            <br />A different way to write.
          </h2>
          <p>
            Some thoughts come out better when you say them. Open the app you’re
            already using, start dictation, and let Fixo Flow put your words at
            your cursor.
          </p>
        </div>
      </section>
      <section className="demo-section" id="see-it-flow">
        <div className="shell">
          <div className="section-heading">
            <div>
              <p className="section-caption">
                From a thought to a little progress
              </p>
              <h2>
                Oh, that’s how
                <br />
                it flows.
              </h2>
            </div>
            <p>
              An email. A quick reply. An idea you don’t want to lose. Pick an
              example and watch it land.
            </p>
          </div>
          <VoiceDemo />
          <p className="demo-disclaimer">
            Illustrative examples. This website does not record your microphone.
            Transcription results vary.
          </p>
        </div>
      </section>
      <FeatureStories />
      <PrivacyStory />
      <GettingStarted />
      <FaqAccordion />
      <ClosingCta />
    </MotionScene>
  );
}
