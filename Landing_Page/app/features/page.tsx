import type { Metadata } from "next";
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
      <FeatureStories />
      <PrivacyStory />
      <ClosingCta />
    </MotionScene>
  );
}
