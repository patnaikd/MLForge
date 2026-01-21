"""Web search tool using Playwright for browser automation."""

import asyncio
import re
from typing import Any, ClassVar
from urllib.parse import quote_plus, urljoin

from pydantic import BaseModel, Field, PrivateAttr

from src.tools.base import BaseAgentTool, ToolResult


class WebSearchInput(BaseModel):
    """Input schema for web search."""

    query: str = Field(description="Search query to execute")
    max_results: int = Field(
        default=5,
        description="Maximum number of results to return",
        ge=1,
        le=20,
    )
    search_type: str = Field(
        default="general",
        description="Type of search: general, documentation, kaggle, github, stackoverflow",
    )


class WebFetchInput(BaseModel):
    """Input schema for fetching a web page."""

    url: str = Field(description="URL to fetch")
    extract_text: bool = Field(
        default=True,
        description="Extract text content (default: true)",
    )
    extract_links: bool = Field(
        default=False,
        description="Extract links from the page",
    )
    wait_for: str | None = Field(
        default=None,
        description="CSS selector to wait for before extracting",
    )
    timeout: int = Field(
        default=30,
        description="Page load timeout in seconds",
    )


class WebSearchTool(BaseAgentTool):
    """Tool for performing web searches and fetching pages using Playwright.

    Supports various search types optimized for data science research:
    - General web search (DuckDuckGo)
    - Documentation search (specific docs sites)
    - Kaggle dataset search
    - GitHub repository search
    - Stack Overflow search
    """

    name: str = "web_search"
    description: str = """Search the web for information, documentation, datasets, and code.

Search types:
- general: General web search using DuckDuckGo
- documentation: Search Python/ML library documentation
- kaggle: Search Kaggle for datasets and notebooks
- github: Search GitHub for repositories and code
- stackoverflow: Search Stack Overflow for Q&A

Example usage:
- General search: {"query": "pandas merge dataframes", "search_type": "general"}
- Find dataset: {"query": "iris flower dataset", "search_type": "kaggle"}
- Find code: {"query": "xgboost hyperparameter tuning", "search_type": "github"}

Note: Requires playwright to be installed and browsers set up.
Run 'playwright install chromium' if not already done.
"""
    args_schema: type[BaseModel] = WebSearchInput

    # Search URL templates (ClassVar to avoid Pydantic field interpretation)
    SEARCH_URLS: ClassVar[dict[str, str]] = {
        "general": "https://duckduckgo.com/html/?q={query}",
        "documentation": "https://duckduckgo.com/html/?q={query}+site:readthedocs.io+OR+site:docs.python.org+OR+site:scikit-learn.org+OR+site:pandas.pydata.org",
        "kaggle": "https://www.kaggle.com/search?q={query}",
        "github": "https://github.com/search?q={query}&type=repositories",
        "stackoverflow": "https://stackoverflow.com/search?q={query}",
    }

    # Private instance attributes (not Pydantic fields)
    _browser_instance: Any = PrivateAttr(default=None)
    _playwright_instance: Any = PrivateAttr(default=None)

    async def _ensure_browser(self) -> Any:
        """Ensure Playwright browser is initialized.

        Returns:
            Browser instance
        """
        if self._browser_instance is None:
            try:
                from playwright.async_api import async_playwright

                self._playwright_instance = await async_playwright().start()
                self._browser_instance = await self._playwright_instance.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except ImportError:
                raise ImportError(
                    "Playwright is not installed. Run: pip install playwright && playwright install chromium"
                )

        return self._browser_instance

    async def _close_browser(self) -> None:
        """Close the browser instance."""
        if self._browser_instance:
            await self._browser_instance.close()
            self._browser_instance = None
        if self._playwright_instance:
            await self._playwright_instance.stop()
            self._playwright_instance = None

    def _run(
        self,
        query: str,
        max_results: int = 5,
        search_type: str = "general",
    ) -> str:
        """Execute web search synchronously.

        Args:
            query: Search query
            max_results: Maximum results to return
            search_type: Type of search

        Returns:
            Search results
        """
        # Run async version in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self._arun(query, max_results, search_type)
        )

    async def _arun(
        self,
        query: str,
        max_results: int = 5,
        search_type: str = "general",
    ) -> str:
        """Execute web search asynchronously.

        Args:
            query: Search query
            max_results: Maximum results to return
            search_type: Type of search

        Returns:
            Search results
        """
        self.logger.info(f"Web search: {query} (type: {search_type})")

        if search_type not in self.SEARCH_URLS:
            return str(
                ToolResult(
                    False,
                    "",
                    error=f"Unknown search type: {search_type}. Valid types: {list(self.SEARCH_URLS.keys())}",
                )
            )

        try:
            browser = await self._ensure_browser()
            page = await browser.new_page()

            try:
                # Build search URL
                search_url = self.SEARCH_URLS[search_type].format(
                    query=quote_plus(query)
                )

                # Navigate to search page
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                # Extract results based on search type
                if search_type == "general" or search_type == "documentation":
                    results = await self._extract_duckduckgo_results(page, max_results)
                elif search_type == "kaggle":
                    results = await self._extract_kaggle_results(page, max_results)
                elif search_type == "github":
                    results = await self._extract_github_results(page, max_results)
                elif search_type == "stackoverflow":
                    results = await self._extract_stackoverflow_results(page, max_results)
                else:
                    results = []

                if not results:
                    return str(
                        ToolResult(
                            True,
                            f"No results found for: {query}",
                            data={"query": query, "search_type": search_type, "results": []},
                        )
                    )

                # Format results
                output_lines = [f"Search results for: {query}", f"Type: {search_type}", ""]

                for i, result in enumerate(results, 1):
                    output_lines.append(f"{i}. {result.get('title', 'Untitled')}")
                    output_lines.append(f"   URL: {result.get('url', 'N/A')}")
                    if result.get("description"):
                        # Truncate long descriptions
                        desc = result["description"][:200]
                        if len(result["description"]) > 200:
                            desc += "..."
                        output_lines.append(f"   {desc}")
                    output_lines.append("")

                return str(
                    ToolResult(
                        True,
                        "\n".join(output_lines),
                        data={
                            "query": query,
                            "search_type": search_type,
                            "results": results,
                        },
                    )
                )

            finally:
                await page.close()

        except Exception as e:
            self.logger.error(f"Web search error: {e}")
            return str(ToolResult(False, "", error=f"Search failed: {str(e)}"))

    async def _extract_duckduckgo_results(
        self, page: Any, max_results: int
    ) -> list[dict[str, str]]:
        """Extract results from DuckDuckGo HTML search page."""
        results = []

        # Wait for results
        try:
            await page.wait_for_selector(".result", timeout=10000)
        except Exception:
            return results

        # Extract result elements
        elements = await page.query_selector_all(".result")

        for element in elements[:max_results]:
            try:
                title_el = await element.query_selector(".result__title a")
                snippet_el = await element.query_selector(".result__snippet")

                if title_el:
                    title = await title_el.inner_text()
                    url = await title_el.get_attribute("href")
                    description = ""
                    if snippet_el:
                        description = await snippet_el.inner_text()

                    results.append({
                        "title": title.strip(),
                        "url": url,
                        "description": description.strip(),
                    })
            except Exception:
                continue

        return results

    async def _extract_kaggle_results(
        self, page: Any, max_results: int
    ) -> list[dict[str, str]]:
        """Extract results from Kaggle search page."""
        results = []

        # Wait for results
        try:
            await page.wait_for_selector("[data-testid='search-result']", timeout=15000)
        except Exception:
            # Try alternative selector
            try:
                await page.wait_for_selector(".sc-hZpJaV", timeout=5000)
            except Exception:
                return results

        # Try multiple selectors for Kaggle's dynamic content
        selectors = [
            "[data-testid='search-result']",
            ".sc-hZpJaV",  # Dataset cards
            "a[href*='/datasets/']",
        ]

        for selector in selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                for element in elements[:max_results]:
                    try:
                        title = await element.inner_text()
                        url = await element.get_attribute("href")
                        if url and not url.startswith("http"):
                            url = urljoin("https://www.kaggle.com", url)

                        if title and url:
                            # Clean up title (first line usually)
                            title = title.split("\n")[0].strip()
                            results.append({
                                "title": title,
                                "url": url,
                                "description": "",
                            })
                    except Exception:
                        continue
                break

        return results[:max_results]

    async def _extract_github_results(
        self, page: Any, max_results: int
    ) -> list[dict[str, str]]:
        """Extract results from GitHub search page."""
        results = []

        # Wait for results
        try:
            await page.wait_for_selector("[data-testid='results-list']", timeout=10000)
        except Exception:
            try:
                await page.wait_for_selector(".repo-list-item", timeout=5000)
            except Exception:
                return results

        # Extract repository results
        elements = await page.query_selector_all(".repo-list-item, [data-testid='results-list'] > div")

        for element in elements[:max_results]:
            try:
                # Try to get repository link
                link_el = await element.query_selector("a[href*='/']")
                desc_el = await element.query_selector("p")

                if link_el:
                    title = await link_el.inner_text()
                    url = await link_el.get_attribute("href")
                    if url and not url.startswith("http"):
                        url = urljoin("https://github.com", url)

                    description = ""
                    if desc_el:
                        description = await desc_el.inner_text()

                    results.append({
                        "title": title.strip(),
                        "url": url,
                        "description": description.strip(),
                    })
            except Exception:
                continue

        return results

    async def _extract_stackoverflow_results(
        self, page: Any, max_results: int
    ) -> list[dict[str, str]]:
        """Extract results from Stack Overflow search page."""
        results = []

        # Wait for results
        try:
            await page.wait_for_selector(".s-post-summary", timeout=10000)
        except Exception:
            return results

        # Extract question results
        elements = await page.query_selector_all(".s-post-summary")

        for element in elements[:max_results]:
            try:
                title_el = await element.query_selector(".s-link")
                excerpt_el = await element.query_selector(".s-post-summary--content-excerpt")

                if title_el:
                    title = await title_el.inner_text()
                    url = await title_el.get_attribute("href")
                    if url and not url.startswith("http"):
                        url = urljoin("https://stackoverflow.com", url)

                    description = ""
                    if excerpt_el:
                        description = await excerpt_el.inner_text()

                    results.append({
                        "title": title.strip(),
                        "url": url,
                        "description": description.strip(),
                    })
            except Exception:
                continue

        return results


