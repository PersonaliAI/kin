import { cn } from "@/lib/utils";

/**
 * Kin brandmark — the rounded black square with a white "K", matching the
 * Kin product card on the landing page. Use this wherever we represent the
 * assistant inside the product (sidebar, splash, etc.).
 */
export function KinMark({
  className,
  size = 32,
  showLabel = false,
}: {
  className?: string;
  size?: number;
  showLabel?: boolean;
}) {
  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <div
        className="rounded-lg bg-[#0a0a0a] flex items-center justify-center shrink-0"
        style={{ width: size, height: size }}
        aria-hidden
      >
        <span
          className="text-white font-bold leading-none"
          style={{ fontSize: Math.round(size * 0.48) }}
        >
          K
        </span>
      </div>
      {showLabel && (
        <span className="text-sm font-semibold tracking-tight">Kin</span>
      )}
    </div>
  );
}
