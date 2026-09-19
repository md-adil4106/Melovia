import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          bg: "var(--color-ink-bg)",
          surface: "var(--color-ink-surface)",
          elevated: "var(--color-ink-elevated)",
          border: "var(--color-ink-border)",
          text: "var(--color-ink-text)",
          muted: "var(--color-ink-muted)",
        },
        warm: {
          DEFAULT: "var(--color-accent-warm)",
          hover: "var(--color-accent-warm-hover)",
          subtle: "var(--color-accent-warm-subtle)",
        },
        cool: {
          DEFAULT: "var(--color-accent-cool)",
          hover: "var(--color-accent-cool-hover)",
          subtle: "var(--color-accent-cool-subtle)",
        },
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        full: "var(--radius-full)",
      },
      spacing: {
        xs: "var(--spacing-xs)",
        sm: "var(--spacing-sm)",
        md: "var(--spacing-md)",
        lg: "var(--spacing-lg)",
        xl: "var(--spacing-xl)",
        "2xl": "var(--spacing-2xl)",
      },
      transitionDuration: {
        fast: "var(--motion-fast)",
        normal: "var(--motion-normal)",
        slow: "var(--motion-slow)",
      },
      fontFamily: {
        display: ["var(--font-serif-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
