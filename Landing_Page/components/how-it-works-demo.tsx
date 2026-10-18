"use client";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import {
  Check,
  ClipboardCheck,
  Mail,
  Mic,
  MousePointer2,
  Pause,
  Play,
} from "lucide-react";
import { Waveform } from "./voice-demo";
import { useDemoAvailability } from "./use-demo-availability";

const STEPS = [
  {
    title: "Find your place.",
    description:
      "Click the text field in the email, document, or message you want to write.",
    icon: MousePointer2,
  },
  {
    title: "Give it a voice.",
    description:
      "Hold Control + Space and speak naturally. Your keyboard shortcut is yours to change.",
    icon: Mic,
  },
  {
    title: "Let your words land.",
    description:
      "Release the shortcut. Fixo Flow transcribes, copies, and attempts to paste your words into the app.",
    icon: ClipboardCheck,
  },
];
const TEXT = "Hey Maya, let’s catch up over coffee next week.";

export function HowItWorksDemo() {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [restart, setRestart] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const progress = useRef<HTMLSpanElement>(null);
  const timeline = useRef<gsap.core.Timeline | null>(null);
  const text = useRef<HTMLSpanElement>(null);
  const id = useId();
  const { active, reduced } = useDemoAvailability(root);

  useLayoutEffect(() => {
    if (text.current) text.current.textContent = step === 2 ? TEXT : "";
    if (reduced) return;
    const context = gsap.context(() => {
      const sequence = gsap.timeline({
        paused: true,
        onComplete: () => setStep((current) => (current + 1) % STEPS.length),
      });
      timeline.current = sequence;
      sequence.fromTo(
        ".how-stage-label",
        { y: 10, opacity: 0.25 },
        { y: 0, opacity: 1, duration: 0.5, ease: "power2.out" },
      );
      if (step === 0) {
        sequence.fromTo(
          ".how-pointer",
          { x: 90, y: 70, rotate: -15 },
          { x: 0, y: 0, rotate: 0, duration: 1.2, ease: "power3.inOut" },
          0,
        );
      } else if (step === 1) {
        sequence.fromTo(
          ".how-keyboard kbd",
          { y: 0 },
          {
            y: 3,
            boxShadow: "0 0px 0 #a598b7",
            duration: 0.25,
            stagger: 0.12,
            ease: "power2.out",
          },
          0.2,
        );
      } else {
        const count = { length: 0 };
        if (text.current) text.current.textContent = "";
        sequence
          .to(
            count,
            {
              length: TEXT.length,
              duration: 1.2,
              ease: "none",
              onUpdate: () => {
                if (text.current)
                  text.current.textContent = TEXT.slice(
                    0,
                    Math.floor(count.length),
                  );
              },
            },
            0.1,
          )
          .fromTo(
            ".how-success",
            { scale: 0.8, opacity: 0 },
            { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(1.6)" },
            1.2,
          );
      }
      sequence.to({}, { duration: 4.5 - sequence.duration() });
      sequence.fromTo(
        progress.current,
        { scaleX: 0 },
        { scaleX: 1, duration: 4.5, ease: "none" },
        0,
      );
    }, root);
    return () => {
      timeline.current = null;
      context.revert();
    };
  }, [step, reduced, restart]);

  useEffect(() => {
    if (active && playing) timeline.current?.play();
    else timeline.current?.pause();
  }, [active, playing, step, reduced, restart]);

  function select(index: number) {
    setRestart((value) => value + 1);
    setPlaying(true);
    setStep(index);
  }
  return (
    <div
      ref={root}
      className="how-explainer"
      data-step={step}
      data-playing={active && playing}
    >
      <div
        className="how-workspace"
        id={`${id}-scene`}
        aria-label={`Step ${step + 1}: ${STEPS[step].title}`}
      >
        <div className="how-scene-top">
          <span>Make a little space for your thoughts.</span>
          <span>0{step + 1} / 03</span>
        </div>
        <div className="how-app-window">
          <div className="window-chrome">
            <span className="traffic-lights" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>A note to Maya</span>
            <Mail size={15} />
          </div>
          <div className="how-compose">
            <span>
              To <strong>Maya</strong>
            </span>
            <h3>A little catch-up</h3>
            <div
              className="how-text-field"
              aria-label={step === 2 ? TEXT : "An empty email text field"}
            >
              <span ref={text} aria-hidden="true">
                {step === 2 ? TEXT : ""}
              </span>
              {step === 0 && (
                <span className="how-field-placeholder">
                  Your words go here
                  <span className="typing-cursor" />
                </span>
              )}
              <MousePointer2
                className="how-pointer"
                size={26}
                aria-hidden="true"
              />
            </div>
          </div>
        </div>
        <div className="how-voice-bar" aria-hidden="true">
          <Mic size={17} />
          <Waveform active={step === 1 && active && playing} />
          <span>
            {step === 0
              ? "Ready when you are"
              : step === 1
                ? "Listening to your thought"
                : "Your words, delivered"}
          </span>
          {step === 2 && <Check size={16} />}
        </div>
        <div className="how-keyboard" aria-label="Control plus Space">
          <kbd>⌃ control</kbd>
          <span>+</span>
          <kbd>space</kbd>
        </div>
        <div className="how-stage-label">
          <span className={`how-stage-icon${step === 2 ? " how-success" : ""}`}>
            {step === 0 ? (
              <MousePointer2 size={18} />
            ) : step === 1 ? (
              <Mic size={18} />
            ) : (
              <Check size={18} />
            )}
          </span>
          <span>
            {step === 0
              ? "First, put your cursor where your thought belongs."
              : step === 1
                ? "Hold the shortcut. Say what’s on your mind."
                : "Release. Read it over. Keep your day moving."}
          </span>
        </div>
        <p className="how-mobile-description">{STEPS[step].description}</p>
        <div className="how-cycle-progress" aria-hidden="true">
          <span ref={progress} />
        </div>
      </div>
      <div className="how-explainer-controls">
        <p className="how-select-hint">Follow along, or choose a step.</p>
        <ol className="how-step-buttons">
          {STEPS.map((item, index) => (
            <li key={item.title}>
              <button
                type="button"
                onClick={() => select(index)}
                aria-pressed={step === index}
                aria-controls={`${id}-scene`}
              >
                <span className="step-number">{index + 1}</span>
                <span>
                  <strong>
                    <span className="how-title-full">{item.title}</span>
                    <span className="how-title-short">
                      {["Choose", "Speak", "Insert"][index]}
                    </span>
                  </strong>
                  <span>{item.description}</span>
                </span>
                <item.icon size={20} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ol>
        <button
          type="button"
          className="how-play-toggle text-link"
          disabled={reduced}
          onClick={() => setPlaying((value) => !value)}
        >
          {playing && !reduced ? <Pause size={14} /> : <Play size={14} />}{" "}
          {reduced
            ? "Reduced motion: choose a step"
            : playing
              ? "Pause walkthrough"
              : "Play walkthrough"}
        </button>
        <p className="how-illustrative">
          Illustrative walkthrough. No microphone is recorded.
        </p>
      </div>
    </div>
  );
}
