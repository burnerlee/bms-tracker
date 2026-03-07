"""BookMyShow crawler: search movie, resolve event ID, check availability for target date."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

BMS_BASE = "https://in.bookmyshow.com"
DEFAULT_TIMEOUT_MS = 30_000
RETRIES = 2
MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _target_date_to_day_and_month(target_date_yyyymmdd: str) -> tuple[int, str]:
    """Convert YYYYMMDD to (day_number, month_abbr) e.g. 20260319 -> (19, 'MAR')."""
    dt = datetime.strptime(target_date_yyyymmdd, "%Y%m%d")
    return dt.day, MONTH_ABBR[dt.month - 1]


@dataclass
class CrawlResult:
    available: bool
    showtimes: list[str]
    message: str
    movie_url: str | None = None


def _extract_event_id_from_href(href: str) -> str | None:
    """Extract event ID from BMS movie/buytickets URL."""
    # e.g. /bengaluru/movies/dhurandhar-the-revenge/ET00412345 or .../buytickets/ET00412345/
    match = re.search(r"/buytickets/([^/]+)/?", href, re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"/movies/[^/]+/([A-Z0-9]+)/?", href, re.I)
    if match:
        return match.group(1).strip()
    return None


def _extract_movie_slug_from_href(href: str, city: str) -> str | None:
    """Extract movie slug from BMS URL: /city/movies/movie-slug/..."""
    pattern = re.compile(
        rf"/{re.escape(city)}/movies/([^/]+)/?",
        re.I,
    )
    match = pattern.search(href)
    return match.group(1).strip() if match else None


def check_availability(
    city: str,
    movie_name: str,
    target_date_yyyymmdd: str,
    event_id: str | None = None,
    movie_slug: str | None = None,
) -> CrawlResult:
    """
    Check if tickets are available for the target date. If event_id (and
    movie_slug) are provided, opens the buytickets URL directly. Otherwise
    searches BookMyShow for the movie first.
    """
    if event_id and movie_slug:
        return _check_availability_direct(
            city=city,
            target_date_yyyymmdd=target_date_yyyymmdd,
            event_id=event_id,
            movie_slug=movie_slug,
        )

    last_error: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            return _check_availability_impl(
                city, movie_name, target_date_yyyymmdd
            )
        except Exception as e:
            last_error = e
            logger.warning("Attempt %s failed: %s", attempt + 1, e)
            if attempt == RETRIES:
                break
    return CrawlResult(
        available=False,
        showtimes=[],
        message=f"Crawler failed after {RETRIES + 1} attempts: {last_error!s}",
        movie_url=None,
    )


def _check_availability_direct(
    city: str,
    target_date_yyyymmdd: str,
    event_id: str,
    movie_slug: str,
) -> CrawlResult:
    """
    Open buytickets page, find the date tab for the target date in the date bar,
    and check if that tab is enabled (not greyed out/disabled). No clicking:
    enabled = tickets available, disabled = not available.
    """
    buytickets_url = (
        f"{BMS_BASE}/movies/{city}/{movie_slug}/buytickets/{event_id}/{target_date_yyyymmdd}"
    )
    logger.info("Checking availability (direct): %s", buytickets_url)

    day_num, month_abbr = _target_date_to_day_and_month(target_date_yyyymmdd)
    date_label = f"{day_num} {month_abbr}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
                ),
            )
            context.set_default_timeout(DEFAULT_TIMEOUT_MS)
            page = context.new_page()
            page.goto(buytickets_url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            date_tabs = _find_all_date_tabs(page, day_num, month_abbr, target_date_yyyymmdd)
            if not date_tabs:
                return CrawlResult(
                    available=False,
                    showtimes=[],
                    message=(
                        f"Could not find date tab for {date_label}. URL: {buytickets_url}"
                    ),
                    movie_url=buytickets_url,
                )

            disabled = all(_is_date_tab_disabled(page, tab) for tab in date_tabs)
            if disabled:
                return CrawlResult(
                    available=False,
                    showtimes=[],
                    message=(
                        f"Date {date_label} is disabled in the date bar (tickets not available). "
                        f"URL: {buytickets_url}"
                    ),
                    movie_url=buytickets_url,
                )

            return CrawlResult(
                available=True,
                showtimes=[],
                message=(
                    f"Date {date_label} is enabled in the date bar (tickets available). "
                    f"URL: {buytickets_url}"
                ),
                movie_url=buytickets_url,
            )
        except Exception as e:
            logger.exception("Crawler error (direct)")
            return CrawlResult(
                available=False,
                showtimes=[],
                message=f"Crawler error: {e!s}",
                movie_url=buytickets_url,
            )
        finally:
            browser.close()


def _find_date_tab(page: Any, day_num: int, month_abbr: str, target_date_yyyymmdd: str = ""):
    """Find the first date tab element for the given day and month."""
    tabs = _find_all_date_tabs(page, day_num, month_abbr, target_date_yyyymmdd)
    return tabs[0] if tabs else None


def _find_all_date_tabs(page: Any, day_num: int, month_abbr: str, target_date_yyyymmdd: str = ""):
    """
    Find all date tab elements that match the given day and month (e.g. 18 MAR).
    Returns a list of locators so we can check if any is enabled.
    """
    day_str = str(day_num)
    combined = page.locator(
        f'[data-date*="{day_str}"], [data-date*="{month_abbr}"], '
        f'button:has-text("{day_str}"):has-text("{month_abbr}"), '
        f'a:has-text("{day_str}"):has-text("{month_abbr}"), '
        f'li:has-text("{day_str}"):has-text("{month_abbr}"), '
        f'[class*="date"]:has-text("{day_str}"):has-text("{month_abbr}"), '
        f'div:has-text("{day_str}"):has-text("{month_abbr}")'
    )
    out = []
    try:
        n = combined.count()
        for i in range(min(n, 10)):
            loc = combined.nth(i)
            if loc.is_visible():
                out.append(loc)
    except Exception:
        pass
    return out


def _is_date_tab_disabled(page: Any, date_tab: Any) -> bool:
    """
    Return True if the date tab is disabled (tickets not available).
    Checks: disabled/aria-disabled, class, pointer-events, and grey text
    (disabled tabs have light grey text; enabled has red bg or dark/white text).
    """
    try:
        return date_tab.evaluate(
            """(el) => {
                if (!el) return true;
                const check = (e) => {
                    if (!e) return false;
                    if (e.getAttribute('disabled') !== null) return true;
                    if ((e.getAttribute('aria-disabled') || '').toLowerCase() === 'true') return true;
                    const c = (e.getAttribute('class') || '').toLowerCase();
                    if (/disabled|unavailable|not-available/.test(c)) return true;
                    const s = window.getComputedStyle(e);
                    if ((s.pointerEvents || 'auto').toLowerCase() === 'none') return true;
                    return false;
                };
                if (check(el)) return true;
                for (const child of el.querySelectorAll('*')) { if (check(child)) return true; }
                const parseRgb = (color) => {
                    const m = /rgb\\(?\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/.exec(color);
                    if (!m) return null;
                    return { r: parseInt(m[1],10), g: parseInt(m[2],10), b: parseInt(m[3],10) };
                };
                const isGrey = (rgb) => {
                    if (!rgb) return false;
                    const diff = Math.max(Math.abs(rgb.r-rgb.g), Math.abs(rgb.g-rgb.b), Math.abs(rgb.r-rgb.b));
                    return diff < 90 && rgb.r < 180 && rgb.g < 180 && rgb.b < 180;
                };
                const isWhiteOrLight = (rgb) => rgb && rgb.r > 200 && rgb.g > 200 && rgb.b > 200;
                const hasRedBg = (e) => {
                    const s = window.getComputedStyle(e);
                    const bg = s.backgroundColor;
                    const rgb = parseRgb(bg);
                    if (rgb && rgb.r > 100 && rgb.r > rgb.g && rgb.r > rgb.b && rgb.g < 150 && rgb.b < 150) return true;
                    const img = s.backgroundImage;
                    if (img && img !== 'none' && (img.includes('rgb') || img.includes('red'))) return true;
                    return false;
                };
                for (let n = el; n && n !== document.body; n = n.parentElement) {
                    if (hasRedBg(n)) return false;
                }
                const nodesToCheck = [el, ...el.querySelectorAll('span, div')];
                for (const node of nodesToCheck) {
                    const color = window.getComputedStyle(node).color;
                    const rgb = parseRgb(color);
                    if (isWhiteOrLight(rgb)) return false;
                    if (isGrey(rgb)) return true;
                }
                return false;
            }"""
        )
    except Exception:
        return True


def _is_real_showtime_book_button(text: str) -> bool:
    """
    True if text looks like a showtime 'Book' action.
    Excludes known false positives: RESEND BOOKING CONFIRMATION, BookAChange.
    Allows: Book, BOOK, "10:30 AM  Book", and labels with whole-word 'book'.
    """
    t = (text or "").strip()
    if not t:
        return False
    t_lower = t.lower()
    if "resend" in t_lower or "confirmation" in t_lower or "bookachange" in t_lower:
        return False
    if not re.search(r"\bbook\b", t_lower):
        return False
    if len(t) > 50:
        return False
    return True


def _parse_availability_from_page(
    page: Any, buytickets_url: str
) -> tuple[list[str], bool]:
    """
    Parse showtimes and availability from the current page.
    Only counts real showtime 'Book' buttons (exact/short text), not phrases
    like 'RESEND BOOKING CONFIRMATION' or 'BookAChange'.
    """
    showtimes: list[str] = []

    def add_book_candidates(locator: Any, limit: int = 50) -> None:
        try:
            for i in range(min(locator.count(), limit)):
                el = locator.nth(i)
                if el.is_visible():
                    text = (el.inner_text() or "").strip()
                    if _is_real_showtime_book_button(text):
                        showtimes.append(text)
        except Exception:
            pass

    add_book_candidates(
        page.locator(
            'button:has-text("Book"), a:has-text("Book"), '
            '[data-action="book"], [class*="book"]'
        )
    )
    add_book_candidates(page.get_by_role("button", name=re.compile(r"^\s*book\s*$", re.I)))
    add_book_candidates(page.get_by_role("link", name=re.compile(r"^\s*book\s*$", re.I)))

    time_pattern = page.locator(
        '[class*="showtime"], [class*="time"], '
        'span:has-text(":"), [data-showtime]'
    )
    try:
        for i in range(min(time_pattern.count(), 50)):
            t = time_pattern.nth(i).inner_text().strip()
            if re.match(r"\d{1,2}\s*:\s*\d{2}", t) or re.match(r"\d{1,2}:\d{2}", t):
                if len(t) <= 12:
                    showtimes.append(t)
    except Exception:
        pass

    body = page.locator("body").inner_text()
    if not showtimes and re.search(r"\d{1,2}\s*:\s*\d{2}\s*(?:AM|PM|am|pm)", body):
        for m in re.finditer(r"(\d{1,2}\s*:\s*\d{2}\s*(?:AM|PM|am|pm)?)", body):
            t = m.group(1).strip()
            if len(t) <= 12:
                showtimes.append(t)
                if len(showtimes) >= 20:
                    break
    available = len(showtimes) > 0
    return showtimes, available


def _check_availability_impl(
    city: str,
    movie_name: str,
    target_date_yyyymmdd: str,
) -> CrawlResult:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
                ),
            )
            context.set_default_timeout(DEFAULT_TIMEOUT_MS)
            page = context.new_page()

            # 1) Navigate to city movies page
            movies_url = f"{BMS_BASE}/{city}/movies"
            logger.info("Navigating to %s", movies_url)
            page.goto(movies_url, wait_until="domcontentloaded")

            # 2) Find and use search
            search_input = page.locator(
                'input[placeholder*="Search"], input[type="search"], '
                'input[name="keyword"], [data-placeholder*="earch"]'
            ).first
            try:
                search_input.wait_for(state="visible", timeout=10_000)
            except PlaywrightTimeout:
                return CrawlResult(
                    available=False,
                    showtimes=[],
                    message="Movie not found: could not find search box on BookMyShow",
                    movie_url=None,
                )
            search_input.fill(movie_name)
            page.wait_for_timeout(1500)

            # 3) Wait for search results and get first movie link
            # Results may appear in a dropdown or new section
            movie_link = page.locator(
                'a[href*="/movies/"][href*="' + city + '"]'
            ).first
            try:
                movie_link.wait_for(state="visible", timeout=10_000)
            except PlaywrightTimeout:
                return CrawlResult(
                    available=False,
                    showtimes=[],
                    message=f"Movie not found: no results for '{movie_name}'",
                    movie_url=None,
                )

            href = movie_link.get_attribute("href") or ""
            if not href.startswith("http"):
                href = BMS_BASE + href if href.startswith("/") else f"{BMS_BASE}/{city}/movies/{href}"

            event_id = _extract_event_id_from_href(href)
            movie_slug = _extract_movie_slug_from_href(href, city)

            if not event_id or not movie_slug:
                # Get event ID and slug by following the movie link
                movie_link.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(2000)
                current_url = page.url
                event_id = event_id or _extract_event_id_from_href(current_url)
                if not event_id:
                    return CrawlResult(
                        available=False,
                        showtimes=[],
                        message=f"Movie found but could not resolve event ID: {current_url}",
                        movie_url=current_url,
                    )
                match = re.search(r"/movies/[^/]+/([^/]+)/?", current_url)
                movie_slug = movie_slug or (match.group(1) if match else "movie")

            # 4) Open buytickets page for target date
            buytickets_url = f"{BMS_BASE}/movies/{city}/{movie_slug}/buytickets/{event_id}/{target_date_yyyymmdd}"
            logger.info("Checking availability: %s", buytickets_url)
            page.goto(buytickets_url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # 5) Parse showtimes / Book buttons
            showtimes, available = _parse_availability_from_page(page, buytickets_url)
            showtimes = list(dict.fromkeys(showtimes))[:15]
            if available:
                message = (
                    f"Tickets available for {target_date_yyyymmdd}. "
                    f"Showtimes or book options: {showtimes or 'see page'}. URL: {buytickets_url}"
                )
            else:
                message = (
                    f"Tickets not yet available for {target_date_yyyymmdd}. "
                    f"URL: {buytickets_url}"
                )

            return CrawlResult(
                available=available,
                showtimes=showtimes,
                message=message,
                movie_url=buytickets_url,
            )

        except Exception as e:
            logger.exception("Crawler error")
            return CrawlResult(
                available=False,
                showtimes=[],
                message=f"Crawler error: {e!s}",
                movie_url=None,
            )
        finally:
            browser.close()


def run_check(config: dict[str, Any]) -> CrawlResult:
    """Run availability check using config dict from load_config()."""
    return check_availability(
        city=config["bms_city"],
        movie_name=config["movie_name"],
        target_date_yyyymmdd=config["target_date_yyyymmdd"],
        event_id=config.get("bms_event_id"),
        movie_slug=config.get("bms_movie_slug"),
    )
