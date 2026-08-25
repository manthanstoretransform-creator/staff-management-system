/**
 * Monitra V2 design tokens.
 *
 * Categorical series colors are validated (lightness band, chroma floor, CVD
 * separation, normal-vision floor, contrast vs. white surface). Assign them by
 * slot order and never cycle past slot 6 — fold the tail into "Other" instead.
 */

export const brand = {
  cyan: "#22D3EE",
  blue: "#2563EB",
  violet: "#7C3AED",
  teal: "#0D9488",
  navy: "#0B1220",
  ink: "#0F172A",
  muted: "#64748B",
  subtle: "#94A3B8",
  line: "#E2E8F0",
  canvas: "#F8FAFC",
  surface: "#FFFFFF",
} as const;

/** Fixed-order categorical slots. Color follows the entity, never its rank. */
export const series = [
  "#2563EB", // 1 blue
  "#0D9488", // 2 teal
  "#7C3AED", // 3 violet
  "#D97706", // 4 amber
  "#DB2777", // 5 pink
  "#4D7C0F", // 6 olive
] as const;

/** Logo gradient, reused for the brand mark and hero accents only. */
export const brandGradient = "linear-gradient(135deg, #22D3EE 0%, #3B82F6 52%, #7C3AED 100%)";

export const fmtHours = (h: number) => `${Math.floor(h)}h ${Math.round((h % 1) * 60)}m`;
export const fmtNumber = (n: number) => n.toLocaleString("en-US");
