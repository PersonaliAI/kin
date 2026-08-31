"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Renders `children` into document.body, positioned relative to `anchorRef`.
// Needed because popovers inside cards/sections with their own stacking
// context (e.g. a framer-motion wrapper) would otherwise render behind or
// get visually clipped by later sibling sections (the recurring
// "dropdowns/calendar cropped" bug) — a portal escapes that entirely.
export function FloatingPopover({
  open,
  anchorRef,
  onClose,
  align = "left",
  side = "bottom",
  className,
  matchAnchorWidth = false,
  children,
}: {
  open: boolean;
  anchorRef: React.RefObject<HTMLElement | null>;
  onClose: () => void;
  align?: "left" | "right";
  side?: "top" | "bottom";
  className?: string;
  /** Force the popover to the anchor's width instead of shrink-to-fit —
   * for dropdowns (like Select) that should visually line up with their
   * trigger button rather than shrinking to their narrowest option. */
  matchAnchorWidth?: boolean;
  children: React.ReactNode;
}) {
  const popRef = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<{ top: number; left: number; maxHeight: number; width?: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    function reposition() {
      const anchor = anchorRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const vh = window.innerHeight;
      const vw = window.innerWidth;
      const popWidth = matchAnchorWidth ? rect.width : popRef.current?.offsetWidth || 256;
      let top: number;
      let maxHeight: number;
      if (side === "top") {
        top = Math.max(8, rect.top - 8);
        maxHeight = top - 8;
      } else {
        top = rect.bottom + 8;
        maxHeight = vh - top - 8;
      }
      let left = align === "right" ? rect.right - popWidth : rect.left;
      left = Math.min(Math.max(8, left), vw - popWidth - 8);
      setStyle({ top, left, maxHeight: Math.max(120, maxHeight), width: matchAnchorWidth ? rect.width : undefined });
    }
    reposition();
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    function handleOutside(e: MouseEvent) {
      if (
        popRef.current &&
        !popRef.current.contains(e.target as Node) &&
        anchorRef.current &&
        !anchorRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
      document.removeEventListener("mousedown", handleOutside);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, align, side, matchAnchorWidth]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={popRef}
      style={{
        position: "fixed",
        top: side === "top" ? undefined : style?.top,
        bottom: side === "top" ? window.innerHeight - (style?.top ?? 0) : undefined,
        left: style?.left ?? -9999,
        maxHeight: style?.maxHeight,
        width: style?.width,
        visibility: style ? "visible" : "hidden",
      }}
      className={`z-[100] overflow-y-auto bg-card border border-border rounded-xl shadow-2xl animate-in fade-in ${className || ""}`}
    >
      {children}
    </div>,
    document.body
  );
}
