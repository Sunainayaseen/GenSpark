# GenSpark Builds — Project Documentation

## 1. Overview

**GenSpark Builds** is a React single-page application (SPA) for AI-powered PC customization and ordering in Pakistan. Users can get build recommendations via an AI chatbot, customize parts, select local vendors, place orders, and track delivery. The app supports three roles: **Buyer**, **Vendor**, and **Admin**.

---

## 2. Tech Stack

| Category    | Technology |
|------------|------------|
| Framework  | React 19 |
| Build      | Vite 7 |
| Routing    | React Router DOM 7 |
| Language   | JavaScript (JSX) |
| Styling    | CSS (CSS variables, no preprocessor) |
| Fonts      | Google Fonts (Inter, Bebas Neue) |

---

## 3. Getting Started

### Prerequisites

- Node.js (v18+ recommended)
- npm or yarn

### Install

```bash
cd my-react-app
npm install
```

### Run (development)

```bash
npm run dev
```

Runs at `http://localhost:5173` (or next available port).

### Build (production)

```bash
npm run build
```

Output: `dist/`

### Preview production build

```bash
npm run preview
```

### Lint

```bash
npm run lint
```

---

## 4. Project Structure

```
my-react-app/
├── public/                 # Static assets (logos, images)
├── src/
│   ├── assets/             # Images, videos, SVGs
│   ├── components/         # Reusable UI components
│   ├── constants/         # Order stages, config
│   ├── context/            # React Context (App, Auth, Cart)
│   ├── hooks/              # Custom hooks (e.g. useScrollAnimation)
│   ├── pages/              # Route-level page components
│   ├── utils/              # scrollAnimations, parallax
│   ├── App.jsx             # Router, providers, animated routes
│   ├── App.css             # Global transitions
│   ├── main.jsx            # Entry, React root
│   └── index.css           # CSS variables, reset, scroll animations
├── index.html
├── package.json
├── vite.config.js
└── DOCUMENTATION.md        # This file
```

---

## 5. Routes & Pages

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `Landing` | Home: hero, features, top picks, reviews, contact strip |
| `/chatbot` | `Chatbot` | AI build assistant: chat, sidebar filters, quick chips, build suggestions |
| `/builds` | `BuildSuggestions` | Suggested builds (Performance, Balanced, Budget); compare, customize, proceed |
| `/configurator` | `BuildConfigurator` | Part-by-part customization with compatibility checks |
| `/vendor-assignment` | `VendorAssignment` | Choose city-based vendor for selected build |
| `/order/:id` | `OrderStatus` | Order tracking and timeline |
| `/vendor/dashboard` | `VendorDashboard` | Vendor view: orders, assembly, uploads |
| `/admin` | `AdminPanel` | Admin: orders, vendors, approvals |
| `/blogs` | `Blogs` | Blog listing page |
| `/contact` | `Contact` | Contact form, email/phone/location |
| `/about` | `About` | About GenSpark, team, mission |
| `/how-it-works` | `HowItWorks` | Timeline flow: 10 steps from signup to feedback |

All routes are wrapped in `Layout` (header + footer). Page transitions use `.main-content` and `.page-enter` / `.page-enter-active` in `App.jsx`.

---

## 6. Components

| Component | File(s) | Purpose |
|-----------|---------|---------|
| `Layout` | `Layout.jsx`, `Layout.css` | Header (logo, nav, cart, login/signup), main slot, footer |
| `AIChatbot` | `AIChatbot.jsx`, `AIChatbot.css` | Floating chat widget: minimize button, open panel, messages, quick actions, link to `/chatbot` |
| `AuthModal` | `AuthModal.jsx`, `AuthModal.css` | Login / Sign up modal |
| `CartDropdown` | `CartDropdown.jsx`, `CartDropdown.css` | Cart icon dropdown with items |
| `HeroSlideshow` | `HeroSlideshow.jsx`, `HeroSlideshow.css` | Landing hero carousel/slideshow |

---

## 7. Context & State

### AppContext (`context/AppContext.jsx`)

- **userRequirements**: purpose, budget, city, preferences, assembly (from Chatbot sidebar).
- **selectedBuild**: build chosen for configurator/vendor.
- **builds**: list of suggested builds (e.g. from Chatbot).
- **orders**: list of user orders (demo data supported).
- **user**: current user (if logged in).
- **vendors**: list of vendors (city, rating, cost, ETA).
- **setUserRequirements**, **setSelectedBuild**, **setBuilds**, etc.

Used by: Chatbot, BuildSuggestions, BuildConfigurator, VendorAssignment, OrderStatus.

### AuthContext (`context/AuthContext.jsx`)

- Auth state and login/signup helpers (structure for integration with backend).

### CartContext (`context/CartContext.jsx`)

- **cartCount**, **isCartOpen**, **setIsCartOpen**, **addToCart**, cart items.
- Used by Layout (cart icon, dropdown) and build pages (Add to Cart).

---

