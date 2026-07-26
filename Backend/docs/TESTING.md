# GenSpark — Software Testing Document

**Project:** GenSpark ERP & PC-Build E-Commerce Platform
**Module under test:** Dashboard backend (Flask, port 5000) — the live production stack
**Document type:** Test Plan & Test Cases (Black Box + White Box)
**Date:** 2026-06-11

> **How to use this document:** Each section below is a table. Copy any table straight into
> Microsoft Word / Google Docs — formatting is preserved. Fill the **Status** and **Actual Result**
> columns during a real test run.

---

## 1. Introduction

This document describes the testing strategy for the GenSpark platform. Two complementary
techniques are used:

| Technique | What it means | Who performs it | Focus |
| --- | --- | --- | --- |
| **Black Box Testing** | Test the system from the outside — give inputs, check outputs. The internal code is *not* examined. | QA team / end user | Does the feature work correctly for the user? |
| **White Box Testing** | Test the internal code — every function, branch (if/else) and logic path is examined. | Developer | Is the code logic itself correct? |

Both are required for complete coverage: black box confirms the product **behaves** correctly,
white box confirms the code is **built** correctly.

---

## 2. Test Environment

| Item | Detail |
| --- | --- |
| Application | GenSpark Dashboard (Flask) |
| Base URL (local) | `http://localhost:5000` |
| Test database | In-memory SQLite (production MySQL `genspark_erp` is never touched during tests) |
| Test framework | pytest |
| Test config | `Dashboard/tests/conftest.py` (fresh DB per test) |
| Browser (black box) | Chrome / Edge (latest) |
| API tool (black box) | Postman / browser dev-tools |
| Key env vars | `STRIPE_SECRET_KEY`, `DATABASE_URL`, `SECRET_KEY`, `MAIL_SERVER` |

---

# PART A — BLACK BOX TEST CASES

*Functional testing from the user's point of view. No code knowledge required.*

## A1. Authentication

| TC ID | Test Case | Steps | Test Data | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BB-AUTH-01 | Sign up with valid data | Open signup → fill form → submit | name, valid email, password | Account created, redirect to login page | | |
| BB-AUTH-02 | Sign up with duplicate email | Submit signup using an email that already exists | existing email | Error shown, account not created (409) | | |
| BB-AUTH-03 | Sign up missing fields | Submit with empty email/password | blank fields | Validation error, form not submitted (400) | | |
| BB-AUTH-04 | Login with correct credentials | Enter valid email + password → submit | active user | Redirect to correct role dashboard | | |
| BB-AUTH-05 | Login with wrong password | Enter valid email + wrong password | wrong password | "Invalid credentials" error (401) | | |
| BB-AUTH-06 | Login with unverified account | Login before email verification | status = pending_email | Login blocked, asked to verify email | | |
| BB-AUTH-07 | Login as blocked user | Login with a blocked account | status = blocked | Access denied | | |
| BB-AUTH-08 | Logout | Click logout while logged in | — | Session ends, redirect to login | | |
| BB-AUTH-09 | Email verification (valid link) | Click verification link from email | valid token | Account activated (status = active) | | |
| BB-AUTH-10 | Email verification (expired link) | Click an old link (>24h) | expired token | "Link expired" message | | |
| BB-AUTH-11 | Forced password change on first login | Login with one-time password | must_change_password = true | Prompted to set a new password | | |

## A2. AI Build Recommendation (Chatbot)

| TC ID | Test Case | Steps | Test Data | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BB-AI-01 | Greeting only | Type a greeting in the build chat | "Hi" / "Hello" | Friendly guide reply, **no** parts list generated | | |
| BB-AI-02 | Gaming build request | Ask for a build with a budget | "200k gaming build" | Full parts list (CPU, GPU, Motherboard, RAM, Storage, PSU, Case) within budget | | |
| BB-AI-03 | Budget in lakh | Enter budget as lakh | "1.2 lakh build" | Build generated for ≈120,000 PKR | | |
| BB-AI-04 | Budget in "k" form | Enter budget with k | "120k build" | Build generated for ≈120,000 PKR | | |
| BB-AI-05 | Office build (no gaming) | Ask for office/work build | "office pc 60000" | Build uses integrated graphics, no discrete GPU | | |
| BB-AI-06 | Total within budget | Check the total of recommended parts | any budget | Sum of part prices ≤ stated budget | | |
| BB-AI-07 | Add recommended build to cart | Click "Add to cart" on recommendation | — | All recommended components added with correct IDs | | |
| BB-AI-08 | Empty catalog fallback | Request build when catalog has no parts | empty DB | A fallback estimate is shown (no crash) | | |

