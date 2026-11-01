# Small-shop ecommerce: API list

Proposed first version: **45 endpoints across 29 URL patterns**. One endpoint means one
HTTP method + path combination. These are planned APIs, not currently implemented APIs.
The models and business rules are defined in [MODELS.md](MODELS.md).

## Scope and conventions

- Base prefix: `/api/`. Paths below include this prefix.
- `id` placeholders are internal database identifiers; `number` is the order's public UUID.
- Access: Public, Customer (authenticated owner), Cart owner (customer or guest token),
  Order owner (customer or guest order token), or Staff.
- Use Django sessions for the initial first-party storefront, including CSRF protection
  on unsafe requests. Authentication transport can be revisited for a separate mobile client.
- Guests prove cart ownership using a secure token cookie. Checkout returns a separate
  guest order token through a secure cookie. Never put secret tokens in URL query strings.
- Lists are paginated. Product lists support search, category, availability, and price sorting.
- Public catalog results contain active categories/products/variants only. Staff can request
  `include_inactive=true` on catalog reads and receive inactive variants/images as well.
- Success responses follow the current project shape: `{"message": "...", "data": ...}`.
- POST creation returns 201; reads/updates/actions return 200; deletes return 204.
  Invalid input returns 400, missing authentication 401/403 as appropriate for sessions,
  forbidden access 403, and inaccessible/missing private records 404.
- All financial values, ownership, stock changes, and status transitions are server-controlled.
- Implement plain request/response serializers, thin APIView classes, business logic in
  services.py, and explicit app-level routes matching the existing project pattern.

## Accounts — 8 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 1 | POST | `/api/auth/register/` | Public | Create customer; username, email, password, names, mobile_number. Never accept staff flags. |
| 2 | POST | `/api/auth/login/` | Public | Username/password; establish session. |
| 3 | POST | `/api/auth/logout/` | Customer | End session. |
| 4 | GET | `/api/auth/me/` | Customer | Current customer profile. |
| 5 | PATCH | `/api/auth/me/` | Customer | Update names and mobile_number; email/username changes deferred. |
| 6 | POST | `/api/auth/password/change/` | Customer | Current password and new password. |
| 7 | POST | `/api/auth/password/reset/` | Public | Email; send reset link with generic response regardless of account existence. |
| 8 | POST | `/api/auth/password/reset/confirm/` | Public | User identifier, expiring reset token, new password. |

Use Django password/reset mechanisms, not custom password/token tables. Account recovery
requires configured email delivery. Establish CSRF cookies through safe session/profile
or cart reads before the first unsafe request; no separate CSRF route is required.

## Saved addresses — 4 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 9 | GET | `/api/addresses/` | Customer | List own saved addresses. |
| 10 | POST | `/api/addresses/` | Customer | Add recipient, phone, street/address, area, city, postal code, country. |
| 11 | PATCH | `/api/addresses/{id}/` | Customer | Edit own address. |
| 12 | DELETE | `/api/addresses/{id}/` | Customer | Delete own address; past orders are unaffected. |

## Categories — 5 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 13 | GET | `/api/categories/` | Public | List categories; include parent id. |
| 14 | GET | `/api/categories/{id}/` | Public | Category details. |
| 15 | POST | `/api/categories/` | Staff | Create name, slug, optional parent. |
| 16 | PATCH | `/api/categories/{id}/` | Staff | Edit category or deactivate it. |
| 17 | DELETE | `/api/categories/{id}/` | Staff | Delete only if no products/children reference it. |

## Products — 5 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 18 | GET | `/api/products/` | Public | Search/filter products; include main image and available price range. |
| 19 | GET | `/api/products/{id}/` | Public | Product details including variants, availability, and images. |
| 20 | POST | `/api/products/` | Staff | Create draft product and initial variant together; stock starts at zero. |
| 21 | PATCH | `/api/products/{id}/` | Staff | Edit name, slug, description, category, is_active. |
| 22 | DELETE | `/api/products/{id}/` | Staff | Delete only if no protected sale/stock history; otherwise archive using PATCH. |

## Variants — 3 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 23 | POST | `/api/products/{id}/variants/` | Staff | Add SKU, options, price; zero initial stock. |
| 24 | PATCH | `/api/variants/{id}/` | Staff | Edit SKU, options, price, is_active; cannot directly edit stock. |
| 25 | DELETE | `/api/variants/{id}/` | Staff | Delete unused variant; protect history and the product's last variant. |

No separate variant read APIs: product detail includes them. Order item snapshots retain
the original SKU/options/price even when the variant is subsequently edited.

## Product images — 3 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 26 | POST | `/api/products/{id}/images/` | Staff | Multipart upload; image, optional variant_id, alt_text, position. |
| 27 | PATCH | `/api/product-images/{id}/` | Staff | Update image, variant assignment, alt text, or position. |
| 28 | DELETE | `/api/product-images/{id}/` | Staff | Remove image. |

Product detail includes general and variant images. Image assignment must match the product.

