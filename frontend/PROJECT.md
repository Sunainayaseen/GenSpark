# GenSpark Builds — FYP Project Documentation

**GenSpark Builds** is an AI-powered PC customization platform that helps users design compatible PC builds, choose verified local vendors for assembly, and track orders with notifications. This document describes the system for your Final Year Project (FYP) report and demo.

---

## 1. Overview

- **Purpose:** Allow users to get AI-recommended PC builds, customize them, assign a vendor, place orders, and track status from assembly to delivery.
- **Roles:** Buyer (end user), Vendor (assembly), Admin (quality check and oversight).
- **Tech stack (this implementation):** React, Vite, React Router, Context API (state), CSS.

---

## 2. High-Level Workflow

```
User → Sign up / Login → AI Chatbot (purpose, budget, city) → Build suggestions
  → Select build → Customize (optional) → Vendor selection & payment
  → Order created → Vendor: Assembly → Upload photos
  → Admin: Quality check → Approve → Shipment → Delivery → Feedback
```

---

## 3. Modules (Mapping to Your Doc)

| Module | Implementation |
|--------|----------------|
| **Authentication & User Management** | `AuthContext`: login, signup, logout; roles: buyer, vendor, admin; persisted in `localStorage`. |
| **Build selection** | Predefined builds (Gaming / Office / Content Creator) and **AI Custom Build** via chatbot. |
| **AI Recommendation & Component Identification** | Chatbot collects purpose, budget, city, preferences; suggests compatible builds. |
| **Custom Configuration** | Build configurator: replace parts, filters, real-time price; compatibility hints. |
| **Verified Vendor Management** | Vendor list by city; ratings, assembly cost; auto or manual assignment. |
| **Order Management & Payment** | `AppContext`: `addOrder`, `updateOrderStatus`; payment method: Online or COD. |
| **Order lifecycle** | `ORDER_STAGES`: Pending → Vendor Assigned → Assembling → Photos Uploaded → Approved → Shipped → Delivered. |
| **Vendor Dashboard** | View assigned orders; Start Assembly → Upload Build Photo (updates status in context). |
| **Admin Quality Assurance** | Validation queue for orders with “Photos Uploaded”; Approve / Flag / Request Rework. |
| **Shipment & Live Tracking** | Order status page shows timeline; stages support Shipped / Delivered. |
| **Notifications** | Timeline entries represent WhatsApp-style updates (message + timestamp). |
| **Database & Security** | In-memory state (Context); ready to replace with REST API + DB; role-based access via AuthContext. |

---

## 4. Step-by-Step Flow (For Demo / Report)

1. **User access & authentication**  
   Sign up or log in. Choose role: Buyer or Vendor. Admin can be seeded for demo.

2. **Build selection**  
   - Predefined: choose Gaming / Office / Content Creator.  
   - AI: open Chatbot, enter purpose, budget, city, preferences → get suggested builds.

3. **AI build generation**  
   Chatbot suggests builds; user picks one. Build can have title, price, parts list.

4. **Custom PC configuration**  
   From “Customize” or configurator: swap parts, see price and compatibility.

5. **Vendor assignment**  
   Go to Vendor Assignment: see city-based vendors, select or auto-assign, choose assembly vs parts-only, select payment (Online / Pay at Delivery).

6. **Order creation & payment**  
   Confirm Order → `addOrder()` creates order with status Pending and Vendor Assigned → redirect to Order Status page.

7. **Assembly & admin quality check**  
   - Vendor Dashboard: orders with `vendorId`; “Start Assembly” → status Assembling; “Upload Build Photo” → Photos Uploaded.  
   - Admin Panel: orders with status “Photos Uploaded” in queue; “Approve” → Approved; “Request Rework” → back to Assembling.

8. **Shipment & delivery**  
   Order status page shows full lifecycle; Shipped / Delivered can be added via `updateOrderStatus` (e.g. from admin or a shipment screen).

9. **Notifications**  
   Each status change appends to `order.timeline` (message + timestamp), shown on Order Status page (represents WhatsApp-style updates).

10. **Feedback & analytics**  
    Placeholder sections in UI; data can be stored in same context or future API.

---

## 5. Key Files (Quick Reference)

| Area | Files |
|------|--------|
| Order lifecycle | `src/constants/orderStages.js` |
| Global state | `src/context/AppContext.jsx`, `src/context/AuthContext.jsx` |
| Auth UI | `src/components/AuthModal.jsx` |
| Flow explanation | `src/pages/HowItWorks.jsx` |
| Order placement | `src/pages/VendorAssignment.jsx` → `addOrder()`, then navigate to `/order/:id` |
| Order tracking | `src/pages/OrderStatus.jsx` → `getOrderById()`, `ORDER_STAGES` |
| Vendor flow | `src/pages/VendorDashboard.jsx` → `updateOrderStatus(assembling / photos-uploaded)` |
| Admin flow | `src/pages/AdminPanel.jsx` → validation queue, `updateOrderStatus(approved / rework)` |

---

## 6. How to Run

```bash
cd my-react-app
npm install
npm run dev
```

Open the URL shown (e.g. `http://localhost:5173`). Use **How it Works** in the nav for the high-level flow; then go through Chatbot → Build → Vendor Assignment → Order Status, and optionally Vendor Dashboard and Admin Panel to show full workflow.

---

## 7. For Your FYP Report

- **Introduction:** Describe the problem (PC building complexity, compatibility, trust in local assembly).
- **Objectives:** AI-based recommendations, verified vendors, order lifecycle, quality check.
- **Methodology:** Modules above; workflow diagram (you can redraw the high-level workflow from Section 2).
- **Implementation:** Tech stack; mention React, Context for state, role-based dashboards, order stages.
- **Testing:** Walk through the steps in Section 4; mention different roles (Buyer, Vendor, Admin).
- **Conclusion / Future work:** Backend API, real database, WhatsApp integration, payments gateway.

You can copy or adapt this document into your report and cite the repository structure and file list as your implementation evidence.