## A3. Catalog / Components

| TC ID | Test Case | Steps | Test Data | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BB-CAT-01 | Search component by name | Type a component name in search | "RTX 4070" | Matching components listed | | |
| BB-CAT-02 | Search with no query | Open catalog without searching | — | Default components listed (in-stock first, cheapest first) | | |
| BB-CAT-03 | Filter by category | Apply a category filter | category = GPU | Only GPUs shown | | |
| BB-CAT-04 | Filter by brand | Apply a brand filter | brand = ASUS | Only that brand shown | | |
| BB-CAT-05 | View vendors for a component | Open a component's vendor list | in-stock item | Approved vendors listed with price & quantity | | |
| BB-CAT-06 | Out-of-stock handling | View an out-of-stock component's vendors | stock = 0 | Out-of-stock vendors excluded | | |

## A4. Cart & Checkout

| TC ID | Test Case | Steps | Test Data | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BB-CART-01 | Add item to cart (guest) | Add a product without logging in | any product | Item added to a guest cart | | |
| BB-CART-02 | Add item to cart (logged in) | Add a product after login | any product | Item added to user cart; guest cart merged | | |
| BB-CART-03 | Add full PC build to cart | Add a prebuilt PC build | a build | All build components added individually | | |
| BB-CART-04 | Add quantity above stock | Set quantity higher than available stock | qty > stock | Error shown with max allowed quantity | | |
| BB-CART-05 | Update cart quantity | Change quantity of a cart item | valid qty | Cart and total updated | | |
| BB-CART-06 | Remove item | Delete an item from cart | — | Item removed, total recalculated | | |
| BB-CART-07 | Clear cart | Click "Clear cart" | — | Cart empty | | |
| BB-CART-08 | Send cart for approval | Submit cart for admin approval | — | Cart status → pending approval | | |
| BB-CART-09 | Place order | Checkout with shipping details | name, phone, address, city | Order created, cart cleared, status = pending | | |
| BB-CART-10 | Stripe payment (success) | Complete payment with test card | succeeded payment | Order saved, stock reduced, payment recorded | | |
| BB-CART-11 | Stripe payment (failed) | Submit a non-succeeded payment | failed/incomplete | Order **not** created, error shown | | |
| BB-CART-12 | Duplicate payment replay | Re-submit the same payment intent | same intent id | No duplicate order (idempotent) | | |
| BB-CART-13 | View my orders | Open "My Orders" | logged in | User sees only their own orders | | |

## A5. Admin Panel

| TC ID | Test Case | Steps | Test Data | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BB-ADM-01 | Admin dashboard KPIs | Open admin dashboard | — | Counts for users, vendors, orders, revenue etc. shown | | |
| BB-ADM-02 | Non-admin blocked | Open `/admin` as a normal user | customer login | Access denied / redirected | | |
| BB-ADM-03 | Add user | Admin adds a new user | name, email, role | User created, one-time password emailed | | |
| BB-ADM-04 | Block / unblock user | Toggle a user's status | — | Status flips active ↔ blocked | | |
| BB-ADM-05 | Approve vendor | Approve a pending vendor | — | Vendor status → approved, email sent | | |
| BB-ADM-06 | Block vendor | Block a vendor | — | Vendor status → blocked | | |
| BB-ADM-07 | Add component | Add a component with image | name, price, stock, image | Component created, image saved | | |
| BB-ADM-08 | Add PC build | Create a build with components | name + component list | Build saved with all components | | |
| BB-ADM-09 | Approve order | Approve a pending order | — | Vendor orders generated, status → processing | | |
| BB-ADM-10 | Reject order | Reject a pending order | no vendor orders yet | Order status → rejected | | |
| BB-ADM-11 | QA pass | Mark an order's QA as pass | order in qa | QA record (pass) created, status → shipped | | |
| BB-ADM-12 | QA fail | Mark an order's QA as fail | order in qa | QA record (fail) created, status → assembly | | |
| BB-ADM-13 | Approve vendor proof | Approve a vendor's completion proof | proof image | Proof approved, rider auto-assignment triggered | | |

## A6. Addresses

