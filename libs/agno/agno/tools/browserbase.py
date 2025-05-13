
import json
from os import getenv
from typing import Optional, Dict

from agno.tools import Toolkit
from agno.utils.log import log_debug, logger

try:
    from browserbase import Browserbase
except ImportError:
    raise ImportError("`browserbase` is not installed. Install it with `pip install browserbase`.")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise ImportError(
        "`playwright` is not installed. Install it using `pip install playwright` and run `playwright install`."
    )


class BrowserbaseToolkit(Toolkit):
    def __init__(
        self,
        project_token: Optional[str] = None,
        auth_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the BrowserbaseToolkit.

        Args:
            project_token (Optional[str]): Project ID for Browserbase.
            auth_key (Optional[str]): API Key for authentication with Browserbase.
            api_endpoint (Optional[str]): Custom API URL for Browserbase (use for self-hosted or regional instances).
        """
        super().__init__(name="browserbase_toolkit", **kwargs)

        self.auth_key = auth_key or getenv("BROWSERBASE_API_KEY")
        if not self.auth_key:
            raise ValueError("Missing BROWSERBASE_API_KEY. Set the environment variable.")

        self.project_token = project_token or getenv("BROWSERBASE_PROJECT_ID")
        if not self.project_token:
            raise ValueError("Missing BROWSERBASE_PROJECT_ID. Set the environment variable.")

        self.api_endpoint = api_endpoint or getenv("BROWSERBASE_BASE_URL")

        if self.api_endpoint:
            self.client = Browserbase(api_key=self.auth_key, base_url=self.api_endpoint)
            log_debug(f"Connected using custom API endpoint: {self.api_endpoint}")
        else:
            self.client = Browserbase(api_key=self.auth_key)

        self._playwright = None
        self._browser = None
        self._page = None
        self._session = None
        self._connect_url = None

        self.register(self.visit_url)
        self.register(self.capture_screenshot)
        self.register(self.fetch_page_html)
        self.register(self.end_session)

    def _ensure_active_session(self):
        """Ensures there is an active Browserbase session."""
        if not self._session:
            try:
                self._session = self.client.sessions.create(project_id=self.project_token)
                self._connect_url = self._session.connect_url if self._session else ""
                if self._session:
                    log_debug(f"Session created with ID: {self._session.id}")
            except Exception as exc:
                logger.error(f"Session creation failed: {str(exc)}")
                raise

    def _start_browser(self, session_url: Optional[str] = None):
        """
        Start the browser using Playwright and connect to the session.

        Args:
            session_url (Optional[str]): URL to connect to an existing session. If not provided, a new session is created.
        """
        if session_url:
            self._connect_url = session_url
        elif not self._connect_url:
            self._ensure_active_session()

        if not self._playwright:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(self._connect_url)
            context = self._browser.contexts[0] if self._browser else None
            self._page = context.pages[0] if context.pages else context.new_page()

    def _shutdown_browser(self):
        """Properly shutdown browser and playwright instance."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._page = None

    def _create_new_session(self) -> Dict[str, str]:
        """Create and return a new Browserbase session info."""
        self._ensure_active_session()
        return {
            "session_id": self._session.id if self._session else "",
            "connect_url": self._session.connect_url if self._session else "",
        }

    def visit_url(self, destination: str, session_link: Optional[str] = None) -> str:
        """
        Navigate to a given URL.

        Args:
            destination (str): URL to visit.
            session_link (Optional[str]): Existing session connect URL if available.

        Returns:
            str: JSON containing navigation status and page title.
        """
        try:
            self._start_browser(session_link)
            if self._page:
                self._page.goto(destination, wait_until="networkidle")
            result = {
                "status": "success",
                "title": self._page.title() if self._page else "",
                "visited_url": destination
            }
            return json.dumps(result)
        except Exception as exc:
            self._shutdown_browser()
            raise exc

    def capture_screenshot(self, save_path: str, session_link: Optional[str] = None, capture_full: bool = True) -> str:
        """
        Capture a screenshot of the current page.

        Args:
            save_path (str): Path to save the screenshot.
            session_link (Optional[str]): Existing session connect URL if available.
            capture_full (bool): Whether to capture the full page or only the visible part.

        Returns:
            str: JSON containing status and file path.
        """
        try:
            self._start_browser(session_link)
            if self._page:
                self._page.screenshot(path=save_path, full_page=capture_full)
            return json.dumps({"status": "screenshot_taken", "file_path": save_path})
        except Exception as exc:
            self._shutdown_browser()
            raise exc

    def fetch_page_html(self, session_link: Optional[str] = None) -> str:
        """
        Fetch the current page's HTML content.

        Args:
            session_link (Optional[str]): Connect URL if reusing a session.

        Returns:
            str: HTML source of the page.
        """
        try:
            self._start_browser(session_link)
            return self._page.content() if self._page else ""
        except Exception as exc:
            self._shutdown_browser()
            raise exc

    def end_session(self) -> str:
        """
        End the current browser session and clean up resources.

        Returns:
            str: JSON with session closure status.
        """
        try:
            self._shutdown_browser()
            self._session = None
            self._connect_url = None

            return json.dumps({
                "status": "session_closed",
                "message": "Browser and session successfully terminated."
            })
        except Exception as exc:
            return json.dumps({
                "status": "warning",
                "message": f"Cleanup completed with errors: {str(exc)}"
            })
