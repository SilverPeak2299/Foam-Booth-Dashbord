# Foam Booth Dashboard

Static sales analytics dashboard for Foam Booth data.

## Run Locally

Build aggregate dashboard data:

```bash
python3 scripts/build_dashboard_data.py
```

Serve the static dashboard:

```bash
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000
```

Planning docs:

- [Product requirements](docs/PRD.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Data sources and privacy rules](docs/DATA_SOURCES.md)

Gemini processing:

- [Gemini task prompt](gemini/TASK.md)
- Source CSV: `data/gemini_source/stage_1_output_no_customer.csv`

Generated dashboard data lives in `public/data/`. GitHub Pages deployment rebuilds these aggregate files and publishes only `index.html`, `assets/`, and `public/`.
