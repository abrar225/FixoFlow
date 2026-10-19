import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Brand } from "./brand";
import { PRODUCT } from "@/lib/product";
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
              Free, open source dictation.
            </p>
          </div>
          <div className="footer-links">
            <Link href="/features/">Features</Link>
            <Link href="/how-it-works/">How it works</Link>
            <Link href="/download/">Download & setup</Link>
            <Link href="/privacy/">Privacy</Link>
            <a
              href={PRODUCT.repository}
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub <ArrowUpRight size={14} />
            </a>
          </div>
        </div>
        <div className="footer-wordmark" aria-hidden="true">
          let it flow<span>↗</span>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} Fixo Flow contributors · v{releases.version} preview</span>
          <span>
            Made to be yours. Shared under the{" "}
            <a
              href={`${PRODUCT.repository}/blob/main/LICENSE`}
              target="_blank"
              rel="noopener noreferrer"
            >
              MIT License.
            </a>
          </span>
        </div>
      </div>
    </footer>
  );
}
