"use client";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import {
  AudioLines,
  Check,
  FileText,
  Mail,
  MessageCircle,
  Mic,
  Play,
  Pause,
  Send,
} from "lucide-react";
import { gsap } from "gsap";
import { useDemoAvailability } from "./use-demo-availability";

const EXAMPLES = [
  {
    name: "An email",
    icon: Mail,
    title: "A little catch-up",
    to: "Maya",
    spoken:
      "Hey Maya, I loved your idea. Let’s find a time to talk about it over coffee next week.",
    output:
      "Hey Maya, I loved your idea. Let’s find a time to talk about it over coffee next week.",
    kind: "email",
  },
  {
    name: "A message",
    icon: MessageCircle,
    title: "The weekend plan",
    to: "The group chat",
    spoken: "I’m bringing the snacks. See you all at the park on Saturday!",
    output: "I’m bringing the snacks. See you all at the park on Saturday!",
    kind: "message",
  },
  {
    name: "A note",
    icon: FileText,
    title: "An idea worth keeping",
    to: "My notes",
    spoken:
      "An idea for the weekend: a photo walk around the old town, followed by a very long lunch.",
    output:
      "An idea for the weekend: a photo walk around the old town, followed by a very long lunch.",
    kind: "note",
  },
] as const;

export function Waveform({ active = false }: { active?: boolean }) {
  return (
    <span
      className={`waveform${active ? " is-active" : ""}`}
      aria-hidden="true"
    >
      {[8, 14, 22, 12, 27, 18, 32, 23, 13, 28, 19, 10, 23, 15, 7].map(
        (height, index) => (
          <i
            key={index}
            style={{ height, animationDelay: `${index * -0.08}s` }}
          />
        ),
      )}
    </span>
  );
}

