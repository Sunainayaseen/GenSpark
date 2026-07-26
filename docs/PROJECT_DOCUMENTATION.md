# GenSpark — Project Documentation

Ye document poore project ki har file/folder ka purpose aur use hone wale tools/technologies ka scope explain karta hai, taake koi bhi is se project samajh sake.

---

## 1. Project Overview

GenSpark ek **PC-building e-commerce platform** hai jisme:
- Customer PC parts browse karke custom build bana sakta hai (AI recommendation ke sath)
- Vendor apne components list/manage karta hai
- Rider order deliver karta hai
- Admin sab kuch manage karta hai
- Ek image-detection (YOLO/AI) feature bhi hai jo hardware component ko camera/image se detect karta hai

Do main parts hain:
- **`Dashboard/`** — Backend (Python / Flask)
- **`my-react-app/`** — Frontend (React + Vite)

---

## 2. Root-level Files/Folders

| Path | Purpose |
|---|---|
| `Dashboard/` | Poora backend (Flask API, models, services) |
| `my-react-app/` | Poora frontend (React app) |
| `docs/` | Extra documentation files |
| `scripts/` | Helper/automation scripts |
| `tools/` | Misc developer tools |
| `dataset/` | AI model training ke liye images/data |
| `uploads/` | User-uploaded files (images etc.) |
| `venv/` | Python virtual environment (local, git-ignored honi chahiye) |
| `best.pt` | Trained YOLO model weight file (image detection ke liye) |
| `chat_intelligence.py` | Chatbot/AI intelligence logic (root level helper) |
| `live_detect_dshow.py` | Live camera se real-time object/component detection script |
| `GENSPARK_TRAIN_COLAB.ipynb` | Google Colab notebook — YOLO model train karne ke liye |
| `genspark_erp.sql` | Database schema/dump (SQL) |
| `START-CAMERA-DETECTION.bat` | Windows script — camera detection feature run karne ke liye |
| `START-GENSPARK-DASHBOARD-DEV.bat` | Windows script — dev mode mein dashboard run karne ke liye |
| `DEBUGGING_GUIDE.md` | Debugging steps/notes |
| `TESTING_AND_VALIDATION_GUIDE.md` | Testing process ki guide |
| `README.md` | Project ka general intro |

---

## 3. Backend — `Dashboard/` (Flask, Python)

### 3.1 Root config & run files
| File | Purpose |
|---|---|
| `run.py` | App run karne ka entry point |
| `config.py` | App configuration (DB URL, secret keys, env settings) |
| `init_db.py` | Database tables create/seed karta hai |
| `migrate_data.py` | Purani/existing data ko naye schema mein migrate karta hai |
| `check_app.py` | App health check script |
| `qa_smoke.py` | Quick smoke test |
| `pytest.ini` | Pytest configuration |
| `requirements.txt` | Python dependencies list |
| `render.yaml` | Render.com deployment config |
| `Procfile` | Gunicorn/production start command (Heroku-style deployment) |
| `.env` / `.env.example` | Environment variables (secrets, DB creds) — example file version-controlled, `.env` nahi honi chahiye |
| `add_brand_id_to_components.sql` | One-off DB migration script |
| `add_must_change_password_column.py` | One-off DB migration script |
| `seed_*.py` (multiple) | Demo/test data seed karne ki scripts (riders, vendors, components, prebuilt parts) |
| `set_component_images.py` / `set_all_component_images.py` | Components ke images DB mein set karne ki scripts |
| `*.bat` files | Windows shortcut scripts (Flask start/stop, admin create, port kill) |
| `API_GUIDE.md`, `DASHBOARD_GUIDE.md`, `DB_SETUP_FOR_VIEWING_USERS.md`, `MAILHOG.md`, `README.md` | Documentation/setup guides |

### 3.2 `app/__init__.py`
Flask app factory — app initialize, blueprints register, extensions (DB, JWT, CORS, SocketIO) setup yahan hota hai.

