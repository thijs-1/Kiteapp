/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'kite-pink': '#FF69B4',
        'kite-pink-dark': '#FF1493',
      },
    },
  },
  plugins: [],
}
