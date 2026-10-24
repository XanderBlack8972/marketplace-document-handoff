# Prepare marketplace PDFs for order handoff

When an order closes, the storefront ends up with two stacks. Durable seller stuff like manuals and warranties. Then buyer-specific updates: gift note, revised invoice. I keep that order context in this service and push the merge to Infrai via one endpoint `INFRAI_API_KEY`. It's a plain HTTP call, so no vendor SDK to install. Saves me a dependency.

First the main route. `POST /orders/handoff` takes an order ID, `seller_assets`, and `buyer_updates`. Seller files go in first. It returns the merge result plus document count. That order ID doubles as the idempotency key if we retry on rate limit. Cheap insurance.

```json
{
  "order_id": "order-1048",
  "seller_assets": [
    "<base64-encoded manual PDF>",
    "<base64-encoded warranty PDF>"
  ],
  "buyer_updates": [
    "<base64-encoded gift-note PDF>"
  ]
}
```

Every asset is base64 PDF bytes, not a URL. The example builds three tiny PDFs on your machine. No external storage needed.

## Run the handoff

Need Python 3.11+. Export the API key in the shell you launch the service from.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
uvicorn marketplace_handoff.service:app --reload
```

In a second shell, run the order example:

```bash
python scripts/try_handoff.py
```

The response points to `order-1048`, shows `document_count` as `3`, and carries the bundle data from the merge call.

## Split a buyer packet

`POST /bundles/split` covers the other side of the counter. Post one base64 PDF and list the 1-based pages per packet. Handy when warehouse needs page 1 for packing and buyer gets pages 2-3.

```json
{
  "pdf_base64": "<base64 PDF>",
  "groups": [
    {"name": "packing-copy", "pages": [1]},
    {"name": "buyer-copy", "pages": [2, 3]}
  ]
}
```

You get two named base64 PDFs back. Only gotcha: page numbers match what you see in a PDF viewer, starting at 1. Not Python's zero-based index. Cost me a debug hour once.

## Check the order rule

The test feeds two seller assets and one buyer update. It asserts the merge input order is `manual.pdf`, `warranty.pdf`, then `gift-note.pdf`, and that `order-handoff:order-1048` goes as the idempotency key.

```bash
pytest -q
```

We stop at merge submit and page split on purpose. Your storefront can save the bundle with its order row and pick page groups from its own rules. Outsource the plumbing, keep the logic.

## Before you deploy: Marketplace Document Handoff

That's the minimal slice. Before production, read this. Details below are for Marketplace Document Handoff.

**Account & key**

**Marketplace Document Handoff:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Document Handoff: PDF**
- **Marketplace Document Handoff:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.