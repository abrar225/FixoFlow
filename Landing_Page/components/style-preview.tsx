"use client";
import { useState } from "react";
import { Check } from "lucide-react";
import { BlurFade } from "./magicui/blur-fade";
const styles = [
  {
    name: "Natural",
    text: "I can't wait to share the idea.",
    detail: "A little cleanup, still your words.",
  },
  {
    name: "Professional",
    text: "I cannot wait to share the idea.",
    detail: "Expands contractions for a more formal tone.",
  },
  {
    name: "Verbatim",
    text: "um I can't wait to share the idea.",
    detail: "Keeps the recognizer’s wording.",
  },
];
export function StylePreview() {
  const [active, setActive] = useState(0);
  return (
    <div className="style-preview">
      <div
        className="style-options"
        role="group"
        aria-label="Preview a writing style"
      >
        {styles.map((style, index) => (
          <button
            key={style.name}
            type="button"
            aria-pressed={active === index}
            onClick={() => setActive(index)}
          >
            {active === index && <Check size={13} />}
            {style.name}
          </button>
        ))}
      </div>
      <div className="style-paper" aria-live="polite">
        <span className="paper-label">A little note</span>
        <BlurFade key={active}>
          <p>{styles[active].text}</p>
        </BlurFade>
        <span className="paper-line" />
        <span className="paper-line short" />
      </div>
      <p className="style-detail">{styles[active].detail}</p>
    </div>
  );
}
