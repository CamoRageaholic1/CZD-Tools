---
name: wger
description: "Log food and calories and answer daily nutrition questions via the self-hosted wger tracker."
version: 1.0.0
author: CamoZeroDay
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Health, Nutrition, Calories, Food-Tracking, wger]
    homepage: https://wger.de
prerequisites:
  commands: [python3]
---

# wger: Food & Calorie Tracking

Use this skill whenever the user talks about food, eating, calories, macros, or
their daily nutrition — e.g. "log two eggs and toast", "how many calories have I
had today?", "what's my protein so far?", "scratch that last item", or "log my
weight at 82 kg".

The skill drives a self-hosted **wger** instance through a small CLI helper. The
helper handles auth, food lookup, logging, and daily totals — you just call it
through the shell and relay its output.

## The tool

Run the helper with `python3`:

```
python3 {skill_dir}/wger_tool.py <subcommand> [args]
```

(Its `config.env` already holds this bot's wger URL and API token, so logging
goes to the correct person's diary.)

| Subcommand | What it does |
|------------|--------------|
| `search <term>` | List foods matching a term, with per-100 g calories and macros. |
| `log <term> <grams>` | Log that many grams of the best-matching food for today, then print the running daily total. |
| `log-id <id> <grams>` | Log an exact food by its numeric id (use after `search` when disambiguating). |
| `barcode <code> [grams]` | Look up a product by its barcode number; logs it if grams are given. |
| `today` | Print today's totals (kcal, protein, carbs, fat) and the list of items. |
| `undo` | Delete the most recently logged item ("scratch that"). |
| `weight <kg>` | Record a bodyweight entry for today. |

## How to log food from natural language

The tool logs by **grams**, so convert the user's portions to grams before
calling `log`. Use these common reference weights (estimate sensibly for
anything not listed, and tell the user what you assumed):

- 1 large egg ≈ 50 g
- 1 slice of bread ≈ 30 g
- 1 medium banana ≈ 120 g; 1 medium apple ≈ 180 g
- 1 cup cooked rice/pasta ≈ 160 g; 1 cup milk ≈ 240 g
- 1 chicken breast ≈ 170 g; 1 tbsp oil/butter/peanut butter ≈ 14 g
- 1 slice of cheese ≈ 20 g

Workflow for a logging request:

1. Break the message into individual foods with quantities.
2. Convert each to grams.
3. Call `log "<food>" <grams>` for each item.
4. If the tool reports it matched a different food than expected, or the food
   isn't found, tell the user and offer `search` results so they can pick.
5. Relay the running daily total the tool prints after the last item.

Example — user says *"I had 2 eggs and a slice of toast"*:

```
python3 {skill_dir}/wger_tool.py log "egg" 100
python3 {skill_dir}/wger_tool.py log "white bread" 30
```

Then summarize: what was logged and the new daily total.

## Answering questions

- "How many calories today?" / "what's my protein?" → run `today` and report.
- "What can I log?" / a food you're unsure exists → run `search <term>`.

## Disambiguation (important with the full catalog)

The database now includes the full **Open Food Facts** catalog (hundreds of
thousands of foods, including branded products and barcodes) on top of ~100
curated whole foods. That means a plain term like "egg" can match many branded
products.

- `log` auto-picks the best match and prints the alternatives it found. If the
  user's intent is a plain whole food (egg, banana, chicken breast), the curated
  generic entry is ranked first, so `log "egg" 100` is usually right.
- When a request is ambiguous or clearly a specific branded item, run
  `search <term>` first, show the user the top few, then `log-id <id> <grams>`
  for the one they mean.
- If the user gives you a barcode number, use `barcode <code> <grams>`.

## Notes & limits

- Macros are per-100 g values from Open Food Facts (community data) or the
  curated set; treat totals as close estimates.
- Each bot logs to its own owner's diary (Atlas → David, Blanche → Babs). Never
  cross-log.
- If the tool prints an `ERROR:` line, relay it plainly; do not retry blindly.