| TC ID | Test Case | Steps | Test Data | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BB-ADDR-01 | Add first address | Save an address | line1 + details | Saved and auto-set as default | | |
| BB-ADDR-02 | Add address without line1 | Save with empty line1 | blank line1 | Validation error | | |
| BB-ADDR-03 | Edit address | Update an existing address | new details | Address updated | | |
| BB-ADDR-04 | Set default | Mark another address as default | — | New default set, others cleared | | |
| BB-ADDR-05 | Delete default address | Delete the default address | had 2+ addresses | Next address promoted to default | | |

---

# PART B — WHITE BOX TEST CASES

*Code-level testing. Each case targets a specific function / logic branch. Implemented as pytest unit tests.*

## B1. Budget Parsing — `_parse_budget_pkr()`  (`ai_build_routes.py`)

*Automated in `tests/test_helpers.py`.*

| TC ID | Function / Branch | Input | Expected Return | Actual | Status |
| --- | --- | --- | --- | --- | --- |
| WB-BUD-01 | Lakh keyword path | "1.2 lakh" | 120000 | 120000 | **PASS** |
| WB-BUD-02 | "k" suffix path | "120k" | 120000 | 120000 | **PASS** |
| WB-BUD-03 | Plain integer path | "150000" | 150000 | 150000 | **PASS** |
| WB-BUD-04 | Bare small number → lakh assumption | "2" | 200000 | 200000 | **PASS** |
| WB-BUD-05 | Currency suffix stripped | "60000 PKR" | 60000 | 60000 | **PASS** |
| WB-BUD-06 | Invalid / empty input branch | "", "   ", "abc", None | None (handled gracefully) | None | **PASS** |

## B2. Build Logic — `_select_components()` / `_recommend_from_catalog()`

*Automated in `tests/test_build_recommendation.py` (seeds an in-memory catalog).*

| TC ID | Function / Branch | Condition Tested | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- |
| WB-SEL-01 | Platform matching (AM5) | AMD Ryzen CPU selected | Motherboard + RAM generation match the socket | Ryzen 7700 → B650 board | **PASS** |
| WB-SEL-02 | Platform matching (LGA1700) | Intel Core CPU selected | Compatible motherboard chosen | Core i5-13400 → B760 board | **PASS** |
| WB-SEL-03 | Budget-fitting greedy step-down | Parts total > budget | Expensive parts stepped down until total ≤ budget | — | Not run (manual) |
| WB-SEL-04 | Required types completeness | Any build request | All `GEMINI_REQUIRED_TYPES` present (CPU, GPU, Motherboard, RAM, Storage, PSU, Case) | All 7 slots filled | **PASS** |
| WB-SEL-05 | Office build branch | purpose = office | Discrete GPU excluded, iGPU used | No GPU in build | **PASS** |
| WB-SEL-06 | OEM exclusion filter | Catalog contains "Dell OptiPlex" / "HP EliteDesk" | OEM prebuilt systems excluded from selection | OptiPlex not selected | **PASS** |
| WB-SEL-07 | Empty-catalog branch | No components in DB | Returns `{}` / `None` (caller falls back to estimate) | `{}` and `None` | **PASS** |
| WB-SEL-08 | `build_components` ids | Successful DB recommendation | Each item carries a real `component_id` for cart resolver | All ids are real ints | **PASS** |

## B3. Greeting Detection — `_is_greeting_only_message()`

*Automated in `tests/test_helpers.py`.*

| TC ID | Branch | Input | Expected Return | Actual | Status |
| --- | --- | --- | --- | --- | --- |
| WB-GRT-01 | Greeting-only true branch | "hi" / "hello there" / "salam" | True (no build) | True | **PASS** |
| WB-GRT-02 | Build-request false branch | "200k gaming build" | False (proceed to recommend) | False | **PASS** |
| WB-GRT-03 | Mixed message | "hi, suggest a 100k build" | False (build intent detected) | False | **PASS** |

## B4. Checkout Logic — `complete_checkout()` (`stripe_checkout.py`)

