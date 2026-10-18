import Image from "next/image";
import Link from "next/link";
import { Download } from "lucide-react";
import { PRODUCT } from "@/lib/product";

export function AppIcon({
  size = 44,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <Image
      src={PRODUCT.icon}
      width={size}
      height={size}
      alt=""
      className={`app-icon ${className}`}
    />
  );
}
export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="Fixo Flow home">
      <AppIcon />
      <span>
        fixo<span className="brand-light">flow</span>
        <span className="brand-dot">.</span>
      </span>
    </Link>
  );
}
export function DownloadLink({
  direct = false,
  light = false,
  children,
}: {
  direct?: boolean;
  light?: boolean;
  children?: React.ReactNode;
}) {
  const content = (
    <>
      <Download size={18} />
      <span>{children || "Get Fixo Flow"}</span>
    </>
  );
  return (
    <Link className={`button${light ? " button-light" : ""}`} href={direct ? "/download/#choose-system" : "/download/"}>
      {content}
    </Link>
  );
}
