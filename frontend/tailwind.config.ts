import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";
import { tokens } from "./src/design/tokens";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    spacing: tokens.spacing,
    borderRadius: tokens.borderRadius,
    colors: tokens.colors,
    fontFamily: tokens.fontFamily,
    fontSize: tokens.fontSize,
    fontWeight: tokens.fontWeight,
    boxShadow: tokens.boxShadow,
    extend: {
      width: tokens.width,
      minWidth: {
        sidebar: tokens.width.sidebar,
        "sidebar-collapsed": tokens.width["sidebar-collapsed"],
        panel: tokens.width.panel,
        menu: tokens.width.menu,
      },
      height: tokens.height,
      maxWidth: tokens.maxWidth,
      keyframes: {
        enter: {
          from: {
            opacity: "0",
            transform: `translateY(${tokens.motion.enterY})`,
          },
          to: {
            opacity: "1",
            transform: "translateY(0)",
          },
        },
      },
      animation: {
        enter: `enter ${tokens.motion.duration.enter} ${tokens.motion.easeOut}`,
        "enter-stagger": `enter ${tokens.motion.duration.card} ${tokens.motion.easeOut} backwards`,
      },
      transitionDuration: {
        color: tokens.motion.duration.color,
      },
      transitionTimingFunction: {
        motion: tokens.motion.easeOut,
      },
    },
  },
  plugins: [animate],
} satisfies Config;
