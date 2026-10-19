import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { PRODUCT } from "@/lib/product";
export const metadata: Metadata = {
  metadataBase: new URL(PRODUCT.origin),
  title: {
    default: "Fixo Flow | A little freedom from your keyboard",
    template: "%s | Fixo Flow",
  },
  description:
    "Turn your voice into writing in your everyday apps. Fixo Flow is free, open source dictation that processes your speech on your computer. No account required.",
  icons: { icon: PRODUCT.icon, apple: PRODUCT.icon },
  openGraph: {
    title: "Fixo Flow | Think it. Speak it. Make it flow.",
    description:
      "Free voice dictation for your everyday apps. Your thoughts, in full flow.",
    images: [{ url: PRODUCT.icon, width: 1254, height: 1254 }],
  },
};
export const viewport: Viewport = {
  themeColor: "#eee9fb",
  width: "device-width",
  initialScale: 1,
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={GeistSans.variable}>
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <Navbar />
        <main id="main">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
