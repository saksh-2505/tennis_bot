import asyncio
from playwright.async_api import async_playwright


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to ReddyBook...")
        try:
            await page.goto(
                "https://reddybook.green", wait_until="networkidle", timeout=30000
            )
            content = await page.content()
            with open("reddybook_dump.html", "w") as f:
                f.write(content)
            print("HTML saved to reddybook_dump.html")

            # Look for links
            links = await page.query_selector_all('a')
            print(f"Found {len(links)} links.")
            for link in links[:20]:
                text = await link.inner_text()
                href = await link.get_attribute("href")
                print(f"Link: {text.strip()} -> {href}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
