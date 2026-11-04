import type { Metadata } from "next";
import Image from "next/image";
import { PRODUCT } from "@/lib/product";
import releases from "@/lib/releases.generated.json";
import {
  FeatureStories,
  PrivacyStory,
  ClosingCta,
} from "@/components/product-sections";
import { VoiceDemo } from "@/components/voice-demo";
import { MotionScene } from "@/components/motion-scene";
export const metadata: Metadata = { alternates: { canonical: "/features/" }, title: "Why Fixo Flow" };
export default function FeaturesPage() {
  return (
    <MotionScene>
      <section className="page-intro shell">
        <p className="section-caption">For the things you say every day</p>
        <h1>
          Your words.
          <br />
          More possibilities.
        </h1>
        <p>
          Write a thoughtful email, keep a fleeting idea, or reply to a friend.
          Fixo Flow brings voice dictation into the apps you already use.
        </p>
      </section>
      <section className="feature-demo-wrap shell">
        <VoiceDemo />
        <p className="demo-disclaimer">
          Illustrative examples, not a live microphone. The bundled speech model
          is designed for English.
        </p>
      </section>
      <section className="desktop-preview shell" id="desktop-preview" aria-labelledby="desktop-preview-title">
        <div className="section-heading">
          <div>
            <p className="section-caption">In development · 0.5.0 preview</p>
            <h2 id="desktop-preview-title">From setup to your first words.</h2>
          </div>
          <p>
            Follow six steps to check permissions and your microphone, choose a local
            speech model, and try dictation without pasting into another app.
            Resume setup whenever you’re ready.
          </p>
        </div>
        <div className="desktop-preview-grid">
          <figure>
            <Image src="/images/app-preview/ui-preview-onboarding.png" width={1040} height={740}
              alt="Guided setup showing six steps and five optional starting presets" />
            <figcaption>Guided setup shows your progress from permissions to practice.</figcaption>
          </figure>
          <figure>
            <Image src="/images/app-preview/ui-preview-settings.png" width={1040} height={740}
              alt="Dark Settings screen showing preset cards, theme and microphone controls" />
            <figcaption>Settings explains what each preset changes before you apply it.</figcaption>
          </figure>
        </div>
        <p className="desktop-preview-note">
          Screenshots from the macOS development preview. These features are in development.
          The <a href={PRODUCT.download}>public download</a> is the English-language {releases.version} preview.
        </p>
      </section>
      <FeatureStories />
      <PrivacyStory />
      <ClosingCta />
    </MotionScene>
  );
}
