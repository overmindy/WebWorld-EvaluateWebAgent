"""Web Environment Module - Simplified browser management."""

import asyncio
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union, TypedDict
from PIL import Image
import io

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, CDPSession
from loguru import logger

# Constants for text extraction
ASCII_CHARSET = "".join(chr(x) for x in range(32, 128))
FREQ_UNICODE_CHARSET = "".join(chr(x) for x in range(129, 1000))
UTTERANCE_MAX_LENGTH = 8192
IN_VIEWPORT_RATIO_THRESHOLD = 0.6

IGNORED_ACTREE_PROPERTIES = (
    "focusable",
    "editable",
    "readonly",
    "level",
    "settable",
    "multiline",
    "invalid",
)

# Type definitions for text extraction
class DOMNode(TypedDict):
    nodeId: str
    nodeType: str
    nodeName: str
    nodeValue: str
    attributes: str
    backendNodeId: str
    parentId: str
    childIds: List[str]
    cursor: int
    union_bound: Optional[List[float]]

class AccessibilityTreeNode(TypedDict):
    nodeId: str
    ignored: bool
    role: Dict[str, Any]
    chromeRole: Dict[str, Any]
    name: Dict[str, Any]
    properties: List[Dict[str, Any]]
    childIds: List[str]
    parentId: str
    backendDOMNodeId: str
    frameId: str
    bound: Optional[List[float]]
    union_bound: Optional[List[float]]
    offsetrect_bound: Optional[List[float]]

class BrowserConfig(TypedDict):
    win_top_bound: float
    win_left_bound: float
    win_width: float
    win_height: float
    win_right_bound: float
    win_lower_bound: float
    device_pixel_ratio: float

class BrowserInfo(TypedDict):
    DOMTree: Dict[str, Any]
    config: BrowserConfig

class TextExtractionMetadata(TypedDict):
    obs_nodes_info: Dict[str, Any]

