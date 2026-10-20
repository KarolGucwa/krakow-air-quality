"""Capture README screenshots of the running dashboard and of the dbt lineage graph.

    pip install playwright && playwright install chromium   # or pass --channel chrome
    streamlit run dashboard/app.py --server.port 8501 &      # dashboard must be running
    dbt docs generate --project-dir dbt --profiles-dir dbt --static
    python scripts/take_screenshots.py --dashboard http://localhost:8501
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
# The Map tab is skipped: its basemap needs WebGL and tile downloads, unavailable in headless CI.
TABS = ["Trends", "Coal ban", "Weather & week", "WHO exceedances", "Data quality"]


def dashboard(page, url: str) -> None:
    page.set_viewport_size({"width": 1400, "height": 1900})
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("text=Kraków air quality", timeout=60_000)
    page.wait_for_timeout(4000)
    for i, tab in enumerate(TABS):
        page.get_by_role("tab", name=tab).click()
        page.wait_for_timeout(3500)
        slug = tab.lower().replace(" & ", "_").replace(" ", "_")
        page.locator('[data-testid="stMainBlockContainer"]').screenshot(
            path=str(OUT / f"dashboard_{i + 1}_{slug}.png"))


def lineage(page) -> None:
    docs = ROOT / "dbt" / "target" / "static_index.html"
    if not docs.exists():
        print("dbt/target/static_index.html missing - run `dbt docs generate --static` first")
        return
    page.set_viewport_size({"width": 1500, "height": 820})
    page.goto(docs.as_uri() + "#!/overview?g_v=1")
    page.wait_for_timeout(5000)
    # Show everything upstream of the dashboard exposure (sources, seeds, models), no tests.
    try:
        box = page.locator('input[ng-model="selectorService.selection.dirty.include"]')
        box.fill("+exposure:streamlit_dashboard")
        box.press("Enter")
        page.get_by_text("Update Graph").click()
        page.wait_for_timeout(4000)
    except Exception as exc:  # the docs UI changes between dbt versions
        print(f"could not filter the lineage graph: {exc}")
    page.screenshot(path=str(OUT / "dbt_lineage.png"), clip={"x": 30, "y": 280, "width": 1450, "height": 255})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", default="http://localhost:8501")
    parser.add_argument("--skip-dashboard", action="store_true")
    parser.add_argument("--channel", default=None,
                        help="use an installed browser instead of Playwright's Chromium, e.g. chrome")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel,
                                    args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(device_scale_factor=2)
        if not args.skip_dashboard:
            dashboard(page, args.dashboard)
        lineage(page)
        browser.close()


if __name__ == "__main__":
    main()
