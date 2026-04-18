import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        prism: {
          bg: "#0b1020",
          panel: "#121a2f",
          accent: "#5eead4",
          warn: "#fbbf24",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
