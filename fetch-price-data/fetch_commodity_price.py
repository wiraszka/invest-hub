import pandas as pd
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

async def scrape_te_commodities_debug():
    url = "https://tradingeconomics.com/commodities"
    out_dir = Path.cwd()
    html_path = out_dir / "te_debug_page.html"
    shot_path = out_dir / "te_debug_screenshot.png"
    csv_path = out_dir / "tradingeconomics_commodities.csv"

    print("=" * 80)
    print("Starting TradingEconomics scrape")
    print(f"Target URL: {url}")
    print(f"Working directory: {out_dir}")
    print("=" * 80)

    browser = None

    try:
        async with async_playwright() as p:
            print("[1] Launching Chromium...")
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            print("[2] Creating browser context...")
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 2200},
                locale="en-US",
            )

            page = await context.new_page()

            print("[3] Navigating to page...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            print(f"    Final URL: {page.url}")
            print(f"    Response status: {response.status if response else 'No response object'}")

            print("[4] Waiting a bit for JS-rendered content...")
            await page.wait_for_timeout(8000)

            title = await page.title()
            print(f"    Page title: {title}")

            body_text = await page.locator("body").inner_text()
            body_preview = body_text[:2000].replace("\n", " ")
            print(f"    Body preview (first 2000 chars):\n{body_preview}\n")

            print("[5] Saving debug artifacts...")
            html = await page.content()
            html_path.write_text(html, encoding="utf-8")
            await page.screenshot(path=str(shot_path), full_page=True)
            print(f"    Saved HTML to: {html_path}")
            print(f"    Saved screenshot to: {shot_path}")

            print("[6] Checking for possible bot/challenge indicators...")
            indicators = [
                "verify that you're not a robot",
                "verify you are not a robot",
                "javascript is disabled",
                "captcha",
                "access denied",
                "blocked",
                "unusual traffic",
                "cloudflare",
            ]

            found_indicators = [x for x in indicators if x.lower() in body_text.lower()]
            if found_indicators:
                print(f"    Potential block indicators found: {found_indicators}")
            else:
                print("    No obvious block keywords found.")

            print("[7] Counting tables and rows...")
            table_count = await page.locator("table").count()
            tbody_row_count = await page.locator("table tbody tr").count()
            tr_count = await page.locator("tr").count()

            print(f"    Number of <table> elements: {table_count}")
            print(f"    Number of <table tbody tr> rows: {tbody_row_count}")
            print(f"    Total <tr> elements: {tr_count}")

            print("[8] Trying to extract rows from all tables...")
            all_data = []

            tables = page.locator("table")
            for t in range(table_count):
                table = tables.nth(t)
                rows = table.locator("tr")
                row_count = await rows.count()
                print(f"    Table {t}: {row_count} rows")

                for r in range(row_count):
                    row = rows.nth(r)
                    cells = row.locator("th, td")
                    cell_count = await cells.count()

                    row_data = []
                    for c in range(cell_count):
                        txt = (await cells.nth(c).inner_text()).strip()
                        row_data.append(txt)

                    if row_data:
                        print(f"        Table {t}, row {r}: {row_data[:6]}")
                        all_data.append(row_data)

            print("[9] Building DataFrame...")
            if not all_data:
                print("    No table data extracted.")
                df = pd.DataFrame()
            else:
                max_len = max(len(r) for r in all_data)
                normalized = [r + [""] * (max_len - len(r)) for r in all_data]
                df = pd.DataFrame(normalized)
                print(f"    Extracted shape: {df.shape}")

            print("[10] Saving CSV...")
            df.to_csv(csv_path, index=False)
            print(f"    Saved CSV to: {csv_path}")

            print("[11] Done.")
            return df

    except PlaywrightTimeoutError as e:
        print("TIMEOUT ERROR")
        print(str(e))
        return pd.DataFrame()

    except Exception as e:
        print("GENERAL ERROR")
        print(type(e).__name__)
        print(str(e))
        return pd.DataFrame()

    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass