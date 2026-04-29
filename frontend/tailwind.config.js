/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
    theme: {
        extend: {
            fontFamily: {
                sans: ['"DM Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
                heading: ['"Sora"', "ui-sans-serif", "system-ui", "sans-serif"],
                mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
            },
            borderRadius: {
                lg: "8px",
                md: "6px",
                sm: "4px",
            },
            colors: {
                jp: {
                    bg: "#FDFCF8",
                    surface: "#FFFFFF",
                    ink: "#1A1A1A",
                    sub: "#5C5C5C",
                    line: "#E0E0E0",
                    primary: "#a491d3",
                    primaryBorder: "#8170a9",
                    secondary: "#818aa3",
                    secondaryBorder: "#656c82",
                    output: "#c5dca0",
                    outputBorder: "#9db080",
                    input: "#f5f2b8",
                    inputBorder: "#c4c193",
                    note: "#f9dad0",
                    noteBorder: "#c7aea6",
                },
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
                popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
                primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
                secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
                muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
                accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
                destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
                border: "hsl(var(--border))",
                input: "hsl(var(--input))",
                ring: "hsl(var(--ring))",
            },
            keyframes: {
                "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
                "accordion-up": { from: { height: "var(--radix-accordion-content-height)" }, to: { height: "0" } },
                "fade-up": {
                    from: { opacity: "0", transform: "translateY(6px)" },
                    to: { opacity: "1", transform: "translateY(0)" },
                },
            },
            animation: {
                "accordion-down": "accordion-down 0.2s ease-out",
                "accordion-up": "accordion-up 0.2s ease-out",
                "fade-up": "fade-up 0.32s ease-out both",
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};
