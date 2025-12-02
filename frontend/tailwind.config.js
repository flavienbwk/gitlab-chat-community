/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        gitlab: {
          orange: '#fc6d26',
          purple: '#6b4fbb',
          blue: '#1f75cb',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
