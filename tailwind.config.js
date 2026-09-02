//tailwind.config.js
export default {
  content: [
    "templates/**/*.html",
    "templates/**/*.js",
    "static/**/*.js",
    "static/**/*.html",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        aura: { 950: '#090a0f' },
        neon: {
          cyan: '#00f5d4',
          magenta: '#f72585',
          violet: '#7b2cbf',
          emerald: '#10b981',
          amber: '#f59e0b',
        }
      }
    }
  },
}