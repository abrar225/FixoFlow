"use client";
import * as Accordion from "@radix-ui/react-accordion";
import { Plus } from "lucide-react";
const questions = [
  [
    "Is it really free?",
    "Yes. Fixo Flow is free to use. There is no account, credit card, subscription, or trial countdown.",
  ],
  [
    "Which computers can use Fixo Flow?",
    "The Mac build requires Apple Silicon and macOS 14 or later. Windows x64 and Ubuntu 24.04 X11 packages are early previews; see Downloads for availability and current limitations. Windows 10 22H2 is a compatibility target, not a claim of continued Microsoft support. Intel Mac and mobile packages are not provided.",
  ],
  [
    "How do I start dictating?",
    "Click the text field you want to write in, then hold Control + Space to speak. Release to transcribe and paste. Configure a separate hands-free shortcut: press once to start and again to finish. Both bindings are configurable in Settings. You can also use the floating bar.",
  ],
  [
    "Does it need an internet connection?",
    "The bundled speech model runs on your computer, so dictation can work offline. Downloading the app and optional release checks need an internet connection. Startup checks can be disabled in Settings. The current bundled model is designed for English.",
  ],
  [
    "Which languages are available?",
    "This release supports English. US, UK and India English preferences share the same recognizer; they do not force regional spelling. Multilingual dictation, including Hindi and Roman Hinglish, is coming soon and remains in accuracy research.",
  ],
  [
    "What happens to my recordings?",
    "Fixo Flow keeps recordings, transcripts, dictionary entries, and preferences locally on your computer. Audio files are stored in the app’s local audio cache; they do not disappear just because you close the app. See the Privacy page for the storage locations.",
  ],
  [
    "What if my words don’t appear in the app?",
    "The transcript is copied to your clipboard before Fixo Flow attempts to paste it. Paste it yourself, or recover it from local history. Accessibility permission is required for automatic pasting.",
  ],
];
export function FaqAccordion() {
  return (
    <section className="faq-section shell" id="faq">
      <div>
        <p className="section-caption">Before you find your flow</p>
        <h2>
          Good
          <br />
          questions.
        </h2>
        <p>
          A few things you might
          <br />
          be wondering.
        </p>
      </div>
      <Accordion.Root type="single" collapsible className="faq-list">
        {questions.map(([question, answer], index) => (
          <Accordion.Item
            value={`question-${index}`}
            key={question}
            className="faq-item"
          >
            <Accordion.Header>
              <Accordion.Trigger className="faq-trigger">
                {question}
                <Plus size={20} aria-hidden="true" />
              </Accordion.Trigger>
            </Accordion.Header>
            <Accordion.Content className="faq-answer">
              <p>{answer}</p>
            </Accordion.Content>
          </Accordion.Item>
        ))}
      </Accordion.Root>
    </section>
  );
}
