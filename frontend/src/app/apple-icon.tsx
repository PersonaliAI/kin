import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a0a",
        }}
      >
        <span
          style={{
            fontFamily: "sans-serif",
            fontWeight: 700,
            fontSize: 110,
            color: "#fafafa",
            lineHeight: 1,
          }}
        >
          K
        </span>
      </div>
    ),
    { ...size },
  );
}