| TC ID | Branch | Condition | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- |
| WB-CHK-01 | Payment status guard | payment intent = succeeded | Order creation proceeds | | |
| WB-CHK-02 | Payment status guard (negative) | payment intent ≠ succeeded | Returns 400, no order created | | |
| WB-CHK-03 | Idempotency branch | Same `payment_intent_id` re-sent | Existing order returned (200), no duplicate | | |
| WB-CHK-04 | Stock check branch | item stock insufficient | Returns 400 before any DB commit | | |
| WB-CHK-05 | Stock decrement | successful order | Component / vendor stock decremented correctly | | |
| WB-CHK-06 | Amount conversion | amount in major units | Converted to minor units (×100) for Stripe | | |

## B5. Cart Service — `add_or_update_item()` / `cart_controller`

| TC ID | Branch | Condition | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- |
| WB-CRT-01 | New item path | item not in cart | New cart row inserted | | |
| WB-CRT-02 | Existing item path | item already in cart | Quantity updated, not duplicated | | |
| WB-CRT-03 | Stock-limit guard | qty > stock | ValueError → 400, `max_quantity` returned | | |
| WB-CRT-04 | Build unpacking | item_type = build | Each `BuildComponent` added individually | | |
| WB-CRT-05 | Cheapest-vendor auto-select | no vendor_id given | Cheapest approved vendor chosen | | |

## B6. Component Search — `api_components_search()`

| TC ID | Branch | Condition | Expected Result | Actual | Status |
| --- | --- | --- | --- | --- | --- |
| WB-SCH-01 | Default ordering | no filters | In-stock items first (stock DESC, then price ASC) | Top result in-stock | **PASS** |
| WB-SCH-02 | Category filter branch | category_id given | Filtered by category | Only that category returned | **PASS** |
| WB-SCH-03 | Brand filter branch | brand_id given | Filtered by brand | — | Not run (manual) |
| WB-SCH-04 | `brand_id` column fallback | older schema without column | Falls back to raw SQL, no crash | — | Not run (manual) |
| WB-SCH-05 | Vendor summary branch | vendor_summary = 1 | Vendor availability data included | — | Not run (manual) |

*WB-SCH-01/02 automated in `tests/test_build_recommendation.py`.*

## B7. Existing Automated Tests (already in repo)

> **Last run:** 2026-06-11 · pytest 8.3.4 · Python 3.11.9 · **26 collected, 26 passed, 0 failed (2.11s)**

| TC ID | Test File | Test Function | What it verifies | Status |
| --- | --- | --- | --- | --- |
| WB-EX-01 | `tests/test_smoke.py` | `test_health_endpoint_is_ok` | `/health` returns 200 OK | **PASS** |
| WB-EX-02 | `tests/test_smoke.py` | `test_root_redirects_to_login` | `/` redirects to `/auth/login` | **PASS** |
| WB-EX-03 | `tests/test_smoke.py` | `test_components_search_returns_seeded_component` | Seeded component is found via search API | **PASS** |

---

# PART C — Security & Edge-Case Checks

*Spans both techniques — verify the system is robust.*

| TC ID | Check | Expected Result | Status |
| --- | --- | --- | --- |
| SEC-01 | SQL injection in search box | Parameterized queries prevent injection | |
| SEC-02 | Access admin route as customer | Blocked (authorization enforced) | |
| SEC-03 | Stock race condition on checkout | Row lock (`with_for_update`) prevents oversell | |
| SEC-04 | Duplicate Stripe payment | Unique transaction id prevents double order | |
| SEC-05 | Image upload — bad extension | Only .png/.jpg/.jpeg/.webp accepted | |
| SEC-06 | Access another user's order | Returns only own orders (unless admin) | |

---

## 4. Test Summary (fill after execution)

> **Note:** 21 white-box cases are now covered by an automated pytest suite (26 test
> functions, since some cases use multiple inputs) — all passed. The remaining cases
> (black-box manual flows, Stripe/cart checkout, and a few search/build branches) are
> written and ready to run manually.

| Metric | Count |
| --- | --- |
| Total test cases (documented) | 98 |
| Black box cases (Part A) | 56 |
| White box cases (Part B) | 36 |
| Security / edge-case checks (Part C) | 6 |
| White-box cases automated & executed | 21 |
| pytest functions run | 26 |
| Passed | 26 |
| Failed | 0 |
| Blocked / Not run (pending manual run) | 77 |
| Pass rate of executed cases (%) | 100% |

---

## 5. How to Run the Automated (White Box) Tests

```bash
# from the Dashboard/ folder
pytest -v
```

Tests use an in-memory SQLite database, so the production MySQL database
(`genspark_erp`) is never affected.

---

*End of document.*
