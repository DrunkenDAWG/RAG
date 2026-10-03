/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        canvas: "#09090b",
        surface: "#121214",
        subtle: "#18181b",
        border: {
          subtle: "#27272a",
          strong: "#3f3f46",
        },
        text: {
          primary: "#ffffff",
          secondary: "#a1a1aa",
          muted: "#71717a",
        },
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(0, 0, 0, 0.4)",
        dropdown: "0 4px 20px 0 rgba(0, 0, 0, 0.6)",
        modal: "0 16px 40px -8px rgba(0, 0, 0, 0.8), 0 0 0 1px #27272a",
      },
    },
  },
  plugins: [],
};