### 3.3 `app/api/` — API Routes (customer-facing)
| File | Purpose |
|---|---|
| `routes.py` | General/main API endpoints |
| `ai_build_routes.py` | AI-based PC build suggestion endpoints |
| `addresses_routes.py` | User address add/edit/delete APIs |
| `notifications_routes.py` | Notifications fetch/mark-read APIs |
| `tracking_routes.py` | Order tracking APIs |
| `stripe_checkout.py` | Stripe payment/checkout session APIs |
| `controllers/cart_controller.py` | Cart business logic (add/remove/update items) |

### 3.4 Role-based Blueprints
| Folder | Purpose |
|---|---|
| `app/auth/routes.py` | Login, signup, password reset, JWT auth |
| `app/admin/routes.py` | Admin-only endpoints (manage users, vendors, orders) |
| `app/vendor/routes.py` | Vendor panel endpoints (manage own components/orders) |
| `app/rider/routes.py` | Rider panel endpoints (delivery status updates) |

### 3.5 `app/models/` — Database Tables (SQLAlchemy ORM)
| File | Represents |
|---|---|
| `user.py` | Customer/user accounts |
| `address.py` | User delivery addresses |
| `cart.py` | Shopping cart items |
| `order.py` | Orders |
| `payment.py` | Payment records |
| `vendor.py` | Vendor accounts |
| `rider.py` | Delivery rider accounts |
| `shipment.py` | Shipment/delivery tracking |
| `build.py` | Custom PC build |
| `assembly.py` | Assembly service details |
| `component.py` | PC hardware components/parts |
| `notification.py` | User notifications |
| `qa.py` | Q&A / support data |
| `ecommerce.py` | General ecommerce entities |

### 3.6 `app/services/` — Business Logic Layer
| File | Purpose |
|---|---|
| `build_intelligence.py` | AI logic — best PC build recommend karta hai based on budget/use-case |
| `compatibility.py` | Parts ek dusre ke sath compatible hain ya nahi check karta hai (e.g. CPU-motherboard socket match) |
| `customization.py` | Build customize karne ki logic (part swap, upgrade) |
| `fees.py` | Assembly fee, shipping fee calculate karta hai |
| `hardware_specs.py` | Hardware specs data/lookup helper |
| `component_info.py` | Component details fetch karta hai |
| `vendor_coverage.py` | Vendor kis area mein deliver kar sakta hai, check karta hai |
| `notification_service.py` | Notification create/send karne ki service |

### 3.7 `app/utils/` — Utility/Helper Functions
| File | Purpose |
|---|---|
| `rate_limit.py` | API rate-limiting (spam/abuse se bachao) |
| `schema.py` | Request data validation schemas |
| `jwt_session_bridge.py` | JWT token aur session ko bridge/sync karta hai |
| `email_helper.py` | Email bhejne ka helper (verification, notifications) |
| `component_media.py` | Component images/media handling |
| `dispatch.py` | Order dispatch logic helper |
| `urls.py` | URL building helpers |
| `vendor_delete.py` | Vendor delete/cleanup helper |

### 3.8 AI / Image Detection
| File | Purpose |
|---|---|
| `app/detect_image_input.py` | Uploaded image se hardware component detect karta hai |
| `app/yolo_weights.py` | YOLO model weights load karne ka helper |

### 3.9 Realtime
| File | Purpose |
|---|---|
| `app/realtime.py` | Socket.IO based realtime updates (e.g. order status, notifications live push) |

### 3.10 `Dashboard/tests/` — Automated Tests
| File | Purpose |
|---|---|
| `conftest.py` | Pytest fixtures/setup |
| `test_auth_hardening.py` | Auth security tests |
| `test_build_recommendation.py` | AI build recommendation tests |
| `test_compatibility.py` | Parts compatibility tests |
| `test_fees.py` | Fee calculation tests |
| `test_helpers.py` | Helper function tests |
| `test_inventory_lifecycle.py` | Inventory flow tests |
| `test_smoke.py` | Basic smoke tests |
| `test_stripe_checkout.py` | Stripe checkout flow tests |
| `test_vendor_consistency.py` | Vendor data consistency tests |

---

