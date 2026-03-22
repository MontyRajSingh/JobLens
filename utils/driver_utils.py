"""
driver_utils.py — Selenium WebDriver factory.

Configures a headless Chrome instance with anti-detection flags.
Supports both local (ChromeDriverManager) and Docker/Railway (CHROME_BIN) setups.
"""

import os
import logging

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)


def setup_driver() -> webdriver.Chrome:
    """
    Create and return a configured headless Chrome WebDriver.

    Uses CHROME_OPTIONS from config for consistent browser fingerprinting.
    If the CHROME_BIN env var is set (e.g. in Docker), uses that binary
    instead of webdriver-manager auto-download.

    Returns:
        webdriver.Chrome: A ready-to-use Chrome WebDriver instance.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from config import CHROME_OPTIONS

    options = Options()
    for opt in CHROME_OPTIONS:
        options.add_argument(opt)

    # Anti-detection flags
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    chrome_bin = os.getenv("CHROME_BIN")
    if chrome_bin:
        # Docker / Railway: use the system-installed Chrome binary
        logger.info("Using CHROME_BIN: %s", chrome_bin)
        options.binary_location = chrome_bin
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
        service = ChromeService(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        # Local dev: auto-manage chromedriver
        from webdriver_manager.chrome import ChromeDriverManager
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

    # Remove navigator.webdriver flag
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    logger.info("Chrome WebDriver initialised successfully")
    return driver
