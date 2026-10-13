"""A real server and a fresh browser context for every E2E test."""

import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from app.main import create_app


# Chromium 拒绝访问的"不安全端口"黑名单（net::ERR_UNSAFE_PORT）。
# 随机端口可能刚好抽到这里面，所以绑定时要跳过。
_UNSAFE_PORTS = {
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53,
    69, 77, 79, 87, 95, 101, 102, 103, 104, 105, 106, 107, 109, 110,
    111, 113, 115, 117, 119, 123, 135, 137, 139, 143, 161, 179, 389,
    427, 465, 512, 513, 514, 515, 526, 530, 531, 532, 540, 548, 554,
    556, 563, 587, 604, 636, 989, 993, 995, 1719, 1720, 1723, 2049,
    3659, 4045, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669,
    9100,
}


@pytest.fixture
def live_server(tmp_path: Path) -> Iterator[str]:
    # Reserve a free port, skipping any port on Chromium's unsafe-port blacklist.
    sock = None
    for _ in range(20):
        candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        candidate.bind(("127.0.0.1", 0))
        host, port = candidate.getsockname()
        if port not in _UNSAFE_PORTS:
            sock = candidate
            break
        candidate.close()
    if sock is None:
        raise RuntimeError("Could not find a safe local port for the E2E server")

    try:
        config = uvicorn.Config(
            create_app(tmp_path / "browser-cars.db"),
            host=host,
            port=port,
            log_level="error",
            ws="none",
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("The E2E server did not start")
                time.sleep(0.02)
            yield f"http://{host}:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("The E2E server did not stop")
    finally:
        sock.close()


@pytest.fixture(scope="session")
def browser(pytestconfig):
    # Import lazily so non-E2E tests do not need a browser installation.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        options = {"headless": not pytestconfig.getoption("--headed")}
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(browser):
    # No cookies, local storage, or browser state is shared between tests.
    context = browser.new_context()
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()