## 4. Frontend — `my-react-app/` (React + Vite)

### 4.1 Root
| File | Purpose |
|---|---|
| `App.jsx` | Sab routes/pages yahan define hote hain |
| `main.jsx` | React app ka entry point (DOM mein mount karta hai) |
| `branding.js` | App name/branding config |
| `index.css`, `App.css` | Global styles |
| `package.json` | Dependencies aur scripts (dev/build/test) |

### 4.2 `src/api/` — Backend Communication Layer
| File | Purpose |
|---|---|
| `authApi.js` | Login/signup/logout API calls |
| `builderApi.js` | PC builder/AI suggestion API calls |
| `paymentApi.js` | Payment/Stripe API calls |
| `ecomApi.js` | Ecommerce/order API calls |
| `addressesApi.js` | Address CRUD API calls |
| `dashboardApi.js` | Dashboard data API calls |

### 4.3 `src/context/` — Global State Management
| File | Purpose |
|---|---|
| `AuthContext.jsx` | Logged-in user state, poore app mein available |
| `CartContext.jsx` | Cart state (items, total) |
| `AppContext.jsx` | General app-wide shared state |

### 4.4 `src/pages/` — Full Pages
| File | Purpose |
|---|---|
| `Landing.jsx` | Home/landing page |
| `BuildConfigurator.jsx` | Custom PC build banane ka page |
| `BuildSuggestions.jsx` | AI se build suggestions dekhne ka page |
| `Components.jsx` | Sab parts/products list page |
| `PrebuiltDetail.jsx` | Ek pre-built PC ki detail page |
| `CartPage.jsx` | Cart page |
| `Checkout.jsx` | Checkout/payment page |
| `OrderPlacedSuccess.jsx` | Order successful confirmation page |
| `MyOrders.jsx` | User ke saare orders |
| `OrderStatus.jsx` | Ek order ka status/progress |
| `TrackOrder.jsx` | Order tracking page |
| `VendorDashboard.jsx` | Vendor ka apna dashboard |
| `VendorAssignment.jsx` | Vendor assignment/management page |
| `AdminPanel.jsx` | Admin control panel |
| `Chatbot.jsx` | AI chatbot full page |
| `ChangePassword.jsx` | Password change page |
| `About.jsx`, `Contact.jsx` | Static info pages |
| `ComponentMediaPlaceholder.jsx` | Component image placeholder logic |

### 4.5 `src/components/` — Reusable UI Components
| File | Purpose |
|---|---|
| `Layout.jsx` | Common page wrapper (header/footer) |
| `AuthModal.jsx` | Login/Signup popup modal |
| `AIChatbot.jsx` | Chatbot widget (floating) |
| `CartDropdown.jsx` | Header cart dropdown |
| `BuildCustomizer.jsx` | Build customization UI |
| `BuildRecommendationCard.jsx` | AI suggestion card UI |
| `NotificationBell.jsx` | Notification bell icon + dropdown |
| `NotificationToaster.jsx` | Toast-style notification popup |
| `ImageDetectOverlay.jsx` | Image detection result overlay (AI feature) |
| `ErrorBoundary.jsx` | React crash catch karke fallback UI dikhata hai |
| `HeaderSearch.jsx` | Header search bar |
| `HeaderUserMenu.css` | User menu ka styling |
| `HeroSlideshow.jsx` | Landing page hero image slideshow |
| `ProfileMenu.jsx` | Profile dropdown menu |
| `ScrollProgressBar.jsx` | Page scroll progress indicator |
| `TiltCard.jsx` | 3D tilt hover effect card |
| `CursorEffects.jsx` | Custom cursor animation effect |
| `SystemMessageCard.jsx` | System-level message/alert card |
| `StripeVerifyTest.jsx` | Stripe verification test component (dev) |
| `NavLinkPrefetch.jsx` | Route prefetching for faster navigation |
| `ConfirmProvider.jsx` | Confirmation dialog provider (global "are you sure?" prompts) |