## Cart — 5 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 29 | GET | `/api/cart/` | Cart owner | Read current basket and live totals; issue guest token if absent. |
| 30 | POST | `/api/cart/items/` | Cart owner | Add variant_id and positive quantity; increment an existing matching line. |
| 31 | PATCH | `/api/cart/items/{id}/` | Cart owner | Set absolute positive quantity. |
| 32 | DELETE | `/api/cart/items/{id}/` | Cart owner | Remove own line. |
| 33 | DELETE | `/api/cart/` | Cart owner | Clear own cart items; retain cart/token. |

Reject inactive/unavailable variants. Stock is checked at cart edits and checked again at
checkout; placing something in a cart does not reserve it. Quantity zero uses DELETE.

## Customer orders and checkout — 4 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 34 | POST | `/api/orders/` | Cart owner | Checkout current cart; checkout_key, saved address id or delivery fields, customer contact, method, optional note. |
| 35 | GET | `/api/orders/` | Customer | List own orders with fulfillment/payment summary. |
| 36 | GET | `/api/orders/{number}/` | Order owner | Order snapshots, items, returned quantities, totals, payment summary, tracking. |
| 37 | POST | `/api/orders/{number}/cancel/` | Order owner or Staff | Cancel pending/confirmed order; restore stock once. |

Checkout uses server prices/charges and is atomic. A retry with the same checkout_key
returns the existing authorized order (200) instead of creating another (201).
Guests supply delivery fields directly and receive a secret order-access token.
Guest orders are not searchable by phone/email through public APIs.

Cancellation marks pending payments cancelled. Already collected payments remain visible
as paid until staff records the refund; cancellation itself does not move money.

## Staff order operations — 4 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 38 | GET | `/api/staff/orders/` | Staff | All orders; filter status, derived payment state, dates, order number, phone. |
| 39 | GET | `/api/staff/orders/{number}/` | Staff | Complete order with payments and internal payment notes. |
| 40 | PATCH | `/api/staff/orders/{number}/` | Staff | Advance allowed fulfillment status; edit courier/tracking. No price/item edits. |
| 41 | POST | `/api/staff/orders/{number}/returns/` | Staff | Record delivered item returns: item_id, quantity, restock_quantity, note. |

Cancellation goes through endpoint 37; returned status is set by endpoint 41, not generic
PATCH. Returns verify item ownership, remaining returnable quantity, and
0 <= restock_quantity <= quantity. Lock order/items/variants and record restocking
movements atomically. Repeated fully processed quantities cannot be returned again.
Partial returns do not automatically refund money; first version supports full refunds only.

## Inventory — 2 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 42 | GET | `/api/staff/stock-movements/` | Staff | Stock history; filter variant, reason, order, date. |
| 43 | POST | `/api/staff/stock-movements/` | Staff | Receive/damage/correct stock; variant_id, quantity_change, reason, note. |

Current stock is included in staff product responses; no separate stock table/read endpoint
is needed. Staff cannot manually submit sale/cancellation/return reasons: the corresponding
order services generate those. Receiving is positive, damage negative, correction either
sign; all changes must leave stock nonnegative. Movement records cannot be edited/deleted.

## Payments and refunds — 2 endpoints

| # | Method | Path | Access | Purpose / main input |
|---|---|---|---|---|
| 44 | POST | `/api/staff/orders/{number}/payments/` | Staff | Record pending payment outcome, or create a retry after failed/cancelled attempt; payment_id when updating, method for retry, status, reference, note. |
| 45 | POST | `/api/staff/payments/{id}/refund/` | Staff | Record completed full manual refund; refund_reference and refund_note. |

Payment amount/currency come from the order. Only pending attempts can change to
succeeded/failed/cancelled. Updating a terminal attempt cannot collect again. Lock the
order while creating retries/recording outcomes; enforce one pending or succeeded attempt.
Reject collection/retry for cancelled or returned orders. Reject collection if the order
already has a refunded payment in this first version.

Refund endpoint requires cancelled/fully returned order and succeeded payment. A repeated
request returns the existing refunded result without recording another refund. It does
not call a payment provider or alter inventory. Online payment checkout, callbacks, and
automatic refunds must be designed against the chosen provider before integration.

## Count and implementation notes

| Area | Endpoints |
|---|---:|
| Accounts | 8 |
| Addresses | 4 |
| Categories | 5 |
| Products | 5 |
| Variants | 3 |
| Images | 3 |
| Cart | 5 |
| Customer orders | 4 |
| Staff orders | 4 |
| Inventory | 2 |
| Payments/refunds | 2 |
| **Total** | **45** |

These 45 methods share 29 URL patterns. Not every model needs full CRUD. Payment history
is nested in orders; order items are created only by checkout; stock movements are
append-only. Django admin is additional built-in tooling, not part of this endpoint count.

Build in stages: accounts/catalog -> inventory/cart -> checkout -> fulfillment/payments.
Verify ownership on every private API and test checkout concurrency, retry safety,
cancellation, return quantity limits, and repeated payment/refund requests before launch.
