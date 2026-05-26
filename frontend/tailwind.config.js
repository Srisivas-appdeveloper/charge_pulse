/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        health: {
          ok: "#10B981",
          warn: "#F59E0B",
          danger: "#F97316",
          critical: "#EF4444",
        },
      },
    },
  },
  plugins: [],
};