### 4.6 `src/utils/` — Helper Functions
| File | Purpose |
|---|---|
| `buildCompatibility.js` | Frontend-side compatibility check logic |
| `buildPartMatcher.js` | Parts ko match karne ki logic |
| `buildResolver.js` | Build data resolve/parse karta hai |
| `assemblyFee.js` (+ test) | Assembly fee calculation |
| `authStorage.js` | Login token local storage mein save/retrieve |
| `format.js` | Price/date formatting helpers |
| `chatIntentParse.js` | Chatbot message se intent nikalta hai |
| `parseBuildRecommendation.js` (+ test) | AI response ko parse karta hai |
| `componentImage.js`, `componentLocalPhotos.js` | Component images resolve karna |
| `detectionErrors.js` | Image detection error handling |
| `flaskBase.js` | Backend base URL config |
| `orderGuards.js` | Order-related validation guards |
| `parallax.js`, `scrollAnimations.js` | Visual scroll animation effects |
| `routePrefetch.js` | Routes ko prefetch karna (performance) |
| `adaptEcomOrder.js` | Ecommerce order data ko frontend format mein adapt karta hai |

### 4.7 Other
| File | Purpose |
|---|---|
| `src/realtime/socket.js` | Socket.IO client connection (realtime updates) |
| `src/constants/orderStages.js` | Order stages ki fixed list (constants) |
| `src/data/prebuiltShowcase.js` | Prebuilt PCs ka static showcase data |
| `src/hooks/useBlockingOrder.js` | Order-blocking state ke liye custom hook |
| `src/hooks/useMotionCapability.js` | Device animation-support detect karne wala hook |
| `src/config/deployUrls.js` | Deployment environment URLs |
| `src/styles/layout-lock.css` | Layout-locking styles |

---

## 5. Tools / Technologies & Their Scope

### Backend
| Tool | Scope/Use |
|---|---|
| **Flask** | Main web framework — routes/APIs serve karta hai |
| **Flask-SQLAlchemy** | Database ORM (models define/query) |
| **Flask-JWT-Extended / PyJWT** | Login authentication (JWT tokens) |
| **Flask-Bcrypt / bcrypt** | Password hashing (security) |
| **Flask-CORS** | Frontend (different origin) se API calls allow karna |
| **Flask-SocketIO / python-socketio** | Realtime features (live notifications, order updates) |
| **Stripe** | Payment processing/checkout |
| **PyMySQL / SQLAlchemy** | MySQL database se connection |
| **Ultralytics (YOLO) / torch / torchvision / opencv** | AI image detection — hardware component ko image/camera se pehchan-na |
| **Pillow** | Image processing |
| **pytest** | Automated testing |
| **gunicorn** | Production web server (deployment) |

### Frontend
| Tool | Scope/Use |
|---|---|
| **React 19** | UI framework |
| **Vite** | Dev server + build tool |
| **React Router** | Page navigation/routing |
| **Axios** | Backend API calls |
| **Stripe.js / react-stripe-js** | Payment form UI + checkout |
| **Socket.IO client** | Realtime updates (backend se live data) |
| **Framer Motion** | Animations |
| **react-markdown + remark-gfm** | Chatbot ke markdown replies render karna |
| **lucide-react** | Icons |
| **ESLint** | Code quality checks |
| **Vitest** | Unit testing |

### Deployment
- **Render.com** (`render.yaml`) — backend hosting
- **Procfile** — Gunicorn start command (Heroku-style)

---

## 6. Quick Summary (One-liner har module ka)

- **Auth** → Login/signup/JWT
- **Builder** → Custom PC build + AI recommendation
- **Components** → Hardware parts catalog + compatibility
- **Cart/Checkout** → Shopping cart + Stripe payment
- **Orders/Tracking** → Order lifecycle + delivery tracking
- **Vendor** → Vendor apne parts/orders manage karta hai
- **Rider** → Delivery status update karta hai
- **Admin** → Sab kuch oversee/manage karta hai
- **AI Detection** → Camera/image se component pehchanna (YOLO)
- **Notifications** → Realtime alerts (Socket.IO)
- **Chatbot** → AI-powered customer assistant
