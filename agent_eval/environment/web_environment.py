"""Web Environment Module - Simplified browser management."""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import io

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from loguru import logger


class WebEnvironment:
    """Web environment for agent evaluation using Playwright."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize web environment with configuration."""
        self.config = config or {}
        self.browser_config = self.config.get("browser", {})

        # Browser instances
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # State tracking
        self.is_initialized = False
        self.current_url = None

        logger.info("WebEnvironment initialized")

    async def initialize(self) -> None:
        """Initialize browser and create new page with simplified startup."""
        try:
            self.playwright = await async_playwright().start()

            # Get browser launcher
            browser_type = self.browser_config.get("type", "chromium")
            browser_launchers = {
                "chromium": self.playwright.chromium,
                "firefox": self.playwright.firefox,
                "webkit": self.playwright.webkit
            }

            if browser_type not in browser_launchers:
                raise ValueError(f"Unsupported browser type: {browser_type}")

            # Get window and display settings
            headless = self.browser_config.get("headless", False)
            viewport = self.browser_config.get("viewport", {"width": 1280, "height": 720})

            # window_size 优先，如果没有设置则使用 viewport + 额外空间给浏览器 UI
            if "window_size" in self.browser_config:
                window_size = self.browser_config["window_size"]
            else:
                # 为浏览器 UI 预留空间：宽度+16，高度+88
                window_size = {
                    "width": viewport["width"] + 16,
                    "height": viewport["height"] + 88
                }

            window_position = self.browser_config.get("window_position", {"x": 0, "y": 0})
            device_scale_factor = self.browser_config.get("device_scale_factor", 1.0)

            # Build launch options with window parameters
            launch_options = {
                'headless': headless,
                'slow_mo': self.browser_config.get("slow_mo", 0),
                'args': [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    f'--window-size={window_size["width"]},{window_size["height"]}',
                    f'--window-position={window_position["x"]},{window_position["y"]}',
                    f'--force-device-scale-factor={device_scale_factor}',
                    '--ignore-ssl-errors',
                    '--ignore-certificate-errors',
                    '--disable-web-security',
                    '--disable-software-rasterizer',
                    '--allow-running-insecure-content',
                    '--disable-extensions',
                    '--log-level=3'
                ]
            }

            # Add additional args for non-headless mode
            if not headless:
                launch_options['args'].extend([
                    "--no-first-run",
                    "--disable-default-apps"
                ])

            self.browser = await browser_launchers[browser_type].launch(**launch_options)

            # Prepare context options
            context_options = {
                'viewport': viewport,
                'ignore_https_errors': True,
                'device_scale_factor': device_scale_factor
            }

            # Handle mobile emulation
            mobile_emulation = self.browser_config.get('mobile_emulation')
            if mobile_emulation and 'deviceName' in mobile_emulation:
                device_name = mobile_emulation['deviceName']
                # Use Playwright's built-in device emulation
                device = self.playwright.devices.get(device_name)
                if device:
                    # Apply device settings but preserve our custom device_scale_factor
                    custom_device_scale_factor = context_options.get('device_scale_factor', 1.0)
                    context_options.update(device)
                    context_options['device_scale_factor'] = custom_device_scale_factor
                    logger.info(f"Mobile emulation enabled: {device_name} with custom scale factor: {custom_device_scale_factor}")
                else:
                    logger.warning(f"Device '{device_name}' not found, using custom settings")

            # Create context and page with settings
            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.browser_config.get("timeout", 30000))

            self.is_initialized = True

            # Log initialization details
            mobile_info = ""
            if mobile_emulation and 'deviceName' in mobile_emulation:
                mobile_info = f", mobile_device: {mobile_emulation['deviceName']}"

            logger.info(f"Browser initialized: {browser_type} with viewport {viewport}, window_size {window_size}, position {window_position}, scale {device_scale_factor}{mobile_info}")

        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            await self.cleanup()
            raise
    
    async def launch_webpage(self, url_or_path: str) -> bool:
        """Navigate to a target webpage or local file with simplified loading."""
        if not self.is_initialized:
            await self.initialize()

        try:
            # Handle local file paths and special URLs
            if not url_or_path.startswith(('http://', 'https://', 'file://', 'about:', 'data:')):
                path = Path(url_or_path).resolve()
                if path.exists():
                    url_or_path = f"file://{path}"
                else:
                    logger.error(f"Local file not found: {path}")
                    return False

            # Navigate to the page and wait for it to load
            await self.page.goto(url_or_path, wait_until="domcontentloaded")

            # Simple focus without complex validation
            await self.page.bring_to_front()

            # Brief wait for rendering
            await asyncio.sleep(0.2)

            self.current_url = url_or_path
            logger.info(f"Navigated to: {url_or_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to navigate to {url_or_path}: {e}")
            return False
    
    async def get_screenshot(self, full_page: bool = False) -> Optional[Image.Image]:
        """
        Capture current page state with simplified screenshot logic.

        Args:
            full_page: Whether to capture full page or just viewport

        Returns:
            PIL Image or None if failed
        """
        if not self.page:
            logger.error("Page not initialized")
            return None

        try:
            # Use standard Playwright screenshot method for simplicity
            screenshot_bytes = await self.page.screenshot(
                full_page=full_page,
                type="png"
            )

            # Convert to PIL Image
            image = Image.open(io.BytesIO(screenshot_bytes))

            logger.debug(f"Screenshot captured: {image.size}")
            return image

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    async def scroll(self, direction: str, amount: int, dx: int = 0, dy: int = 0, x: int = None, y: int = None) -> bool:
        """
        Scroll page vertically/horizontally, optionally from a specific coordinate position.

        Args:
            direction: 'up', 'down', 'left', 'right'
            amount: Scroll amount in pixels
            dx: Additional horizontal offset
            dy: Additional vertical offset
            x: Optional X coordinate to position mouse before scrolling (screenshot coordinates)
            y: Optional Y coordinate to position mouse before scrolling (screenshot coordinates)

        Returns:
            bool: True if scroll successful, False otherwise
        """
        if not self.page:
            logger.error("Page not initialized")
            return False

        try:
            # If coordinates are provided, move mouse to that position first
            if x is not None and y is not None:
                # Convert screenshot coordinates to browser coordinates
                device_scale_factor = self.browser_config.get("device_scale_factor", 1.0)
                actual_x = x / device_scale_factor
                actual_y = y / device_scale_factor
                await self.page.mouse.move(actual_x, actual_y)
                logger.debug(f"Moved mouse to screenshot coordinates ({x}, {y}) -> browser coordinates ({actual_x}, {actual_y}) before scrolling")

            # Calculate scroll deltas
            if direction == "down":
                delta_y = amount + dy
                delta_x = dx
            elif direction == "up":
                delta_y = -(amount + dy)
                delta_x = dx
            elif direction == "right":
                delta_x = amount + dx
                delta_y = dy
            elif direction == "left":
                delta_x = -(amount + dx)
                delta_y = dy
            else:
                logger.error(f"Invalid scroll direction: {direction}")
                return False

            await self.page.mouse.wheel(delta_x, delta_y)

            if x is not None and y is not None:
                logger.success(f"Scrolled {direction} by {amount} pixels from coordinates ({x}, {y}) (dx={dx}, dy={dy})")
            else:
                logger.success(f"Scrolled {direction} by {amount} pixels (dx={dx}, dy={dy})")
            return True

        except Exception as e:
            logger.error(f"Failed to scroll: {e}")
            return False

    async def click(self, x: int, y: int) -> bool:
        """
        Click at specified coordinates with simplified logic.

        Args:
            x: X coordinate (screenshot coordinates)
            y: Y coordinate (screenshot coordinates)

        Returns:
            bool: True if click successful, False otherwise
        """
        if not self.page:
            logger.error("Page not initialized")
            return False

        try:
            # Convert screenshot coordinates to browser coordinates
            # Account for device_scale_factor
            device_scale_factor = self.browser_config.get("device_scale_factor", 1.0)
            actual_x = x / device_scale_factor
            actual_y = y / device_scale_factor

            await self.page.mouse.click(actual_x, actual_y)
            logger.success(f"Clicked at screenshot coordinates ({x}, {y}) -> browser coordinates ({actual_x}, {actual_y})")
            return True

        except Exception as e:
            logger.error(f"Failed to click at ({x}, {y}): {e}")
            return False

    async def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """
        Drag from start to end position.

        Args:
            start_x: Starting X coordinate (screenshot coordinates)
            start_y: Starting Y coordinate (screenshot coordinates)
            end_x: Ending X coordinate (screenshot coordinates)
            end_y: Ending Y coordinate (screenshot coordinates)

        Returns:
            bool: True if drag successful, False otherwise
        """
        if not self.page:
            logger.error("Page not initialized")
            return False

        try:
            # Convert screenshot coordinates to browser coordinates
            # Account for device_scale_factor
            device_scale_factor = self.browser_config.get("device_scale_factor", 1.0)
            actual_start_x = start_x / device_scale_factor
            actual_start_y = start_y / device_scale_factor
            actual_end_x = end_x / device_scale_factor
            actual_end_y = end_y / device_scale_factor

            await self.page.mouse.move(actual_start_x, actual_start_y)
            await self.page.mouse.down()
            await self.page.mouse.move(actual_end_x, actual_end_y)
            await self.page.mouse.up()
            logger.success(f"Dragged from screenshot coordinates ({start_x}, {start_y}) to ({end_x}, {end_y}) -> browser coordinates ({actual_start_x}, {actual_start_y}) to ({actual_end_x}, {actual_end_y})")
            return True

        except Exception as e:
            logger.error(f"Failed to drag from ({start_x}, {start_y}) to ({end_x}, {end_y}): {e}")
            return False

    async def ensure_page_focus(self) -> bool:
        """
        Ensure the page is focused with simplified logic.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.page:
            logger.error("Page not initialized")
            return False

        try:
            # Simple focus operation
            await self.page.bring_to_front()
            return True

        except Exception as e:
            logger.error(f"Failed to ensure page focus: {e}")
            return False

    async def input_text(self, text: str, element_selector: Optional[str] = None,
                        x: Optional[int] = None, y: Optional[int] = None,
                        replace_mode: bool = False) -> bool:
        """
        Type text into form fields using selector or coordinates.

        Args:
            text: Text to input. Special values:
                  - 'delete' or 'backspace': Perform delete operation
                  - Any other text: Input the text
            element_selector: CSS selector for target element (optional)
            x: X coordinate to click before typing (optional)
            y: Y coordinate to click before typing (optional)
            replace_mode: If True, replace existing text instead of appending

        Returns:
            bool: True if input successful, False otherwise
        """
        if not self.page:
            logger.error("Page not initialized")
            return False

        try:
            # Handle delete operations
            if text.lower() in ['delete', 'backspace']:
                return await self._handle_delete_operation(element_selector, x, y)

            if element_selector:
                # Use element selector
                element = await self.page.wait_for_selector(element_selector, timeout=5000)
                if element:
                    await element.click()
                    if replace_mode:
                        # Clear existing content and set new text
                        await element.fill(text)
                    else:
                        # Append to existing content
                        await element.type(text)
                    logger.debug(f"Input text to element '{element_selector}': {text[:50]}...")
                else:
                    logger.error(f"Element not found: {element_selector}")
                    return False
            elif x is not None and y is not None:
                # Use coordinates - convert screenshot coordinates to browser coordinates
                device_scale_factor = self.browser_config.get("device_scale_factor", 1.0)
                actual_x = x / device_scale_factor
                actual_y = y / device_scale_factor
                await self.page.mouse.click(actual_x, actual_y)

                if replace_mode:
                    # Select all text and replace
                    await self.page.keyboard.press("Control+a")
                    await self.page.keyboard.type(text)
                else:
                    # Append to existing content
                    await self.page.keyboard.type(text)
                logger.success(f"Input text at screenshot coordinates ({x}, {y}) -> browser coordinates ({actual_x}, {actual_y}): {text[:50]}...")
            else:
                # Type at current focus
                if replace_mode:
                    # Select all text and replace
                    await self.page.keyboard.press("Control+a")
                    await self.page.keyboard.type(text)
                else:
                    # Append to existing content
                    await self.page.keyboard.type(text)
                logger.success(f"Input text at current focus: {text[:50]}...")

            return True

        except Exception as e:
            logger.error(f"Failed to input text: {e}")
            return False

    async def _handle_delete_operation(self, element_selector: Optional[str] = None,
                                     x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """
        Handle delete/backspace operations.

        Args:
            element_selector: CSS selector for target element (optional)
            x: X coordinate to click before deleting (optional)
            y: Y coordinate to click before deleting (optional)

        Returns:
            bool: True if delete successful, False otherwise
        """
        try:
            if element_selector:
                # Use element selector
                element = await self.page.wait_for_selector(element_selector, timeout=5000)
                if element:
                    await element.click()
                    # Select all and delete
                    await self.page.keyboard.press("Control+a")
                    await self.page.keyboard.press("Delete")
                    logger.debug(f"Deleted content in element '{element_selector}'")
                else:
                    logger.error(f"Element not found: {element_selector}")
                    return False
            elif x is not None and y is not None:
                # Use coordinates
                device_scale_factor = self.browser_config.get("device_scale_factor", 1.0)
                actual_x = x / device_scale_factor
                actual_y = y / device_scale_factor
                await self.page.mouse.click(actual_x, actual_y)
                # Select all and delete
                await self.page.keyboard.press("Control+a")
                await self.page.keyboard.press("Delete")
                logger.success(f"Deleted content at coordinates ({x}, {y})")
            else:
                # Delete at current focus
                await self.page.keyboard.press("Control+a")
                await self.page.keyboard.press("Delete")
                logger.success("Deleted content at current focus")

            return True

        except Exception as e:
            logger.error(f"Failed to delete content: {e}")
            return False

    async def set_text_at_coordinates(self, text: str, x: int, y: int) -> bool:
        """
        Set text directly at specified coordinates, replacing any existing content.
        This is a convenience method that uses replace_mode=True.

        Args:
            text: Text to set
            x: X coordinate (screenshot coordinates)
            y: Y coordinate (screenshot coordinates)

        Returns:
            bool: True if successful, False otherwise
        """
        return await self.input_text(text, x=x, y=y, replace_mode=True)

    async def execute_javascript(self, javascript_code: str) -> Any:
        """
        Execute JavaScript code in the browser console and return the result.

        Args:
            javascript_code: JavaScript code to execute

        Returns:
            Any: Result of the JavaScript execution, or None if failed
        """
        if not self.page:
            logger.error("Page not initialized")
            return None

        try:
            result = await self.page.evaluate(javascript_code)
            logger.debug(f"Executed JavaScript: {javascript_code[:100]}...")
            return result

        except Exception as e:
            logger.error(f"Failed to execute JavaScript: {e}")
            return None

    async def get_page_status(self) -> Dict[str, Any]:
        """
        Get detailed page status for debugging.

        Returns:
            Dict containing page status information
        """
        if not self.page:
            return {"error": "Page not initialized"}

        try:
            status = {
                "url": self.current_url,
                "is_closed": self.page.is_closed(),
                "viewport": await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })"),
                "document_ready": await self.page.evaluate("() => document.readyState"),
                "has_focus": await self.page.evaluate("() => document.hasFocus()"),
                "is_visible": await self.page.evaluate("() => !document.hidden"),
                "page_title": await self.page.title(),
                "browser_contexts": len(self.browser.contexts) if self.browser else 0
            }

            # Check if there are multiple pages in the context
            if self.context:
                status["pages_in_context"] = len(self.context.pages)
                status["active_page_url"] = self.page.url

            return status

        except Exception as e:
            return {"error": f"Failed to get page status: {e}"}

    async def reset(self) -> bool:
        """
        Reset browser to clean state.

        Returns:
            bool: True if reset successful, False otherwise
        """
        try:
            if self.page:
                # Clear cookies and local storage
                await self.context.clear_cookies()
                await self.page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")

                # Navigate to blank page
                await self.page.goto("about:blank")
                self.current_url = None

                logger.info("Browser reset to clean state")
                return True
            else:
                logger.warning("No page to reset")
                return False

        except Exception as e:
            logger.error(f"Failed to reset browser: {e}")
            return False

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self.page:
                await self.page.close()
                self.page = None

            if self.context:
                await self.context.close()
                self.context = None

            if self.browser:
                await self.browser.close()
                self.browser = None

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None

            self.is_initialized = False
            logger.info("Browser cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    def __del__(self):
        """Destructor to ensure cleanup."""
        if self.is_initialized:
            logger.warning("WebEnvironment not properly cleaned up, forcing cleanup")
            # Note: Can't call async cleanup in __del__, should use context manager
