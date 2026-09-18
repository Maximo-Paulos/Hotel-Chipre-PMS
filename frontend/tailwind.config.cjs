/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Petrol navy, from the logo's dark half. A real hue, not a tinted
        // black -- it has to sit next to teal without going muddy.
        ink: {
          50: "#eef3f4",
          100: "#d3e0e2",
          200: "#a5c0c5",
          300: "#6f959d",
          400: "#3f6b75",
          500: "#204c57",
          600: "#153944",
          700: "#0f2c36",
          800: "#0b2029",
          900: "#071a22",
          950: "#04121a"
        },
        // Teal, sampled from the logo's chip gradient. This is the brand
        // colour the product was always supposed to have; the old `brand`
        // ramp was Tailwind's `sky` copied verbatim.
        brand: {
          50: "#eafaf6",
          100: "#c9f2e8",
          200: "#95e5d3",
          300: "#5bd0ba",
          400: "#2bb39c",
          500: "#12a594",
          600: "#0d7d6e",
          700: "#0c6459",
          800: "#0d4f48",
          900: "#0c413c",
          950: "#04251f"
        },
        // Brass: the front-desk bell, the key fobs, the luggage cart. Used
        // only to mark money and the single most important action on a
        // screen -- never as decoration.
        brass: {
          100: "#f7ecd9",
          200: "#eed7b0",
          300: "#e3bd80",
          400: "#d4a259",
          500: "#c08a3e",
          600: "#a06d2e",
          700: "#7c5326",
          800: "#5c3e21"
        },
        paper: {
          DEFAULT: "#f5f7f6",
          raised: "#ffffff",
          sunk: "#eaeeed"
        }
      },
      fontFamily: {
        // Archivo carries the marketing voice: it has a width axis, so
        // headlines can be set expanded like hotel wayfinding signage.
        display: ["Archivo Variable", "Archivo", "system-ui", "sans-serif"],
        // Inter is what the product itself is set in, so every recreated
        // product surface on the page uses it and reads as the real app.
        sans: ["Inter Variable", "Inter", "system-ui", "-apple-system", "sans-serif"]
      },
      fontSize: {
        // Display sizes carry their own tracking; at these sizes the default
        // spacing reads loose and amateur.
        "display-sm": ["2.25rem", { lineHeight: "1.08", letterSpacing: "-0.02em" }],
        "display-md": ["3rem", { lineHeight: "1.04", letterSpacing: "-0.025em" }],
        "display-lg": ["3.75rem", { lineHeight: "1.0", letterSpacing: "-0.03em" }],
        "display-xl": ["4.75rem", { lineHeight: "0.96", letterSpacing: "-0.035em" }]
      },
      spacing: {
        // The rack column: every night in the occupancy grid is this wide,
        // and the page's vertical rules line up with it.
        rack: "3.5rem"
      },
      borderRadius: {
        // Three radii with distinct jobs, so hierarchy survives: chips,
        // controls and panels. Anything else is a drift.
        chip: "0.375rem",
        control: "0.625rem",
        panel: "1rem",
        // The pages were written against Tailwind's stock scale and spread
        // two jobs across six radii (rounded-lg x703, -xl x145, -2xl x90,
        // -3xl x19 ...). The stock names are remapped onto the three system
        // radii so every existing class lands on one of them: small bits are
        // chips, `lg` is a control, anything larger is a panel.
        sm: "0.375rem",
        DEFAULT: "0.375rem",
        md: "0.375rem",
        lg: "0.625rem",
        xl: "1rem",
        "2xl": "1rem",
        "3xl": "1rem"
      },
      boxShadow: {
        // One elevation scale. The old page had a different arbitrary
        // rgba shadow inline on almost every card.
        raise: "0 1px 2px rgba(7,26,34,0.06), 0 2px 8px rgba(7,26,34,0.04)",
        float: "0 12px 32px -12px rgba(7,26,34,0.22), 0 2px 6px rgba(7,26,34,0.06)",
        deep: "0 32px 64px -24px rgba(4,18,26,0.55)",
        // Same remap as the radii: resting surfaces raise, popovers and
        // drawers float, modals sit deep. Stock shadows are neutral black;
        // these are tinted with the ink hue so depth reads as one light.
        sm: "0 1px 2px rgba(7,26,34,0.06), 0 2px 8px rgba(7,26,34,0.04)",
        DEFAULT: "0 1px 2px rgba(7,26,34,0.06), 0 2px 8px rgba(7,26,34,0.04)",
        md: "0 12px 32px -12px rgba(7,26,34,0.22), 0 2px 6px rgba(7,26,34,0.06)",
        lg: "0 12px 32px -12px rgba(7,26,34,0.22), 0 2px 6px rgba(7,26,34,0.06)",
        xl: "0 12px 32px -12px rgba(7,26,34,0.22), 0 2px 6px rgba(7,26,34,0.06)",
        "2xl": "0 32px 64px -24px rgba(4,18,26,0.55)"
      },
      transitionTimingFunction: {
        // A single curve for the whole site. Slightly overshoot-free so
        // panels settle rather than bounce.
        rack: "cubic-bezier(0.22, 0.61, 0.36, 1)"
      }
    }
  },
  plugins: []
};
