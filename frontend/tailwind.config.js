/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        slate: {
          950: "#0a0f1a",
        },
      },
      typography: {
        DEFAULT: {
          css: {
            color: "#e2e8f0",
            maxWidth: "none",
          },
        },
      },
    },
  },
  plugins: [],
};
