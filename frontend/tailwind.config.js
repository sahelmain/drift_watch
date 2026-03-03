/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        drift: {
          50: "#eef4ff",
          100: "#dae6ff",
          200: "#bdd4ff",
          300: "#90baff",
          400: "#5c94ff",
          500: "#3b6eff",
          600: "#1f45f5",
          700: "#1a35e1",
          800: "#1c2db6",
          900: "#1c2c8f",
          950: "#0f1635",
        },
        surface: {
          DEFAULT: "#0f1729",
          50: "#f0f4ff",
          100: "#e0e7f5",
          200: "#c3d0e8",
          300: "#8b9dc4",
          400: "#5e7299",
          500: "#3d5278",
          600: "#2c3d5e",
          700: "#1e2d4a",
          800: "#162037",
          900: "#0f1729",
          950: "#080d1a",
        },
      },
    },
  },
  plugins: [],
};
