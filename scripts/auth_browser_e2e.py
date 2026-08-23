"""Real-browser release gate for MathAI login and device Email history.

Playwright is intentionally a release-tool dependency, not an app dependency.
The script never prints the supplied controlled Email address.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Frame, Page, expect, sync_playwright


STORAGE_KEY = "mathai_recent_emails_v2"
SAFE_HISTORY = ["test-a@example.com", "test-b@example.com"]


def _login_surface(page: Page) -> Page | Frame:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        candidates: list[Page | Frame] = [page, *page.frames]
        for candidate in candidates:
            try:
                if candidate.get_by_role("button", name="顯示驗證碼（測試期間）").count():
                    return candidate
            except Exception:
                pass
        page.wait_for_timeout(250)
    raise AssertionError("login UI did not appear")


def _wait_for_login(page: Page) -> Page | Frame:
    surface = _login_surface(page)
    surface.get_by_text("學生登入／註冊", exact=True).wait_for(timeout=30_000)
    return surface


def _set_history(page: Page, values: list[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for component in page.frames:
            if "device_email_history_component.mathai_device_email_history" not in component.url:
                continue
            try:
                component.evaluate(
                    "([key, values]) => localStorage.setItem(key, JSON.stringify(values))",
                    [STORAGE_KEY, values],
                )
                component.evaluate("location.reload()")
                return
            except Exception:
                pass
        page.wait_for_timeout(250)
    raise AssertionError("device history component frame did not become stable")


def verify_history_ui(page: Page, url: str, *, mobile: bool = False) -> None:
    profile = "mobile" if mobile else "desktop"
    print(f"{profile}: opening login UI", flush=True)
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    surface = _wait_for_login(page)
    clear_button = surface.get_by_role(
        "button", name="清除這台裝置的登入 Email 紀錄"
    )
    if clear_button.count():
        clear_button.click()
        expect(
            page.get_by_role("button", name="清除這台裝置的登入 Email 紀錄")
        ).to_have_count(0, timeout=30_000)
        page.wait_for_timeout(500)
    _set_history(page, SAFE_HISTORY)
    print(f"{profile}: localStorage seeded", flush=True)
    page.wait_for_timeout(3_000)
    surface = _wait_for_login(page)
    surface.get_by_text("這台裝置曾使用的 Email", exact=True).wait_for(timeout=30_000)
    recent = surface.get_by_role("combobox", name="這台裝置曾使用的 Email")
    expect(recent).to_have_value(SAFE_HISTORY[0], timeout=30_000)
    print(f"{profile}: history visible", flush=True)
    page.reload(wait_until="domcontentloaded")
    surface = _wait_for_login(page)
    expect(
        surface.get_by_role("combobox", name="這台裝置曾使用的 Email")
    ).to_have_value(SAFE_HISTORY[0], timeout=30_000)
    print(f"{profile}: reload persistence visible", flush=True)
    if mobile:
        assert page.viewport_size and page.viewport_size["width"] <= 430


def verify_testing_allowlist_gate(page: Page, url: str) -> None:
    """Release gate: direct-code display is internal test accounts only.

    A non-allowlisted Email must never receive a displayed OTP and must never
    trigger the official /otp request from the testing button.
    """
    print("desktop: opening testing allowlist gate", flush=True)
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    surface = _wait_for_login(page)
    email_input = surface.get_by_label("Email", exact=True)
    email_input.fill("test-a@example.com")
    surface.get_by_role("button", name="顯示驗證碼（測試期間）").click()
    blocked = surface.get_by_text(
        "此 Email 不開放測試期間直接顯示驗證碼，請改用 Email 寄送驗證碼登入。",
        exact=True,
    )
    blocked.wait_for(timeout=30_000)
    expect(surface.get_by_text("您的登入驗證碼是", exact=False)).to_have_count(0)
    expect(surface.get_by_text("已寄出 Email", exact=False)).to_have_count(0)
    print("desktop: non-allowlisted direct code blocked", flush=True)


def request_real_otp(page: Page, url: str, email: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    surface = _wait_for_login(page)
    surface.get_by_text("改用 Email 寄送驗證碼登入（正式流程）", exact=True).click()
    email_input = surface.get_by_label("Email（正式 OTP 流程）", exact=True)
    email_input.fill(email)
    surface.get_by_role("button", name="寄送驗證碼").click()
    accepted = surface.get_by_text("驗證碼已寄出，請查看 Email。", exact=True)
    limited = surface.get_by_text("驗證碼剛剛已寄出，請稍候再試。", exact=True)
    accepted.or_(limited).wait_for(timeout=30_000)


def _controlled_email(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload if isinstance(payload, list) else payload.get("emails", [])
    for value in values:
        email = str(value).strip().lower()
        if "@" in email and email != "trial@example.com":
            return email
    raise ValueError("controlled Email file contains no usable address")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--request-otp-email-file", type=Path)
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("--url must be an HTTP(S) application URL")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        desktop = browser.new_context(viewport={"width": 1280, "height": 960})
        verify_history_ui(desktop.new_page(), args.url)
        desktop.close()
        testing = browser.new_context(viewport={"width": 1280, "height": 960})
        verify_testing_allowlist_gate(testing.new_page(), args.url)
        testing.close()
        mobile = browser.new_context(viewport={"width": 390, "height": 844})
        verify_history_ui(mobile.new_page(), args.url, mobile=True)
        mobile.close()
        if args.request_otp_email_file:
            otp_context = browser.new_context(viewport={"width": 1280, "height": 960})
            request_real_otp(
                otp_context.new_page(),
                args.url,
                _controlled_email(args.request_otp_email_file),
            )
            otp_context.close()
        browser.close()
    print("AUTH BROWSER E2E: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
