---
version: "alpha"
name: "Estilo Deep Learning High-Tech"
description: "High-tech AI platform landing page. Ideal for landing pages, modern websites. AI-ready template."
colors:
  primary: "#76B900"
  secondary: "#2A2A2A"
  tertiary: "#FFFFFF"
  neutral: "#4A4A4A"
  surface: "#00BFFF"
  accent: "#BDBDBD"
typography:
  h1:
    fontFamily: Roboto Mono
    fontSize: 2.5rem
    fontWeight: 700
  body-md:
    fontFamily: Roboto Mono
    fontSize: 1rem
    fontWeight: 400
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral}"
    padding: 12px
---

## Overview

High-tech AI platform landing page. Ideal for landing pages, modern websites. AI-ready template. The visual language of AI didn't emerge from design studios. It came from research papers. NVIDIA's green-black palette and angular geometry became shorthand for 'computational power' long before anyone thought to codify it. DeepMind went the other direction — clean, almost clinical whites with those signature node-and-edge diagrams that made neural architectures feel tangible. Both approaches worked because they solved the same problem: how do you make invisible intelligence visible?

Neural network diagrams crossed over from technical documentation into brand identity somewhere around 2016. Suddenly every ML startup had interconnected nodes in their hero section. The good ones abstracted it — subtle, geometric, suggestive of complexity without being literal. The bad ones looked like textbook figures with a gradient slapped on.

What solidified was an 'intelligence aesthetic': dark backgrounds suggesting depth, accent colors that pulse or glow (implying activity), and typography that leans monospace or geometric sans. It's a language that says 'something is thinking here.' The best implementations feel alive without being noisy — restrained motion, data-driven animation, interfaces that breathe.

- Density: 5/10 — Balanced
- Variance: 4/10 — Moderate
- Motion: 8/10 — Cinematic

- **Style:** High-Tech, Dark, Professional
- **Keywords:** AI, deep learning, accelerated computing, neural networks, data science, futuristic, powerful, precise, dark mode
- **Era:** 2026+ AI Dominance
- **Light/Dark:** ✗ No / ✓ Full

## Colors

- **Verde Vibrante** (#76B900) — Primary surface or dominant color
- **Carvão** (#2A2A2A) — Secondary surface or text color
- **Branco Puro** (#FFFFFF) — Light surface, card backgrounds
- **Cinza Frio** (#4A4A4A) — Secondary text, borders, muted elements
- **Azul Elétrico** (#00BFFF) — Secondary accent
- **Cinza Claro** (#BDBDBD) — Secondary text, borders, muted elements
- **Preto Profundo** (#1A1A1A) — Primary background surface
- **Verde Circuito** (#6EFA5F) — Success states, positive indicators

## Typography

- **Display / Hero:** Roboto Mono — Weight 700, tight tracking, used for headline impact
- **Body:** Roboto Mono — Weight 400, 16px/1.6 line-height, max 72ch per line
- **UI Labels / Captions:** Roboto Mono — 0.875rem, weight 500, slight letter-spacing
- **Monospace:** Roboto Mono — Used for code, metadata, and technical values

Scale:
- Hero: clamp(2.5rem, 5vw, 4rem)
- H1: 2.25rem
- H2: 1.5rem
- Body: 1rem / 1.6
- Small: 0.875rem

## Layout

- **Grid:** CSS Grid primary. Max-width containment: 1280px centered with 1.5rem side padding.
- **Spacing rhythm:** Balanced. Base unit: 0.5rem (8px).
- **Section vertical gaps:** clamp(4rem, 8vw, 8rem).
- **Hero layout:** Split-screen (text left, visual right).
- **Feature sections:** Zig-zag alternating text+image rows. No 3-equal-columns.
- **Mobile collapse:** All multi-column layouts collapse below 768px. No horizontal overflow.
- **z-index contract:** base (0) / sticky-nav (100) / overlay (200) / modal (300) / toast (500).

## Elevation & Depth

Animações de redes neurais, visualização de fluxo de dados, brilhos sutis, gradientes suaves, tipografia técnica, elementos 3D interativos (WebGL), micro-interações precisas.

- **Physics:** Spring — stiffness 120, damping 20. Confident, weighted transitions.
- **Entry animations:** Fade + translate-Y (16px → 0) over 540ms ease-out. Staggered cascades for lists: 120ms between items.
- **Hover states:** Scale(1.03) + shadow lift over 200ms.
- **Page transitions:** Fade + slide (300ms).
- **Performance:** Only transform and opacity animated. No layout-triggering properties.

## Shapes

Base corner radius: 8px. See rounded tokens in front matter for the full scale.

## Components

- **Primary Button:** Subtly rounded (0.5rem) shape. Accent color fill. Hover: 8% darken + subtle lift shadow. Active: -1px translate tactile press. Font weight 600. No outer glows.
- **Secondary / Ghost Button:** Outline variant. 1.5px border in muted color. Text in primary color. Hover: subtle background fill.
- **Cards:** Subtly rounded (0.5rem) corners. Surface background. Subtle shadow (0 2px 12px rgba(0,0,0,0.06)). 1px border stroke.
- **Inputs:** Label above input. 1px border stroke. Focus ring: 2px accent color offset 2px. Error text below in semantic red. No floating labels.
- **Navigation:** Primary surface background. Active item: accent color indicator. Font weight 500 when active.
- **Skeletons:** Shimmer animation matching component dimensions. No circular spinners.
- **Empty States:** Icon-based composition with descriptive text and action button.

## Do's and Don'ts

- No emojis in UI — use icon system only (Lucide, Heroicons)
- No pure white (#FFFFFF) backgrounds — use off-white or dark surfaces
- No oversaturated accent colors (saturation cap: 80%)
- No 3-column equal-width feature layouts — use zig-zag or asymmetric grid
- No `h-screen` — use `min-h-[100dvh]`
- No AI copywriting clichés: "Elevate", "Seamless", "Unleash", "Next-Gen"
- No broken external image links — use picsum.photos or inline SVG
- No generic lorem ipsum in demos

## Implementation notes (Vocal web UI)

- Tokens live in `theme.css` (`:root` custom properties) and are shared by the
  landing page (`index.html`) and the console (`app.html`).
- Tailwind via CDN; complex effects (glow, data-flow, backdrop-filter, neural
  canvas) are plain CSS/JS in `<style>`/`theme.css` — no build step.
- The hero "3D neural network" is a dependency-free canvas: a rotating 3D
  node/edge graph with perspective projection and pointer parallax (WebGL-class
  visual without a 600KB library). Feature cards use CSS `perspective: 1500px`
  tilt micro-interactions.
- Icons: inline SVG, Lucide-style 24x24 stroke paths. No emoji anywhere.
- All dynamic text in the console is rendered with `textContent` (no innerHTML
  interpolation of user/API data) — XSS-safe by construction.
- Landing is a pure open-source project page (no pricing/testimonials/company
  marketing): hero, asymmetric feature bento, quickstart terminal, project footer.
- Dual hosting: the same files run served by Vocal (`/ui`) and from GitHub Pages.
  Asset paths are relative; `js/connection.js` resolves the API base (same-origin
  when local, user's `http://localhost:8000` when hosted) and every request goes
  straight from the browser to that server. Server answers Chrome's Private
  Network Access preflight (`allow_private_network=True`).
- Mic UX mirrors the CLI (`vocal devices` / `--device`): every record path has a
  persisted microphone-source picker plus a live level meter and an
  idle / listening / hearing-voice indicator (`js/mic.js`).
