import type { Config } from "tailwindcss";

/**
 * CastIron — "Foundry Control Room" design system.
 * Palette forged from the audited brand assets (docs/icon.svg):
 *   coal    — near-black iron backgrounds
 *   iron    — slate steel lines & muted text
 *   forge   — emerald "ALL GREEN" signal (brand primary)
 *   ember   — molten amber failover accent (CTAs, chaos)
 *   danger  — outage red
 *   b2      — Backblaze red (sponsor chips only)
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        coal: {
          950: "#070B0E",
          900: "#0B1218",
          850: "#0E171E",
          800: "#12202B",
        },
        iron: {
          DEFAULT: "rgba(148,163,184,0.14)",
          strong: "rgba(148,163,184,0.28)",
          text: "#8FA3B8",
        },
        fg: "#E7EDF3",
        forge: {
          300: "#6EE7B7",
          400: "#34D399",
          500: "#10B981",
          600: "#059669",
        },
        ember: {
          300: "#FCD34D",
          400: "#FBBF24",
          500: "#F59E0B",
          600: "#D97706",
        },
        danger: "#EF4444",
        b2: "#E21E29",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      letterSpacing: {
        widest2: "0.28em",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(24px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        blink: {
          "0%, 49%": { opacity: "1" },
          "50%, 100%": { opacity: "0" },
        },
        "ember-pulse": {
          "0%, 100%": { boxShadow: "0 0 24px 0 rgba(245,158,11,0.35)" },
          "50%": { boxShadow: "0 0 48px 6px rgba(245,158,11,0.55)" },
        },
        "signal-ping": {
          "0%": { transform: "scale(0.9)", opacity: "0.9" },
          "70%": { transform: "scale(1.9)", opacity: "0" },
          "100%": { transform: "scale(1.9)", opacity: "0" },
        },
        marquee: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-50%)" },
        },
        "float-slow": {
          "0%, 100%": { transform: "translateY(0) rotate(var(--tilt, 0deg))" },
          "50%": { transform: "translateY(-10px) rotate(var(--tilt, 0deg))" },
        },
      },
      animation: {
        rise: "rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both",
        blink: "blink 1.1s step-end infinite",
        "ember-pulse": "ember-pulse 2.6s ease-in-out infinite",
        "signal-ping": "signal-ping 2.2s cubic-bezier(0, 0, 0.2, 1) infinite",
        marquee: "marquee 36s linear infinite",
        "float-slow": "float-slow 7s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
