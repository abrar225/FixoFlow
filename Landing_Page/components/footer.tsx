import Link from "next/link";
import { Brand } from "./brand";
import releases from "@/lib/releases.generated.json";
export function Footer() {
  return (
    <footer className="site-footer">
      <div className="shell">
        <div className="footer-top">
          <div>
            <Brand />
            <p>
              A little freedom from your keyboard.
              <br />
              Free dictation for your everyday words.
            </p>
          </div>
          <div className="footer-links">
            <Link href="/features/">Features</Link>
            <Link href="/how-it-works/">How it works</Link>
            <Link href="/download/">Download & setup</Link>
            <Link href="/privacy/">Privacy</Link>
          </div>
        </div>
        <div className="footer-wordmark" aria-hidden="true">
          let it flow<span>↗</span>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} Fixo Flow · v{releases.version} preview</span>
          <span>Free to use. All rights reserved.</span>
        </div>
      </div>
    </footer>
  );
}
