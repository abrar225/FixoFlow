// Apple brand silhouette from Simple Icons (CC0). Lucide supplies UI icons.
import { siApple } from "simple-icons";
export function AppleLogo({
  size = 20,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d={siApple.path} />
    </svg>
  );
}
