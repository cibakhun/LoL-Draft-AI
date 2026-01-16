/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'neon-blue': '#00f0ff',
        'void-purple': '#7d00ff',
        'glass-border': 'rgba(255, 255, 255, 0.05)',
        'bg-dark': '#050510',
        'bg-panel': 'rgba(20, 20, 30, 0.6)',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      animation: {
        'slide-in': 'slideIn 0.3s ease-out forwards',
        'pulse-glow': 'pulseGlow 2s infinite',
      },
      keyframes: {
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseGlow: {
          '0%, 100%': { textShadow: '0 0 5px rgba(0, 240, 255, 0.5)' },
          '50%': { textShadow: '0 0 20px rgba(0, 240, 255, 0.9)' },
        }
      }
    },
  },
  plugins: [],
}