## 8. Styling & Theme

### CSS variables (`src/index.css`)

- **Primary (teal):** `--primary: #22A39F`, `--primary-light: #2ebdb8`, `--primary-dark: #1a8582`, `--primary-rgb: 34, 163, 159`.
- **Backgrounds:** `--bg-primary: #F3EFE0` (cream), `--bg-secondary: #434242`, `--bg-tertiary: #2d2d2d`, `--color-darkest: #222222`.
- **Text:** `--text-primary`, `--text-secondary`, `--text-on-light`, `--text-on-light-secondary`.
- **Spacing:** `--spacing-xs` through `--spacing-2xl`.
- **Radius:** `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-xl`.
- **Transitions:** `--transition`.

### Scroll animations

- **Utility:** `utils/scrollAnimations.js` — `initScrollAnimations()`.
- **Usage:** `data-scroll="fade-up"`, `data-delay="100"`, `data-duration="700"`, `data-once="true"`.
- **Stagger:** Parent with class `scroll-stagger`; children animate when parent gets `scroll-stagger-visible` (IntersectionObserver).
- **Classes:** `.scroll-animate-fade-up`, `.scroll-animate-fade`, `.animate-in`, etc. defined in `index.css`.

### Parallax

- **Utility:** `utils/parallax.js` — `initParallax()` for elements with `data-parallax` (or similar).

---

## 9. Utilities

| File | Purpose |
|------|---------|
| `utils/scrollAnimations.js` | IntersectionObserver-based scroll animations; supports `data-scroll`, `data-delay`, `data-duration`, and `scroll-stagger` containers. |
| `utils/parallax.js` | Parallax effect for designated elements. |

---

## 10. Constants

| File | Purpose |
|------|---------|
| `constants/orderStages.js` | Order lifecycle stages (e.g. `ORDER_STAGES`) used in OrderStatus, VendorDashboard, AdminPanel, notifications. |

---

## 11. Key Features by Page

### Landing (`/`)

- Hero with slideshow.
- “Why Choose GenSpark?” feature grid (4 cards).
- “Top Picks for Every Need” build cards.
- “What Our Customers Say” reviews (stats + review cards).
- “Contact Us” strip with email/phone/location and “Send us a Message” form.

### Chatbot (`/chatbot`)

- Center: chat messages, welcome message, quick chips (Gaming · 100k, Office · 50k, Content · 150k).
- Sidebar: purpose (select), budget (PKR), city; “Get recommendations” button.
- Build suggestions rendered as cards (customize, add to cart, proceed).
- Logo and “Back to home” in center header.

### Build Suggestions (`/builds`)

- One-screen layout (no scroll): header + 3 build cards (Performance, Balanced, Budget).
- Each card: type, title, price, performance bar, wattage, ETA, parts list, Customize / Add to Cart / Proceed.
- Compare mode: select up to 2 builds.
- Cream background; teal accents.

### Build Configurator (`/configurator`)

- Customize selected build: replace parts, filters, real-time compatibility and price.

### Vendor Assignment (`/vendor-assignment`)

- Select a city-based vendor for the chosen build; view ratings, assembly cost, ETA.

### Order Status (`/order/:id`)

- Order timeline and status (e.g. pending, vendor-assigned, assembling, shipped, delivered).

### How It Works (`/how-it-works`)

- No cards; vertical **timeline** with 10 steps.
- Each step: number circle (teal) + title + short description.
- Top strip: “End-to-end flow” summary.
- Single CTA: “Start Your Build” → `/chatbot`.

### Contact (`/contact`)

- Contact info cards (Email, Phone, Location) with SVG icons.
- “Send us a Message” form: name, email, phone, subject, message; submit handler (e.g. alert).

---

## 12. Assets & Public Files

- **Logo:** `public/gs-logo.png` (and fallbacks: `Gemini_Generated_Image_...png`) used in Layout and Chatbot header.
- **Fonts:** Google Fonts (Inter, Bebas Neue) linked in `index.html`.
- **Videos:** Placeholder under `src/assets/videos/` (see README there if present).

---

## 13. Browser Support

- Modern evergreen browsers (Chrome, Firefox, Safari, Edge).
- CSS uses variables and some modern properties; `-webkit-` prefixes used where needed (e.g. mask).

---

## 14. Environment & Deployment

- No `.env` required for basic run; Vite uses `import.meta.env` if needed.
- Build: `npm run build`; deploy `dist/` to any static host (Vercel, Netlify, etc.).
- For API integration, add base URL and keys via environment variables and use in context or API modules.

---

## 15. Summary

GenSpark Builds is a React + Vite SPA with React Router, global state via Context (App, Auth, Cart), scroll and parallax utilities, and a teal/cream theme. Pages cover landing, AI chatbot, build suggestions, configurator, vendor selection, order tracking, vendor dashboard, admin panel, blogs, contact, about, and how-it-works. This document serves as the central reference for structure, routes, components, styling, and features.