export function VoiceDemo({ variant = "full" }: { variant?: "hero" | "full" }) {
  const [selected, setSelected] = useState(0);
  const [phase, setPhase] = useState<"ready" | "speaking" | "writing">("ready");
  const [paused, setPaused] = useState(false);
  const [restart, setRestart] = useState(0);
  const example = EXAMPLES[selected];
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);
  const output = useRef<HTMLSpanElement>(null);
  const progress = useRef<HTMLSpanElement>(null);
  const timeline = useRef<gsap.core.Timeline | null>(null);
  const { active, reduced } = useDemoAvailability(ref);
  const isHero = variant === "hero";

  useLayoutEffect(() => {
    const text = output.current;
    if (!text) return;
    if (reduced) {
      text.textContent = example.output;
      setPhase("ready");
      return;
    }
    const count = { length: 0 };
    const context = gsap.context(() => {
      const cycle = gsap.timeline({
        paused: true,
        onComplete: () => setSelected((index) => (index + 1) % EXAMPLES.length),
      });
      timeline.current = cycle;
      cycle
        .call(() => {
          text.textContent = "";
          setPhase("speaking");
        })
        .fromTo(
          ".writing-content",
          { opacity: 0.3, y: 12 },
          { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" },
          0,
        )
        .call(() => setPhase("writing"), [], 1.2)
        .to(
          count,
          {
            length: example.output.length,
            duration: 1.65,
            ease: "none",
            onUpdate: () => {
              text.textContent = example.output.slice(
                0,
                Math.floor(count.length),
              );
            },
          },
          1.2,
        )
        .call(
          () => {
            text.textContent = example.output;
            setPhase("ready");
          },
          [],
          2.85,
        )
        .to({}, { duration: 2.8 })
        .to(".writing-content", { opacity: 0, y: -8, duration: 0.3 });
      cycle.fromTo(
        progress.current,
        { scaleX: 0 },
        { scaleX: 1, duration: cycle.duration(), ease: "none" },
        0,
      );
    }, ref);
    return () => {
      timeline.current = null;
      context.revert();
    };
  }, [example, selected, restart, reduced]);

  useEffect(() => {
    if (active && !paused) timeline.current?.play();
    else timeline.current?.pause();
  }, [active, paused, selected, restart, reduced]);

  function choose(index: number) {
    setPaused(false);
    setSelected(index);
    setRestart((value) => value + 1);
  }
  return (
    <div
      ref={ref}
      data-example={example.kind}
      data-phase={phase}
      className={`voice-demo ${isHero ? "voice-demo-hero" : "voice-demo-full"}`}
    >
      {!isHero && (
        <div
          className="example-controls"
          role="group"
          aria-label="Choose an example"
        >
          {EXAMPLES.map((item, index) => (
            <button
              key={item.name}
              type="button"
              aria-pressed={selected === index}
              onClick={() => choose(index)}
            >
              <item.icon size={17} />
              {item.name}
            </button>
          ))}
        </div>
      )}
      <div className="demo-scene">
        <svg
          className="flow-loop"
          viewBox="0 0 560 540"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M50 395C-25 275 83 56 301 69C490 81 578 220 480 361C411 459 240 502 218 400C195 294 433 284 498 469"
            stroke="currentColor"
            strokeWidth="38"
            strokeLinecap="round"
          />
          <path
            d="M50 395C-25 275 83 56 301 69C490 81 578 220 480 361C411 459 240 502 218 400C195 294 433 284 498 469"
            stroke="white"
            strokeOpacity=".3"
            strokeWidth="1"
          />
        </svg>
        <div className={`writing-window ${example.kind}`}>
          <div className="window-chrome">
            <span className="traffic-lights" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>{example.name}</span>
            <example.icon size={15} />
          </div>
          <div className="writing-content">
            <div className="window-recipient">
              <span>{example.kind === "note" ? "Saved to" : "To"}</span>
              <strong>{example.to}</strong>
              {example.kind !== "note" && (
                <span className="recipient-dot" aria-hidden="true" />
              )}
            </div>
            {example.kind !== "message" && <h3>{example.title}</h3>}
            <div className="example-output" id={`${id}-output`}>
              <span className="sr-only">{example.output}</span>
              <p
                aria-hidden="true"
                className={example.kind === "message" ? "message-bubble" : ""}
              >
                <span ref={output}>{example.output}</span>
                {phase === "writing" && <span className="typing-cursor" />}
              </p>
            </div>
            <div className="window-bottom">
              <span>
                {phase === "ready" ? (
                  <>
                    <Check size={13} /> Words, right where you need them.
                  </>
                ) : (
                  "Putting your thought into words…"
                )}
              </span>
              {example.kind !== "note" && (
                <span className="send-illustration" aria-hidden="true">
                  <Send size={14} />
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="speech-note">
          <div className="speech-note-top">
            <Mic size={17} />
            <span>You say something like…</span>
          </div>
          <p>“{example.spoken}”</p>
          <span className="speech-annotation">One thought, out loud.</span>
        </div>
        <div
          className={`dictation-capsule${phase === "speaking" ? " recording" : ""}`}
        >
          <AudioLines size={19} />
          <Waveform active={phase === "speaking" && active && !paused} />
          <span>
            {phase === "speaking"
              ? "Listening"
              : phase === "writing"
                ? "Writing"
                : "In your flow"}
          </span>
          <span className="capsule-dot" />
        </div>
        {isHero && (
          <span className="hero-sticker" aria-hidden="true">
            your voice,
            <br />
            on the page <span>↗</span>
          </span>
        )}
      </div>
      <div className="demo-playbar">
        <button
          className="replay-button"
          type="button"
          onClick={() => setPaused((value) => !value)}
          aria-label={paused || reduced ? "Play examples" : "Pause examples"}
          aria-controls={`${id}-output`}
          disabled={reduced}
        >
          {paused || reduced ? (
            <Play size={13} fill="currentColor" />
          ) : (
            <Pause size={13} fill="currentColor" />
          )}
          {reduced
            ? "Motion reduced"
            : paused
              ? "Play examples"
              : "Pause examples"}
        </button>
        <div
          className="example-dots"
          role="group"
          aria-label="Choose a demo example"
        >
          {EXAMPLES.map((item, index) => (
            <button
              key={item.kind}
              type="button"
              aria-label={`Show ${item.kind} example`}
              aria-pressed={selected === index}
              onClick={() => choose(index)}
            >
              <span />
            </button>
          ))}
        </div>
        <span className="demo-status">
          {selected + 1} / {EXAMPLES.length}
          <span className="demo-status-label"> · Illustrative demo</span>
        </span>
      </div>
      <div className="demo-cycle-progress" aria-hidden="true">
        <span ref={progress} />
      </div>
      <span className="sr-only">
        Three illustrative examples cycle automatically. Use Pause examples to
        stop the loop, or choose an example.
      </span>
    </div>
  );
}
