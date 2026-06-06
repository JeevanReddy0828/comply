# Landing page screenshots

The landing page references two images here. Until they exist, the page falls
back to striped placeholders (each `<img onerror>` removes itself, revealing the
placeholder behind it), so the page never looks broken.

Drop in these two files:

| File | What to capture |
|---|---|
| `system-detail.png` | System Detail of the seeded **Resume Screener** at **67%** — summary cards + the control table showing the green/red status mix. |
| `control-remediation.png` | A failing control expanded (e.g. **DOC_003**) showing the plain-language remediation panel and the **Add evidence** button. |

## How to capture (reproducible)

1. `docker compose up -d` and start the backend on `:8000`.
2. `python scripts/seed_demo.py` → seeds the Resume Screener (~67%) and prints
   the login (`demo@comply.dev` / `ComplyDemo123`) and the system URL.
3. Run the frontend (`npm run dev` in `frontend/`), sign in, open the system.
4. Capture the two views above at ~1280×800 and save them here with the exact
   filenames in the table.

Target aspect ratio is ~16:9 (the page crops to `object-fit: cover`, top-aligned).
