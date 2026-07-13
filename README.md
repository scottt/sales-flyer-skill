# sales-flyer

Generate sales material — an **A4 PDF flyer** and **square messaging-app cards**
(LINE 圖文訊息 / WhatsApp / WeChat, 1040×1040 PNG) — from a single YAML file.

Change a price in the YAML and every deliverable updates. The print flyer and the
phone cards cannot drift apart.

<!-- Add a screenshot here once you have real branding. -->

## Install as a Claude Code plugin

This repo is its own [plugin marketplace](https://docs.claude.com/en/docs/claude-code/plugins).
In Claude Code:

```
/plugin marketplace add scottt/sales-flyer-skill
/plugin install sales-flyer@sales-flyer
```

(The same thing from a terminal: `claude plugin marketplace add scottt/sales-flyer-skill`
then `claude plugin install sales-flyer@sales-flyer`.)

Then just ask for what you want — "make me a pricing flyer for Acme" — and the
skill is picked up automatically; or invoke it explicitly with
`/sales-flyer:sales-flyer` (plugin name, then skill name). The skill instructions
cover the copywriting rules (sell outcomes, source every number, badge the middle
tier), not just the mechanics.

To update later: `/plugin marketplace update sales-flyer`.

## Or run it as a plain CLI

No Claude Code required. Needs [uv](https://docs.astral.sh/uv/) and nothing else —
`build.py` declares its own dependencies (PEP 723) and downloads Chromium on first
run.

```bash
git clone https://github.com/scottt/sales-flyer-skill
cd sales-flyer-skill
uv run skills/sales-flyer/build.py skills/sales-flyer/content/example-petsdotcom.yaml
```

Outputs land in `out/`, relative to wherever you run it:

```
out/petsdotcom.pdf           A4, 2 pages — email / print / hand to a customer
out/petsdotcom-card-1.png    1040×1040 — hook + value props
out/petsdotcom-card-2.png    1040×1040 — what it does + proof numbers
out/petsdotcom-card-3.png    1040×1040 — pricing + call to action
out/petsdotcom-print.html    the rendered HTML (a build artifact; inspect, don't edit)
out/petsdotcom-cards.html
```

## Making your own flyer

```bash
cp skills/sales-flyer/content/example-petsdotcom.yaml acme.yaml
$EDITOR acme.yaml
uv run skills/sales-flyer/build.py acme.yaml
```

The example (a fictional Pets.com subscription) is fully commented and exercises
every supported field. Useful flags:

```bash
uv run skills/sales-flyer/build.py acme.yaml --only cards      # skip the PDF
uv run skills/sales-flyer/build.py acme.yaml --card-size 1080  # different square size
uv run skills/sales-flyer/build.py acme.yaml --outdir dist
```

Iterate on the YAML, not the rendered HTML in `out/` — it gets overwritten. And
**look at the PNGs afterwards**: a price broken across two lines is the #1 failure
of the square format, and the only way to catch it is to open the image.

## Hacking on the skill itself

To point Claude Code at your working copy instead of the installed plugin, symlink
the skill directory (it is self-contained — `build.py`, `templates/` and `content/`
all live inside it):

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/sales-flyer" ~/.claude/skills/sales-flyer
```

## Tool and Font Dependencies

Playwright ships a self-contained Chromium per platform,
renders the PDF *and* screenshots the cards at exact pixel sizes,
and needs no system packages at all.

The one thing that still comes from the OS is **fonts**. For Traditional Chinese,
macOS and Windows are fine out of the box; on Linux install Noto Sans CJK TC
(`sudo dnf install google-noto-sans-cjk-fonts` / `apt install fonts-noto-cjk`).

## Layout

```
.claude-plugin/marketplace.json      makes this repo installable via /plugin marketplace add
.claude-plugin/plugin.json           the plugin manifest
skills/sales-flyer/SKILL.md          Claude Code skill definition
skills/sales-flyer/build.py          PEP 723 uv script: YAML → HTML → PDF + PNGs
skills/sales-flyer/templates/print.html.j2   A4 layout
skills/sales-flyer/templates/cards.html.j2   square card layout (one .card = one PNG)
skills/sales-flyer/content/example-petsdotcom.yaml   worked example, fully commented
```
