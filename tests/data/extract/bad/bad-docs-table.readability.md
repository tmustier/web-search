**Heads up:** Billing endpoints are rate limited by account tier.

# Billing API Endpoints

Use these endpoints to read invoices and update payment methods. The table
below is intentionally dense and includes repeated headers.

| Method | Endpoint | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/v1/billing/invoices` | read:billing | List invoices (paginated). |
| GET | `/v1/billing/invoices/{id}` | read:billing | Retrieve a single invoice by ID. |
| POST | `/v1/billing/payment-methods` | write:billing | Add a new payment method. |
| DELETE | `/v1/billing/payment-methods/{id}` | write:billing | Remove a payment method. |
| GET | `/v1/billing/credits` | read:billing | List promotional credits and expirations. |
| POST | `/v1/billing/credits/apply` | write:billing | Apply a credit to the current invoice. |

## Schemas

The `payment_method` object includes nested billing details and
regional tax metadata.

## Errors

* `402` payment required
* `409` billing profile locked
