import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        "canvas-soft": "var(--canvas-soft)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        accent: "var(--accent)",
        "accent-2": "var(--accent-2)",
        border: "var(--border)",
      },
      fontFamily: {
        display: ["Space Grotesk", "Manrope", "Segoe UI", "sans-serif"],
        body: ["IBM Plex Sans", "Manrope", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        panel: "0 18px 45px rgba(14, 21, 44, 0.14)",
      },
      keyframes: {
        riseIn: {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        riseIn: "riseIn 420ms ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
