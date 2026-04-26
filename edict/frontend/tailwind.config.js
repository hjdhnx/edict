/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        imperial: {
          50: '#fef7ed',
          100: '#fdecd4',
          200: '#fad5a8',
          300: '#f7b671',
          400: '#f38d38',
          500: '#f07012',
          600: '#e15808',
          700: '#bb4009',
          800: '#95330f',
          900: '#792c10',
        },
        dynasty: {
          50: '#fdf4f3',
          100: '#fce8e4',
          200: '#fad4ce',
          300: '#f5b5ab',
          400: '#ee8a7a',
          500: '#e25f4d',
          600: '#cf4430',
          700: '#ae3624',
          800: '#903022',
          900: '#782d23',
        },
      },
    },
  },
  plugins: [],
};