DOMTree = List[DOMNode]
AccessibilityTree = List[AccessibilityTreeNode]


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
        self.cdp_session: Optional[CDPSession] = None

        # State tracking
        self.is_initialized = False
        self.current_url = None

        # Text extraction metadata
        self.text_extraction_metadata: TextExtractionMetadata = {"obs_nodes_info": {}}

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

            # Initialize CDP session for text extraction
            self.cdp_session = await self.context.new_cdp_session(self.page)
            # Enable accessibility tree access
            await self.cdp_session.send("Accessibility.enable")

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
            elif direction == "custom":
                # For custom direction, use dx and dy directly
                delta_x = dx*3.33333
                delta_y = dy*3.33333
                logger.debug(f"Using custom scroll direction: ({delta_x}, {delta_y})")
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

        logger.debug(f"Replace mode: {replace_mode}")

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
                    logger.debug(f"Input text to element '{element_selector}': {text}")
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
                logger.success(f"Input text at screenshot coordinates ({x}, {y}) -> browser coordinates ({actual_x}, {actual_y}): {text}")
            else:
                # Type at current focus
                if replace_mode:
                    # Select all text and replace
                    await self.page.keyboard.press("Control+a")
                    await self.page.keyboard.type(text)
                else:
                    # Append to existing content
                    await self.page.keyboard.type(text)
                logger.success(f"Input text at current focus: {text}")

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
            # Close CDP session first
            if self.cdp_session:
                try:
                    await self.cdp_session.detach()
                except:
                    pass
                self.cdp_session = None

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
            # Reset text extraction metadata
            self.text_extraction_metadata = {"obs_nodes_info": {}}
            logger.info("Browser cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    # Text extraction methods
    async def fetch_browser_info(self) -> BrowserInfo:
        """Fetch browser information including DOM tree and configuration."""
        if not self.page or not self.cdp_session:
            raise RuntimeError("Browser not initialized or CDP session not available")

        # Extract DOM tree using CDP
        tree = await self.cdp_session.send(
            "DOMSnapshot.captureSnapshot",
            {
                "computedStyles": [],
                "includeDOMRects": True,
                "includePaintOrder": True,
            },
        )

        # Get viewport size for bounds calibration
        viewport = await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")

        # Calibrate the bounds - in some cases, the bounds are scaled somehow
        bounds = tree["documents"][0]["layout"]["bounds"]
        if bounds:
            b = bounds[0]
            n = b[2] / viewport["width"] if b[2] != 0 else 1.0
            bounds = [[x / n for x in bound] for bound in bounds]
            tree["documents"][0]["layout"]["bounds"] = bounds

        # Extract browser window information
        win_top_bound = await self.page.evaluate("window.pageYOffset")
        win_left_bound = await self.page.evaluate("window.pageXOffset")
        win_width = await self.page.evaluate("window.screen.width")
        win_height = await self.page.evaluate("window.screen.height")
        win_right_bound = win_left_bound + win_width
        win_lower_bound = win_top_bound + win_height
        device_pixel_ratio = await self.page.evaluate("window.devicePixelRatio")

        # Force device pixel ratio to 1.0 for consistency
        device_pixel_ratio = 1.0

        config: BrowserConfig = {
            "win_top_bound": win_top_bound,
            "win_left_bound": win_left_bound,
            "win_width": win_width,
            "win_height": win_height,
            "win_right_bound": win_right_bound,
            "win_lower_bound": win_lower_bound,
            "device_pixel_ratio": device_pixel_ratio,
        }

        info: BrowserInfo = {"DOMTree": tree, "config": config}
        return info

    async def get_bounding_client_rect(self, backend_node_id: str) -> Dict[str, Any]:
        """Get bounding client rect for a DOM node."""
        if not self.cdp_session:
            return {"result": {"subtype": "error"}}

        try:
            remote_object = await self.cdp_session.send(
                "DOM.resolveNode", {"backendNodeId": int(backend_node_id)}
            )
            remote_object_id = remote_object["object"]["objectId"]
            response = await self.cdp_session.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": remote_object_id,
                    "functionDeclaration": """
                        function() {
                            if (this.nodeType == 3) {
                                var range = document.createRange();
                                range.selectNode(this);
                                var rect = range.getBoundingClientRect().toJSON();
                                range.detach();
                                return rect;
                            } else {
                                return this.getBoundingClientRect().toJSON();
                            }
                        }
                    """,
                    "returnByValue": True,
                },
            )
            return response
        except Exception as e:
            return {"result": {"subtype": "error"}}

    @staticmethod
    def get_element_in_viewport_ratio(
        elem_left_bound: float,
        elem_top_bound: float,
        width: float,
        height: float,
        config: BrowserConfig,
    ) -> float:
        """Calculate the ratio of element that is visible in viewport."""
        elem_right_bound = elem_left_bound + width
        elem_lower_bound = elem_top_bound + height

        win_left_bound = 0
        win_right_bound = config["win_width"]
        win_top_bound = 0
        win_lower_bound = config["win_height"]

        # Compute the overlap in x and y axes
        overlap_width = max(
            0,
            min(elem_right_bound, win_right_bound)
            - max(elem_left_bound, win_left_bound),
        )
        overlap_height = max(
            0,
            min(elem_lower_bound, win_lower_bound)
            - max(elem_top_bound, win_top_bound),
        )

        # Compute the overlap area
        if width * height == 0:
            return 0.0
        ratio = overlap_width * overlap_height / (width * height)
        return ratio

    async def fetch_page_html(
        self,
        info: BrowserInfo,
        current_viewport_only: bool = True,
    ) -> DOMTree:
        """Fetch and process the page HTML into a DOM tree structure."""
        tree = info["DOMTree"]
        strings = tree["strings"]
        document = tree["documents"][0]
        nodes = document["nodes"]

        # Build a navigable DOM tree
        dom_tree: DOMTree = []
        graph = defaultdict(list)

        for node_idx in range(len(nodes["nodeName"])):
            cur_node: DOMNode = {
                "nodeId": "",
                "nodeType": "",
                "nodeName": "",
                "nodeValue": "",
                "attributes": "",
                "backendNodeId": "",
                "parentId": "",
                "childIds": [],
                "cursor": 0,
                "union_bound": None,
            }

            node_type_idx = nodes["nodeType"][node_idx]
            node_type = "generic"
            if node_type_idx >= 0 and node_type_idx < len(strings):
                node_type = strings[node_type_idx]

            node_name = strings[nodes["nodeName"][node_idx]]

            node_value_idx = nodes["nodeValue"][node_idx]
            node_value = ""
            if node_value_idx >= 0 and node_value_idx < len(strings):
                node_value = " ".join(strings[node_value_idx].split())

            node_attributes = [
                strings[i] for i in nodes["attributes"][node_idx]
            ]
            node_attributes_str = ""
            for i in range(0, len(node_attributes), 2):
                a = node_attributes[i]
                b = node_attributes[i + 1]
                b = " ".join(b.split())
                node_attributes_str += f'{a}="{b}" '
            node_attributes_str = node_attributes_str.strip()

            cur_node["nodeId"] = str(node_idx)
            cur_node["nodeType"] = node_type
            cur_node["nodeName"] = node_name
            cur_node["nodeValue"] = node_value
            cur_node["attributes"] = node_attributes_str
            cur_node["backendNodeId"] = str(nodes["backendNodeId"][node_idx])
            cur_node["parentId"] = str(nodes["parentIndex"][node_idx])

            if cur_node["parentId"] != "-1":
                graph[cur_node["parentId"]].append(str(cur_node["nodeId"]))

            # Get the bounding box
            if cur_node["parentId"] == "-1":
                cur_node["union_bound"] = [0.0, 0.0, 10.0, 10.0]
            else:
                response = await self.get_bounding_client_rect(
                    cur_node["backendNodeId"]
                )
                if response.get("result", {}).get("subtype", "") == "error":
                    cur_node["union_bound"] = None
                else:
                    x = response["result"]["value"]["x"]
                    y = response["result"]["value"]["y"]
                    width = response["result"]["value"]["width"]
                    height = response["result"]["value"]["height"]
                    cur_node["union_bound"] = [x, y, width, height]

            dom_tree.append(cur_node)

        # Add parent-children relationships
        for parent_id, child_ids in graph.items():
            dom_tree[int(parent_id)]["childIds"] = child_ids

        # Filter nodes not in current viewport if requested
        if current_viewport_only:
            dom_tree = await self._filter_viewport_nodes(dom_tree, info["config"])

        return dom_tree

    async def _filter_viewport_nodes(self, dom_tree: DOMTree, config: BrowserConfig) -> DOMTree:
        """Filter DOM tree to only include nodes visible in current viewport."""
        def remove_node_in_graph(node: DOMNode) -> None:
            node_id = node["nodeId"]
            parent_id = node["parentId"]
            child_ids = node["childIds"]

            # Update the children of the parent node
            if parent_id != "-1" and int(parent_id) < len(dom_tree):
                parent_node = dom_tree[int(parent_id)]
                if parent_node["parentId"] != "[REMOVED]":
                    # Remove the node_id from parent
                    if node_id in parent_node["childIds"]:
                        index = parent_node["childIds"].index(node_id)
                        parent_node["childIds"].pop(index)

                        # Insert children_nodeids in the same location
                        for child_id in child_ids:
                            parent_node["childIds"].insert(index, child_id)
                            index += 1

            # Update children node's parent
            for child_id in child_ids:
                if int(child_id) < len(dom_tree):
                    dom_tree[int(child_id)]["parentId"] = parent_id

            # Mark as removed
            dom_tree[int(node_id)]["parentId"] = "[REMOVED]"

        for node in dom_tree:
            if not node["union_bound"]:
                remove_node_in_graph(node)
                continue

            x, y, width, height = node["union_bound"]

            # Skip invisible nodes
            if width == 0.0 or height == 0.0:
                remove_node_in_graph(node)
                continue

            in_viewport_ratio = self.get_element_in_viewport_ratio(
                elem_left_bound=float(x),
                elem_top_bound=float(y),
                width=float(width),
                height=float(height),
                config=config,
            )

            if in_viewport_ratio < IN_VIEWPORT_RATIO_THRESHOLD:
                remove_node_in_graph(node)

        # Return only non-removed nodes
        return [
            node
            for node in dom_tree
            if node.get("parentId", "-1") != "[REMOVED]"
        ]

    async def fetch_page_accessibility_tree(
        self,
        info: BrowserInfo,
        current_viewport_only: bool = True,
    ) -> AccessibilityTree:
        """Fetch and process the page accessibility tree."""
        if not self.cdp_session:
            raise RuntimeError("CDP session not available")

        accessibility_tree: AccessibilityTree = (await self.cdp_session.send(
            "Accessibility.getFullAXTree", {}
        ))["nodes"]

        # Remove duplicate nodes (some nodes are repeated in the accessibility tree)
        seen_ids = set()
        _accessibility_tree = []
        for node in accessibility_tree:
            if node["nodeId"] not in seen_ids:
                _accessibility_tree.append(node)
                seen_ids.add(node["nodeId"])
        accessibility_tree = _accessibility_tree

        nodeid_to_cursor = {}
        for cursor, node in enumerate(accessibility_tree):
            nodeid_to_cursor[node["nodeId"]] = cursor

            # Get bounding box for nodes with backend DOM node ID
            if "backendDOMNodeId" not in node:
                node["union_bound"] = None
                continue

            backend_node_id = str(node["backendDOMNodeId"])
            if node["role"]["value"] == "RootWebArea":
                # Root web area is always inside the viewport
                node["union_bound"] = [0.0, 0.0, 10.0, 10.0]
            else:
                response = await self.get_bounding_client_rect(backend_node_id)
                if response.get("result", {}).get("subtype", "") == "error":
                    node["union_bound"] = None
                else:
                    x = response["result"]["value"]["x"]
                    y = response["result"]["value"]["y"]
                    width = response["result"]["value"]["width"]
                    height = response["result"]["value"]["height"]
                    node["union_bound"] = [x, y, width, height]

        # Filter nodes not in current viewport if requested
        if current_viewport_only:
            accessibility_tree = await self._filter_accessibility_viewport_nodes(
                accessibility_tree, nodeid_to_cursor, info["config"]
            )

        return accessibility_tree

    async def _filter_accessibility_viewport_nodes(
        self,
        accessibility_tree: AccessibilityTree,
        nodeid_to_cursor: Dict[str, int],
        config: BrowserConfig
    ) -> AccessibilityTree:
        """Filter accessibility tree to only include nodes visible in current viewport."""
        def remove_node_in_graph(node: AccessibilityTreeNode) -> None:
            nodeid = node["nodeId"]
            node_cursor = nodeid_to_cursor[nodeid]
            parent_nodeid = node["parentId"]
            children_nodeids = node["childIds"]

            if parent_nodeid in nodeid_to_cursor:
                parent_cursor = nodeid_to_cursor[parent_nodeid]
                parent_node = accessibility_tree[parent_cursor]

                # Update the children of the parent node
                if parent_node.get("parentId") is not None:
                    # Remove the nodeid from parent's childIds
                    if nodeid in parent_node["childIds"]:
                        index = parent_node["childIds"].index(nodeid)
                        parent_node["childIds"].pop(index)

                        # Insert children_nodeids in the same location
                        for child_nodeid in children_nodeids:
                            parent_node["childIds"].insert(index, child_nodeid)
                            index += 1

            # Update children node's parent
            for child_nodeid in children_nodeids:
                if child_nodeid in nodeid_to_cursor:
                    child_cursor = nodeid_to_cursor[child_nodeid]
                    accessibility_tree[child_cursor]["parentId"] = parent_nodeid

            # Mark as removed
            accessibility_tree[node_cursor]["parentId"] = "[REMOVED]"

        for node in accessibility_tree:
            if not node["union_bound"]:
                remove_node_in_graph(node)
                continue

            x, y, width, height = node["union_bound"]

            # Skip invisible nodes
            if width == 0 or height == 0:
                remove_node_in_graph(node)
                continue

            in_viewport_ratio = self.get_element_in_viewport_ratio(
                elem_left_bound=float(x),
                elem_top_bound=float(y),
                width=float(width),
                height=float(height),
                config=config,
            )

            if in_viewport_ratio < IN_VIEWPORT_RATIO_THRESHOLD:
                remove_node_in_graph(node)

        # Return only non-removed nodes
        return [
            node
            for node in accessibility_tree
            if node.get("parentId", "Root") != "[REMOVED]"
        ]

    @staticmethod
    def parse_html(dom_tree: DOMTree) -> Tuple[str, Dict[str, Any]]:
        """Parse the HTML DOM tree into a string text representation."""
        obs_nodes_info = {}
        nodeid_to_cursor = {
            node["nodeId"]: idx for idx, node in enumerate(dom_tree)
        }
        def dfs(node_cursor: int, depth: int) -> str:
            tree_str = ""
            node = dom_tree[node_cursor]
            indent = "\t" * depth
            valid_node = True

            try:
                node_str = f"[{node_cursor}] <{node['nodeName']}"
                if node["attributes"]:
                    node_str += f" {node['attributes']}"
                node_str += f"> {node['nodeValue']}"
                valid_node = bool(node["attributes"] or node["nodeValue"])

                if valid_node:
                    obs_nodes_info[str(node_cursor)] = {
                        "backend_id": node["backendNodeId"],
                        "union_bound": node["union_bound"],
                        "text": node_str,
                    }
                    tree_str += f"{indent}{node_str}\n"

            except Exception:
                valid_node = False

            for child_id in node["childIds"]:
                if child_id in nodeid_to_cursor:
                    child_cursor = nodeid_to_cursor[child_id]
                    child_depth = depth + 1 if valid_node else depth
                    child_str = dfs(child_cursor, child_depth)
                    tree_str += child_str

            return tree_str

        html = dfs(0, 0)
        return html, obs_nodes_info

    @staticmethod
    def parse_accessibility_tree(
        accessibility_tree: AccessibilityTree,
    ) -> Tuple[str, Dict[str, Any]]:
        """Parse the accessibility tree into a string text representation."""
        node_id_to_idx = {}
        for idx, node in enumerate(accessibility_tree):
            node_id_to_idx[node["nodeId"]] = idx

        obs_nodes_info = {}
        def dfs(idx: int, obs_node_id: str, depth: int) -> str:
            tree_str = ""
            node = accessibility_tree[idx]
            indent = "\t" * depth
            valid_node = True

            try:
                role = node["role"]["value"]
                name = node["name"]["value"]
                node_str = f"[{obs_node_id}] {role} {repr(name)}"
                properties = []

                for property in node.get("properties", []):
                    try:
                        if property["name"] in IGNORED_ACTREE_PROPERTIES:
                            continue
                        properties.append(
                            f'{property["name"]}: {property["value"]["value"]}'
                        )
                    except KeyError:
                        pass

                if properties:
                    node_str += " " + " ".join(properties)

                # Check if node is valid
                if not node_str.strip():
                    valid_node = False

                # Filter out empty generic nodes
                if not name.strip():
                    if not properties:
                        if role in [
                            "generic",
                            "img",
                            "list",
                            "strong",
                            "paragraph",
                            "banner",
                            "navigation",
                            "Section",
                            "LabelText",
                            "Legend",
                            "listitem",
                        ]:
                            valid_node = False
                    elif role in ["listitem"]:
                        valid_node = False

                if valid_node:
                    tree_str += f"{indent}{node_str}"
                    obs_nodes_info[obs_node_id] = {
                        "backend_id": node.get("backendDOMNodeId"),
                        "union_bound": node["union_bound"],
                        "text": node_str,
                    }

            except Exception:
                valid_node = False

            for child_node_id in node["childIds"]:
                if child_node_id not in node_id_to_idx:
                    continue

                child_depth = depth + 1 if valid_node else depth
                child_str = dfs(
                    node_id_to_idx[child_node_id], child_node_id, child_depth
                )
                if child_str.strip():
                    if tree_str.strip():
                        tree_str += "\n"
                    tree_str += child_str

            return tree_str

        tree_str = dfs(0, accessibility_tree[0]["nodeId"], 0)
        return tree_str, obs_nodes_info

    @staticmethod
    def clean_accessibility_tree(tree_str: str) -> str:
        """Further clean accessibility tree by removing redundant StaticText nodes."""
        clean_lines: List[str] = []
        for line in tree_str.split("\n"):
            # Remove statictext if the content already appears in the previous line
            if "statictext" in line.lower():
                prev_lines = clean_lines[-3:]
                pattern = r"\[\d+\] StaticText (.+)"

                match = re.search(pattern, line, re.DOTALL)
                if match:
                    static_text = match.group(1)[1:-1]  # remove the quotes
                    if static_text and all(
                        static_text not in prev_line
                        for prev_line in prev_lines
                    ):
                        clean_lines.append(line)
            else:
                clean_lines.append(line)

        return "\n".join(clean_lines)

    async def get_page_text_info(
        self,
        observation_type: str = "accessibility_tree",
        current_viewport_only: bool = True
    ) -> str:
        """
        Extract text information from the current page.

        Args:
            observation_type: Type of text extraction ("html" or "accessibility_tree")
            current_viewport_only: Whether to only include elements in current viewport

        Returns:
            String representation of the page structure with text information
        """
        if not self.page or not self.cdp_session:
            logger.error("Page or CDP session not initialized")
            return ""

        try:
            # Get tab information
            open_tabs = self.context.pages if self.context else []
            try:
                tab_titles = [await tab.title() for tab in open_tabs]
                current_tab_idx = open_tabs.index(self.page)
                for idx in range(len(open_tabs)):
                    if idx == current_tab_idx:
                        tab_titles[idx] = f"Tab {idx} (current): {tab_titles[idx]}"
                    else:
                        tab_titles[idx] = f"Tab {idx}: {tab_titles[idx]}"
                tab_title_str = " | ".join(tab_titles)
            except Exception:
                tab_title_str = " | ".join(
                    [f"Tab {idx}" for idx in range(len(open_tabs))]
                )

            # Fetch browser information
            try:
                browser_info = await self.fetch_browser_info()
            except Exception:
                # Wait for page load and retry
                await self.page.wait_for_load_state("load", timeout=500)
                browser_info = await self.fetch_browser_info()

            # Extract content based on observation type
            if observation_type == "html":
                dom_tree = await self.fetch_page_html(
                    browser_info,
                    current_viewport_only=current_viewport_only,
                )
                content, obs_nodes_info = self.parse_html(dom_tree)
                self.text_extraction_metadata["obs_nodes_info"] = obs_nodes_info

            elif observation_type == "accessibility_tree":
                accessibility_tree = await self.fetch_page_accessibility_tree(
                    browser_info,
                    current_viewport_only=current_viewport_only,
                )
                content, obs_nodes_info = self.parse_accessibility_tree(
                    accessibility_tree
                )
                content = self.clean_accessibility_tree(content)
                self.text_extraction_metadata["obs_nodes_info"] = obs_nodes_info

            else:
                raise ValueError(
                    f"Invalid observation type: {observation_type}. Use 'html' or 'accessibility_tree'"
                )

            # Combine tab information with content
            full_content = f"{tab_title_str}\n\n{content}"
            return full_content

        except Exception as e:
            logger.error(f"Failed to extract page text info: {e}")
            return ""

    async def get_element_center(self, element_id: str) -> Optional[Tuple[float, float]]:
        """
        Get the center coordinates of an element identified by its ID.

        Args:
            element_id: The element ID from text extraction

        Returns:
            Tuple of (x, y) coordinates as ratios of viewport size, or None if not found
        """
        if element_id not in self.text_extraction_metadata["obs_nodes_info"]:
            logger.warning(f"Element ID {element_id} not found in extracted nodes")
            return None

        try:
            node_info = self.text_extraction_metadata["obs_nodes_info"][element_id]
            node_bound = node_info["union_bound"]

            if not node_bound:
                return None

            x, y, width, height = node_bound
            center_x = x + width / 2
            center_y = y + height / 2

            # Get viewport size
            viewport = await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")

            return (
                center_x / viewport["width"],
                center_y / viewport["height"],
            )

        except Exception as e:
            logger.error(f"Failed to get element center for {element_id}: {e}")
            return None

    async def get_text_extraction_metadata(self) -> TextExtractionMetadata:
        """Get metadata from the last text extraction operation."""
        return self.text_extraction_metadata

    async def get_combined_page_info(
        self,
        include_screenshot: bool = True,
        include_html: bool = False,
        include_accessibility_tree: bool = True,
        current_viewport_only: bool = True
    ) -> Dict[str, Any]:
        """
        Get combined page information including screenshot and text data.

        Args:
            include_screenshot: Whether to include screenshot
            include_html: Whether to include HTML DOM tree text
            include_accessibility_tree: Whether to include accessibility tree text
            current_viewport_only: Whether to only include elements in current viewport

        Returns:
            Dictionary containing requested page information
        """
        result = {}

        if include_screenshot:
            screenshot = await self.get_screenshot()
            result["screenshot"] = screenshot

        if include_html:
            html_text = await self.get_page_text_info("html", current_viewport_only)
            result["html_text"] = html_text

        if include_accessibility_tree:
            accessibility_text = await self.get_page_text_info("accessibility_tree", current_viewport_only)
            result["accessibility_text"] = accessibility_text

        result["metadata"] = await self.get_text_extraction_metadata()
        result["url"] = self.current_url

        return result

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
