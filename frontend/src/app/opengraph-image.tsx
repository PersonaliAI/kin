import { ImageResponse } from "next/og";

export const alt = "Kin — AI Personal Assistant in Telegram";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const ORANGE = "#f97316";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 80,
          background: "#0a0a0a",
          backgroundImage: `radial-gradient(ellipse 900px 500px at 70% -10%, ${ORANGE}33, transparent 65%)`,
          fontFamily: "sans-serif",
        }}
      >
        {/* KinMark + wordmark, matching src/components/kin-mark.tsx */}
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div
            style={{
              width: 88,
              height: 88,
              borderRadius: 20,
              background: "#0a0a0a",
              border: "1px solid rgba(255,255,255,0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span
              style={{
                fontSize: 42,
                fontWeight: 700,
                color: "#fafafa",
                lineHeight: 1,
              }}
            >
              K
            </span>
          </div>
          <span style={{ fontSize: 44, fontWeight: 700, color: "#ffffff" }}>
            Kin
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontSize: 78,
              fontWeight: 700,
              color: "#ffffff",
              lineHeight: 1.12,
              letterSpacing: "-0.02em",
            }}
          >
            <span>The assistant that</span>
            <span style={{ display: "flex" }}>
              actually{"\u00A0"}
              <span style={{ color: ORANGE }}>does things</span>.
            </span>
          </div>
          <span style={{ fontSize: 32, color: "rgba(255,255,255,0.55)" }}>
            Your AI personal assistant in Telegram
          </span>
        </div>

        <span style={{ fontSize: 24, color: "rgba(255,255,255,0.35)" }}>
          kin.personaliai.com
        </span>
      </div>
    ),
    { ...size },
  );
}