class WebFetchTool(BaseAgentTool):
    """Tool for fetching and extracting content from web pages."""

    name: str = "web_fetch"
    description: str = """Fetch content from a specific web page.

Features:
- Extract text content from pages
- Extract links for further exploration
- Wait for dynamic content to load
- Handle JavaScript-rendered pages

Example usage:
- Fetch documentation: {"url": "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html"}
- Get all links: {"url": "https://example.com", "extract_links": true}

Note: Requires playwright to be installed.
"""
    args_schema: type[BaseModel] = WebFetchInput

    # Private instance attributes (not Pydantic fields)
    _browser_instance: Any = PrivateAttr(default=None)
    _playwright_instance: Any = PrivateAttr(default=None)

    async def _ensure_browser(self) -> Any:
        """Ensure Playwright browser is initialized."""
        if self._browser_instance is None:
            try:
                from playwright.async_api import async_playwright

                self._playwright_instance = await async_playwright().start()
                self._browser_instance = await self._playwright_instance.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except ImportError:
                raise ImportError(
                    "Playwright is not installed. Run: pip install playwright && playwright install chromium"
                )

        return self._browser_instance

    def _run(
        self,
        url: str,
        extract_text: bool = True,
        extract_links: bool = False,
        wait_for: str | None = None,
        timeout: int = 30,
    ) -> str:
        """Fetch web page synchronously."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self._arun(url, extract_text, extract_links, wait_for, timeout)
        )

    async def _arun(
        self,
        url: str,
        extract_text: bool = True,
        extract_links: bool = False,
        wait_for: str | None = None,
        timeout: int = 30,
    ) -> str:
        """Fetch web page asynchronously.

        Args:
            url: URL to fetch
            extract_text: Whether to extract text content
            extract_links: Whether to extract links
            wait_for: CSS selector to wait for
            timeout: Page load timeout

        Returns:
            Page content
        """
        self.logger.info(f"Fetching URL: {url}")

        try:
            browser = await self._ensure_browser()
            page = await browser.new_page()

            try:
                # Navigate to page
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)

                # Wait for specific element if requested
                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, timeout=10000)
                    except Exception:
                        self.logger.warning(f"Timeout waiting for selector: {wait_for}")

                data: dict[str, Any] = {"url": url}
                output_parts = [f"Content from: {url}", ""]

                # Extract text content
                if extract_text:
                    # Remove script and style elements
                    await page.evaluate("""
                        const elements = document.querySelectorAll('script, style, noscript');
                        elements.forEach(el => el.remove());
                    """)

                    # Get main content or body text
                    content = await page.evaluate("""
                        () => {
                            // Try to find main content area
                            const main = document.querySelector('main, article, .content, #content, .main');
                            if (main) return main.innerText;
                            return document.body.innerText;
                        }
                    """)

                    # Clean up whitespace
                    content = re.sub(r"\n{3,}", "\n\n", content)
                    content = content.strip()

                    # Truncate if too long
                    max_length = 10000
                    if len(content) > max_length:
                        content = content[:max_length] + "\n\n... (truncated)"

                    data["text_length"] = len(content)
                    output_parts.append("=== TEXT CONTENT ===")
                    output_parts.append(content)
                    output_parts.append("")

                # Extract links
                if extract_links:
                    links = await page.evaluate("""
                        () => {
                            const links = [];
                            document.querySelectorAll('a[href]').forEach(a => {
                                const href = a.href;
                                const text = a.innerText.trim();
                                if (href && text && !href.startsWith('javascript:')) {
                                    links.push({url: href, text: text.substring(0, 100)});
                                }
                            });
                            return links.slice(0, 50);  // Limit to 50 links
                        }
                    """)

                    data["links"] = links
                    data["link_count"] = len(links)

                    output_parts.append("=== LINKS ===")
                    for link in links:
                        output_parts.append(f"- {link['text']}: {link['url']}")
                    output_parts.append("")

                return str(
                    ToolResult(
                        True,
                        "\n".join(output_parts),
                        data=data,
                    )
                )

            finally:
                await page.close()

        except Exception as e:
            self.logger.error(f"Web fetch error: {e}")
            return str(ToolResult(False, "", error=f"Fetch failed: {str(e)}"))
