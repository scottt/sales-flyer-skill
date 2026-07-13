---
name: sales-flyer
description: Generate a sales flyer with pricing as an A4 PDF plus square messaging-app cards (LINE 圖文 / WhatsApp / WeChat, 1040×1040 PNG). Use when the user asks for sales material, a product one-pager, a pricing flyer, a DM/EDM, LINE 圖文訊息, or marketing collateral for a product or service. Handles Traditional Chinese and English.
---

# Sales Flyer

Turn a product's positioning and pricing into two deliverables that share one
source of truth:

| Output | Use |
|---|---|
| `<name>.pdf` | A4, 2 pages — email attachment, print, hand to a customer |
| `<name>-card-1..N.png` | 1040×1040 — LINE 圖文訊息, WhatsApp, WeChat, IG |

Content lives in **one YAML file**; two Jinja2 templates render it. Change a price
in the YAML and both deliverables update — the flyer and the cards can never drift.

## How to use

`build.py`, `templates/` and `content/` live in this skill's own directory
(alongside this file) — call them by that path. Write the customer's YAML and the
output into the **user's** working directory, never into the skill directory.

1. **Gather the content.** You need: brand name + tagline, a headline, 3 value
   props, 3–6 named customer outcomes, 2–4 proof numbers, 2–4 pricing tiers, and
   contact details. If the user hasn't given you pricing, **ask** — a flyer without
   a number is a brochure, not sales material.
2. **Copy `content/example-petsdotcom.yaml`** from the skill directory to
   `<customer>.yaml` in the user's project and fill it in. The example is fully
   commented; every field it shows is supported.
3. **Build:**
   ```bash
   uv run <skill-dir>/build.py <customer>.yaml
   # → out/<name>.pdf, out/<name>-card-1.png, ...
   ```
   Options: `--outdir DIR`, `--only pdf|cards`, `--card-size 1080`. `--outdir`
   defaults to `out/` relative to the current directory.
4. **Look at the output.** Read the PNGs back and check for wrapped numbers,
   overflowing cards, and collisions. This step is not optional — a flyer with a
   price broken across two lines is worse than no flyer.
5. Iterate on the YAML, not the rendered HTML. The rendered HTML in `out/` is a
   build artifact and gets overwritten.

## Writing the copy (this is most of the work)

- **Sell outcomes, not features.** "貨款入帳自動對帳 — LINE 馬上通知哪張單" beats
  "MCP-based banking integration." A buyer who isn't technical must be able to
  point at a line and say "I want that one."
- **Lead the proof section with the number that hurts.** Cost comparisons work
  because the reader is already paying the bigger number. Put the painful figure
  first and the cheap one next to it.
- **Never ship a number you can't source.** Every stat gets a `note` and the
  section gets a `stats_source`. If someone challenges the flyer in a meeting and
  the figure collapses, the deal collapses with it.
- **Pre-empt objections in the FAQ.** Write down what the salesperson actually
  hears — "what if the AI wires money to the wrong account" — not what marketing
  wishes they heard.
- **Three tiers, middle one badged.** The badge (`badge: 推薦`) is what most buyers
  pick. Price the middle tier as the one you want to sell.
- Keep pricing honest about validity: `pricing_fineprint` should state that prices
  are pre-tax and quote-bound, especially when component costs are volatile.

## Design rules baked into the templates

Don't rewrite the CSS to "make it pop" — the constraints are deliberate:

- Numbers never wrap (`white-space: nowrap`), and long values on the square cards
  auto-shrink. A wrapped price is the #1 failure of this format.
- Stat tones are semantic: `neutral` (the number they pay today), `good` (green —
  your number), `brand` (blue — the ratio). Green is reserved for "this is the win."
- Brand color drives everything from `brand.color` / `brand.accent`; change the two
  hex values, not the individual rules.
- The square cards are a **re-layout**, not a shrunk A4: fewer words, bigger type,
  a `*_mobile` variant of any string that's too long for a phone. Every `*_mobile`
  field falls back to the desktop string when omitted.

## The mobile cards

LINE rich messages are square. Card 1 = hook + value props (blue, high contrast in
a chat feed), card 2 = what it does + the proof numbers, card 3 = pricing + CTA.
Send them as a sequence, or load them into LINE Official Account Manager as 圖文訊息.

To use a real QR code, set `cta.qr` to an image path relative to `out/` (the render
directory) — otherwise a placeholder box is drawn.

## Requirements

`uv` only. `build.py` is a PEP 723 script: it declares its own dependencies and
downloads Chromium on first run. No system libraries, no poppler, no GTK — works
on Windows, macOS and Linux.

CJK text needs a CJK font installed on the machine doing the render (macOS and
Windows have one; on Linux install `Noto Sans CJK TC`). Set `font:` in the YAML.
