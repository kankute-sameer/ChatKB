/**
 * SINGLE SOURCE OF TRUTH for UI design.
 * Edit values here only. Tailwind and components read from this file.
 * Do not hardcode colors, spacing, radii, or type sizes in components or CSS.
 */

export const tokens = {
  spacing: {
    0: "0px",
    px: "1px",
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    5: "20px",
    6: "24px",
    8: "32px",
    12: "48px",
    16: "64px",
    20: "80px",
    "agent-hero": "144px",
    title: "11px",
    icon: "20px",
    row: "40px",
    /** Horizontal inset for rounded-lg composer (matches borderRadius.lg). */
    composer: "28px",
  },
  borderRadius: {
    none: "0px",
    DEFAULT: "8px",
    lg: "25px",
    full: "9999px",
  },
  colors: {
    transparent: "transparent",
    current: "currentColor",
    inherit: "inherit",
    white: "#FFFFFF",
    ink: {
      DEFAULT: "#141414",
      muted: "#484848",
      placeholder: "#8E8E8E",
    },
    gray: {
      50: "#FAFAFA",
      fill: "#F3F3F3",
      100: "#F5F5F5",
      200: "#EEEEEE",
      300: "#E5E5E5",
      400: "#A3A3A3",
      500: "#737373",
      600: "#525252",
      700: "#404040",
      800: "#262626",
      900: "#171717",
    },
    accent: {
      DEFAULT: "#2563EB",
      foreground: "#FFFFFF",
      muted: "#EFF4FF",
    },
    orbit: "#8B8B8B",
    status: {
      success: "#15803D",
      "success-foreground": "#15803D",
      "success-muted": "#DCFCE7",
      personal: "#525252",
      "personal-foreground": "#525252",
      "personal-muted": "#F5F5F5",
    },
    avatar: {
      blue: "#3B82F6",
      red: "#E11D48",
    },
    background: "#FFFFFF",
    foreground: "#141414",
    sidebar: "#FFFFFF",
    border: "#EEEEEE",
    input: "#EEEEEE",
    ring: "#2563EB",
    card: {
      DEFAULT: "#FFFFFF",
      foreground: "#141414",
    },
    popover: {
      DEFAULT: "#FFFFFF",
      foreground: "#141414",
    },
    primary: {
      DEFAULT: "#2563EB",
      foreground: "#FFFFFF",
    },
    secondary: {
      DEFAULT: "#F5F5F5",
      foreground: "#141414",
    },
    muted: {
      DEFAULT: "#F5F5F5",
      foreground: "#484848",
    },
    destructive: {
      DEFAULT: "#DC2626",
      foreground: "#FFFFFF",
    },
  },
  fontFamily: {
    sans: ["Lexend", "ui-sans-serif", "system-ui", "sans-serif"],
    serif: ['"Source Serif 4"', "Georgia", "ui-serif", "serif"],
  },
  fontSize: {
    xs: ["12px", { lineHeight: "16px" }],
    connect: ["13px", { lineHeight: "20px" }],
    sm: ["14px", { lineHeight: "20px" }],
    nav: ["16px", { lineHeight: "22px" }],
    base: ["16px", { lineHeight: "24px" }],
    composer: ["18px", { lineHeight: "26px" }],
    lg: ["18px", { lineHeight: "28px" }],
    brand: ["24px", { lineHeight: "30px" }],
    title: ["20px", { lineHeight: "28px" }],
    xl: ["24px", { lineHeight: "32px" }],
    hero: ["40px", { lineHeight: "50px" }],
    "2xl": ["32px", { lineHeight: "40px" }],
  },
  fontWeight: {
    light: "300",
    ui: "350",
    normal: "400",
    medium: "500",
    hero: "500",
  },
  boxShadow: {
    none: "none",
    soft: "0 8px 28px 0 rgb(0 0 0 / 0.12)",
  },
  width: {
    sidebar: "275px",
    "sidebar-collapsed": "64px",
    panel: "384px",
    menu: "160px",
    icon: "20px",
  },
  height: {
    row: "40px",
    icon: "20px",
  },
  maxWidth: {
    composer: "768px",
    content: "960px",
    login: "400px",
  },
  motion: {
    easeOut: "cubic-bezier(0.16, 1, 0.3, 1)",
    orbit: "cubic-bezier(0.5, 0, 0.5, 1)",
    duration: {
      color: "150ms",
      enter: "500ms",
      card: "200ms",
      orbit: "1.4s",
      orbitReduced: "3s",
    },
    enterY: "8px",
    staggerMs: 40,
  },
} as const;

export const avatarClass = {
  blue: "bg-avatar-blue",
  red: "bg-avatar-red",
} as const;

export type AvatarColor = keyof typeof avatarClass;
