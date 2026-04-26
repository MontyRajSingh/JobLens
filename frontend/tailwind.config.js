/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          400: '#E6FF55', // Electric Lime
          500: '#D4FF00', 
          600: '#BCE600',
          accent: '#FF007F', // Hot Pink
        },
        surface: {
          800: '#1A1A1A',
          900: '#0A0A0A',
          950: '#000000',
        }
      },
      fontFamily: {
        display: ['Oswald', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
        sans: ['"IBM Plex Mono"', 'monospace'], // Mono default for terminal vibe
      },
      boxShadow: {
        'brutal': '4px 4px 0px 0px rgba(212, 255, 0, 1)',
        'brutal-white': '4px 4px 0px 0px rgba(255, 255, 255, 1)',
        'brutal-pink': '4px 4px 0px 0px rgba(255, 0, 127, 1)',
        'brutal-lg': '8px 8px 0px 0px rgba(212, 255, 0, 1)',
      }
    },
  },
  plugins: [],
}
