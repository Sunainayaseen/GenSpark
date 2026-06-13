# GenSpark — System Architecture Diagram (Booklet Edition)

> **Project:** GenSpark — AI-powered PC component e-commerce, assembly & delivery platform
> **Stack:** React (Vite) frontend · Flask modular backend · MySQL/SQLite · YOLOv8 vision · Stripe payments
> **Verified against source code** — `Dashboard/` (modular backend) + `my-react-app/` (frontend).

All diagrams below are written in **Mermaid**. They render automatically in GitHub, VS Code (with a Markdown preview / Mermaid extension), and most documentation tools. For a print booklet you can paste any block into [mermaid.live](https://mermaid.live) and export PNG/SVG.

---

## 1. High-Level System Architecture

```mermaid
flowchart TB
    User(["👤 User<br/>Customer · Vendor · Rider · Admin"])

    subgraph Client["🖥️ FRONTEND — React 19 + Vite (Vercel)"]
        direction TB
        Public["Customer Portal<br/>Landing · Components · Builds<br/>Configurator · Cart · Checkout · Orders"]
        AIUI["AI Features<br/>Chatbot · Build Configurator<br/>Image Detect Overlay"]
        DashWrap["Dashboard Wrappers (iframe)<br/>/admin · /vendor/dashboard"]
    end

    subgraph Server["⚙️ BACKEND — Flask (App Factory) · port 5000 (Railway)"]
        direction TB
        subgraph API["REST API — JSON"]
            ApiBp["/api  — orders, cart, components,<br/>detect, recommend-build, tracking"]
            EcomBp["/api/ecom — products, cart,<br/>orders, admin approval"]
        end
        subgraph SSR["Server-Rendered Dashboards — Jinja2"]
            AdminBp["/admin — users, components,<br/>orders, vendors, QA, reports"]
            VendorBp["/vendor — inventory, orders,<br/>assembly, shipments, earnings"]
            RiderBp["/rider — deliveries, live GPS, earnings"]
        end
        AuthBp["/auth — login · signup · logout<br/>Flask-Login + JWT + Bcrypt + RBAC"]
    end

    subgraph AI["🧠 AI / ML"]
        YOLO["YOLOv8 (best.pt)<br/>detect: mouse · keyboard · monitor · RAM"]
        Reco["Build Recommender<br/>budget + purpose → real components"]
    end

    subgraph Ext["☁️ External Services"]
        Stripe["💳 Stripe<br/>PaymentIntents (PKR)"]
        Mail["✉️ SMTP (optional)"]
    end

    DB[("🗄️ Database<br/>MySQL (prod) / SQLite (dev)<br/>~30 tables")]

    User --> Client
    Public -->|"axios / fetch + JWT"| API
    AIUI -->|"/api/detect · /api/recommend-build"| API
    DashWrap -->|"iframe + session cookie"| SSR
    Client -->|"POST /auth/login"| AuthBp

    API --> AuthBp
    SSR --> AuthBp
    ApiBp --> YOLO
    ApiBp --> Reco
    ApiBp --> Stripe
    AuthBp --> Mail

    API --> DB
    SSR --> DB
    AuthBp --> DB
```

---

## 2. Backend Module / Blueprint Architecture

Verified from [Dashboard/app/__init__.py](Dashboard/app/__init__.py) (`create_app` factory + blueprint registration).

```mermaid
flowchart LR
    Run["run.py<br/>create_app() · host 0.0.0.0 · port 5000<br/>preloads YOLO best.pt"] --> Factory

    subgraph Factory["app/__init__.py — Application Factory"]
        direction TB
        Ext1["SQLAlchemy · Bcrypt · Flask-Login<br/>Flask-CORS (credentials) · CSRF (exempt /api)"]
        Schema["ensure_database_schema()<br/>+ legacy migrations"]
    end

    Factory --> B1 & B2 & B3 & B4 & B5 & B6

    B1["auth_bp<br/>/auth"]
    B2["admin_bp<br/>/admin"]
    B3["vendor_bp<br/>/vendor"]
    B4["rider_bp<br/>/rider"]
    B5["api_bp<br/>/api"]
    B6["ecom_bp<br/>/api/ecom"]

    B5 --> AiRoutes["ai_build_routes.py<br/>/api/recommend-build"]
    B5 --> Yolo["yolo_weights.py<br/>/api/detect/component"]
    B5 --> Stripe2["stripe_checkout.py<br/>/api/create-payment-intent<br/>/api/order/complete-checkout"]

    B2 & B3 & B4 --> Tpl["templates/<br/>admin · vendor · rider (Jinja2)"]
    B1 & B2 & B3 & B4 & B5 & B6 --> Models["app/models/<br/>SQLAlchemy ORM"]
```

**Blueprints (verified):**

| Blueprint | Prefix | Responsibility |
|-----------|--------|----------------|
| `auth_bp` | `/auth` | Login / signup / logout, role-based redirect |
| `admin_bp` | `/admin` | Users, components, categories, brands, builds, orders, vendors, QA, reports |
| `vendor_bp` | `/vendor` | Profile, inventory, orders, assembly tracking, shipments, earnings |
| `rider_bp` | `/rider` | Deliveries, live GPS tracking, earnings |
| `api_bp` | `/api` | Orders, cart, component search, YOLO detect, AI recommend, Stripe, tracking |
| `ecom_bp` | `/api/ecom` | Products, cart→approval→order flow, admin order management |

---

## 3. Order Lifecycle — Data Flow (Sequence)

The platform's core multi-actor workflow: customer order → admin approval → vendor assembly → rider delivery.

```mermaid
sequenceDiagram
    actor C as Customer (React)
    participant API as Flask /api
    participant DB as Database
    participant S as Stripe
    actor A as Admin
    actor V as Vendor
    actor R as Rider

    C->>API: POST /api/create-payment-intent (amount PKR)
    API->>S: Create PaymentIntent
    S-->>C: client_secret → confirm card
    C->>API: POST /api/order/complete-checkout (payment_intent_id, items)
    API->>S: Retrieve intent (verify succeeded)
    API->>DB: Create Order + OrderItems + Payment (status=pending)
    API-->>C: order_number

    A->>API: POST /api/orders/{id}/admin-approve
    API->>DB: status → approved → VendorOrders created

    V->>API: vendor order: assigned → accepted → assembling
    V->>API: POST assembly update (+ proof image)
    API->>DB: AssemblyTracking + QaCheck

    R->>API: request-pickup → start-tracking
    R->>API: POST /api/tracking/ping (lat,lng)
    API->>DB: RiderLocationPing (live GPS trail)
    R->>API: delivered
    API->>DB: Shipment delivered + Notification
```

---

## 4. Database — Entity Relationship (Core Tables)

Verified from [Dashboard/app/models/](Dashboard/app/models/) (~30 models). Showing the core relationships.

```mermaid
erDiagram
    USER ||--o| VENDOR : "is"
    USER ||--o| RIDER : "is"
    USER }o--|| ROLE : "has"
    USER ||--o{ ORDER : "places"
    USER ||--o| CART : "owns"

    COMPONENT }o--|| COMPONENT_CATEGORY : "in"
    COMPONENT }o--o| BRAND : "by"
    VENDOR ||--o{ VENDOR_COMPONENT : "stocks"
    COMPONENT ||--o{ VENDOR_COMPONENT : "sold via"

    PC_BUILD ||--o{ BUILD_COMPONENT : "contains"
    COMPONENT ||--o{ BUILD_COMPONENT : "part of"

    CART ||--o{ CART_ITEM : "has"
    ORDER ||--o{ ORDER_ITEM : "has"
    ORDER ||--o{ VENDOR_ORDER : "split into"
    VENDOR_ORDER ||--o{ VENDOR_ORDER_ITEM : "has"
    VENDOR ||--o{ VENDOR_ORDER : "fulfills"
    ORDER ||--o{ PAYMENT : "paid by"
    ORDER ||--o{ SHIPMENT : "shipped via"
    ORDER ||--o{ ASSEMBLY_TRACKING : "assembled in"
    ORDER ||--o{ QA_CHECK : "verified by"
    ORDER ||--o{ ORDER_STATUS_HISTORY : "logs"

    RIDER ||--o{ DELIVERY_ASSIGNMENT : "delivers"
    ORDER ||--o| DELIVERY_ASSIGNMENT : "assigned"
    DELIVERY_ASSIGNMENT ||--o{ RIDER_LOCATION_PING : "tracked by"

    USER ||--o{ NOTIFICATION : "receives"
```

> A separate **eCommerce module** (`ecom_*` tables: `EcomProduct`, `EcomCart`, `EcomCartItem`, `EcomOrder`, `EcomOrderItem`) runs the simple shop with a cart→admin-approval→order flow, independent of the component-build pipeline above.

---

## 5. AI / Computer-Vision Pipeline

```mermaid
flowchart LR
    subgraph Detect["Component Detection"]
        Img["📷 Image upload<br/>(camera / gallery)"] --> EP1["POST /api/detect/component"]
        EP1 --> Y["YOLOv8 best.pt<br/>(ultralytics)"]
        Y --> Box["Bounding boxes + labels<br/>mouse · keyboard · monitor · RAM<br/>(conf ≥ threshold)"]
    end

    subgraph Recommend["Build Recommendation"]
        Q["Budget (PKR) + Purpose<br/>gaming / office"] --> EP2["POST /api/recommend-build"]
        EP2 --> Logic["Parse budget · query live catalog<br/>filter by category/price/stock<br/>ensure CPU/MB/RAM coherence"]
        Logic --> Out["Real component IDs → cart"]
    end

    Box --> ChatUI["AI Chatbot / Configurator (React)"]
    Out --> ChatUI
```

- **Model:** custom `best.pt` (YOLOv8) trained on 4 PC-peripheral classes; preloaded at startup in [Dashboard/run.py](Dashboard/run.py).
- **Training assets:** `dataset/` (data.yaml + images/labels), training scripts in `tools/`, outputs in `runs/detect/`.

---

## 6. Deployment Topology

```mermaid
flowchart TB
    Dev["👩‍💻 Developer<br/>START-GENSPARK-DASHBOARD-DEV.bat"]

    subgraph Local["Local Dev"]
        FE_L["my-react-app<br/>vite dev :5173"]
        BE_L["Dashboard/run.py<br/>Flask :5000"]
        DB_L[("SQLite<br/>genspark_erp.db")]
        FE_L -->|"vite proxy /api → 127.0.0.1:5000"| BE_L
        BE_L --> DB_L
    end

    subgraph Prod["Production"]
        FE_P["Vercel<br/>genspark-frontend.vercel.app"]
        BE_P["Railway<br/>genspark-production.up.railway.app"]
        DB_P[("Managed MySQL")]
        FE_P -->|"HTTPS + JWT/cookies (CORS credentials)"| BE_P
        BE_P --> DB_P
    end

    Dev --> Local
```

| Tier | Local Dev | Production |
|------|-----------|------------|
| Frontend | Vite dev server `:5173` | Vercel |
| Backend | Flask `:5000` (`Dashboard/run.py`) | Railway (gunicorn) |
| Database | SQLite (`genspark_erp.db`) | MySQL (managed) |
| Payments | Stripe test keys | Stripe live keys |

---

## 7. Repository Map — Active vs Legacy

> Documenting this honestly matters for an FYP booklet — the repo contains historical iterations.

```mermaid
flowchart TB
    subgraph Active["✅ ACTIVE"]
        D["Dashboard/ — modular Flask backend (blueprints + 30 models)"]
        R["my-react-app/ — React 19 + Vite frontend"]
        DS["dataset/ · tools/ · scripts/ — YOLO training & data import"]
    end
    subgraph Legacy["⚠️ LEGACY / NOT DEPLOYED"]
        M["app.py (root) — ~2,900-line monolith"]
        BK["backend/app.py — older monolith copy"]
        VD["'vendor dashboard/' — old Flask UI"]
        OLD["app/ (root) · venv · myvenv · myvenv64 — stale"]
    end
```

**Active architecture (this booklet):** `Dashboard/` (backend) + `my-react-app/` (frontend).
**Legacy / parallel iterations:** root `app.py`, `backend/`, `vendor dashboard/`, old virtualenvs — kept for history, not part of the modular design.

---

## 8. One-Line Summary

> **GenSpark** is a React + Flask platform where customers configure/buy PCs (with **YOLOv8** component detection and **AI budget-based build recommendation**), pay via **Stripe**, and orders flow through a **multi-role pipeline** — Admin approval → Vendor assembly/QA → Rider live-GPS delivery — all backed by a ~30-table MySQL/SQLite schema.

---

*Generated from verified source inspection of `Dashboard/`, `my-react-app/`, models, routes, configs and dev launchers. All blueprints, routes, models, ports, and integrations were read from the actual code, not assumed.*
