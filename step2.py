"""
Step 2: Deep Browser Evidence Collection (Playwright)

This module uses a headless Chromium browser via Playwright to:
  - Bypass Cloudflare JS challenge
  - Crawl episode/watch-page URLs from the homepage
  - Intercept network requests for .m3u8 / .mp4 streams
  - Extract embedded iframe player sources
  - Block popup/ad tabs automatically
  - Scan footer for legal notices
  - Capture screenshots as evidence

Usage:
    from step2 import run_step2
    evidence = run_step2("animevietsub.by", "https://animevietsub.by/")
"""

import os
import re
import json
import random
import asyncio
import logging
from datetime import datetime
from urllib.parse import urlparse, urljoin

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

# Stream URL patterns to intercept
STREAM_EXTENSIONS = [".m3u8", ".mp4", ".ts", ".mpd"]

CDN_KEYWORDS = [
    "pstream", "gdrive", "ok.ru", "fbcdn", "fembed",
    "vidstream", "mp4upload", "streamtape", "doodstream",
    "filemoon", "voesx", "mixdrop", "streamsb",
    "playlist.m3u8", "manifest.mpd", "index.m3u8",
    "master.m3u8", "chunklist", "segment",
]

# ── Banner image collection config ──
# CSS class/id keywords hinting at ad/banner containers
BANNER_CLASS_KEYWORDS = [
    "banner", "ads", "ad-", "-ad", "advert", "sponsor",
    "promo", "sidebar", "widget", "popup-ad", "quangcao",
    "affiliate", "partner",
]

# URL path/host keywords that suggest an ad image network
AD_IMAGE_URL_KEYWORDS = [
    "banner", "ads", "adserver", "doubleclick", "googlesyndication",
    "adnxs", "adtech", "adsystem", "affiliate", "promo",
    "sponsor", "partner", "track", "click",
]

# Image file extensions recognised as banner assets
BANNER_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")

# Minimum pixel dimension to consider an image a banner
# (filters out tiny icons/avatars)
MIN_BANNER_WIDTH  = 80   # px
MIN_BANNER_HEIGHT = 30   # px

# Directory for downloaded banner images
BANNERS_SUBDIR = "banners"

# URL patterns that indicate an ACTUAL episode watch page
# (not just anime info pages)
EPISODE_WATCH_PATTERNS = [
    # --- Pirate site patterns ---
    r"/tap-\d+",
    r"tap-\d+.*\.html",
    r"/episode[/-]\d+",
    r"/watch/.+/\d+",
    r"/xem-phim/.+/tap",
    # --- Legitimate site patterns ---
    r"/vod/.+",              # VTVGo VOD content
    r"/kenh-truyen-hinh/.+", # VTVGo live TV channels
    r"/chuong-trinh/.+",     # Program pages
    r"/live/.+",             # General live streams
    r"/video/.+",            # Generic video paths
    r"/truyen-hinh/.+",      # TV channels
    r"/phim-bo/.+",          # TV series (official)
    r"/phim-le/.+",          # Movies (official)
]

# Broader patterns for content pages (info + episodes)
EPISODE_URL_PATTERNS = [
    # --- Pirate site patterns ---
    r"/xem-phim/",
    r"/tap-",
    r"/episode/",
    r"/watch/",
    r"/phim/",
    r"/xem/",
    # --- Legitimate site patterns ---
    r"/vod/",
    r"/kenh-truyen-hinh/",
    r"/chuong-trinh/",
    r"/live/",
    r"/video/",
    r"/truyen-hinh/",
]

# Legal notice keywords (Vietnamese)
LEGAL_KEYWORDS = [
    # --- Core legal identifiers ---
    "giấy phép",
    "giấy phép số",
    "gp số",
    "cơ quan chủ quản",
    "mã số thuế",
    "mst:",
    "đkkd",
    "giấy chứng nhận",
    "cục phát thanh",
    "bộ thông tin",
    "số giấy phép",
    "chịu trách nhiệm nội dung",
    "trụ sở",
    # --- Official broadcaster keywords ---
    "đài truyền hình",
    "đơn vị quản lý",
    "tổng biên tập",
    "giám đốc",
    "bản quyền thuộc",
    "© 20",
    "sở hữu bởi",
    "đăng ký kinh doanh",
]

# Timeouts (milliseconds)
CLOUDFLARE_WAIT_MS = 15000
PAGE_LOAD_TIMEOUT_MS = 60000
NETWORK_SETTLE_MS = 8000

# How many episodes to sample for evidence
MAX_EPISODES_TO_CHECK = 3

# Screenshots directory
SCREENSHOTS_DIR = os.path.join("logs", "screenshots")

# Logging
logger = logging.getLogger("step2")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
)

# ── Extra imports for banner downloader ──
import hashlib
import urllib.request
from urllib.error import URLError


from bs4 import BeautifulSoup

def get_clean_text_from_html(html_content: str) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe", "svg", "aside", "form", "button"]):
        tag.decompose()
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote", "pre", "article", "section", "br"]):
        tag.insert_before("\n")
    text = soup.get_text(separator="", strip=False)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if re.sub(r"[ \t]+", " ", line).strip()]
    return "\n".join(lines).strip()


# ──────────────────────────────────────────────
# STEALTH BROWSER LAUNCH
# ──────────────────────────────────────────────

async def launch_stealth_browser(pw):
    """
    Launch a Chromium browser with stealth-like settings
    to reduce bot-detection fingerprinting.
    playwright-stealth v2.x automatically patches all pages.
    """

    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--window-size=1920,1080",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh",
        java_script_enabled=True,
        ignore_https_errors=True,
    )

    # ── Anti-DevTools detection scripts ──
    # Many pirate players detect DevTools/headless via:
    #   1. window.outerHeight - window.innerHeight > threshold
    #   2. debugger statement timing
    #   3. console.log with getter (fires when DevTools is open)
    #   4. Firebug detection
    await context.add_init_script("""
        // 1. Spoof outerHeight/outerWidth to match inner dimensions
        //    This defeats the common devtools-size-check
        Object.defineProperty(window, 'outerHeight', {
            get: () => window.innerHeight
        });
        Object.defineProperty(window, 'outerWidth', {
            get: () => window.innerWidth
        });

        // 2. Neutralize debugger-based detection
        //    Override Function.prototype.constructor to neuter
        //    `new Function('debugger')` and eval('debugger')
        const _origFunction = Function.prototype.constructor;
        Function.prototype.constructor = function() {
            const args = Array.from(arguments);
            const body = args[args.length - 1];
            if (typeof body === 'string' &&
                body.includes('debugger')) {
                // Return no-op
                return function() {};
            }
            return _origFunction.apply(this, args);
        };

        // 3. Override console detection methods
        //    Some sites use console.log with a getter on an
        //    object that only fires when DevTools is open
        const _consoleLog = console.log;
        const _consoleDir = console.dir;
        const _consoleTable = console.table;
        // Wrap them to swallow any detection traps
        console.log = function() { return _consoleLog.apply(console, arguments); };
        console.dir = function() { return _consoleDir.apply(console, arguments); };
        console.table = function() { return _consoleTable.apply(console, arguments); };

        // 4. Prevent Firebug detection
        window.__firebug = undefined;
        window.Firebug = undefined;

        // 5. Override chrome.runtime detection
        //    (Already handled by playwright-stealth but reinforce it)
        if (!window.chrome) window.chrome = {};
        if (!window.chrome.runtime) window.chrome.runtime = {};

        // 6. Block devtools-warning iframe from loading
        const _createElement = document.createElement.bind(document);
        document.createElement = function(tag) {
            const el = _createElement(tag);
            if (tag.toLowerCase() === 'iframe') {
                const _setSrc = Object.getOwnPropertyDescriptor(
                    HTMLIFrameElement.prototype, 'src'
                );
                if (_setSrc && _setSrc.set) {
                    Object.defineProperty(el, 'src', {
                        set: function(val) {
                            if (typeof val === 'string' &&
                                val.includes('devtools-warning')) {
                                // Block this iframe from loading
                                return;
                            }
                            _setSrc.set.call(this, val);
                        },
                        get: function() {
                            return _setSrc.get.call(this);
                        }
                    });
                }
            }
            return el;
        };
    """)

    page = await context.new_page()

    return browser, context, page


# ──────────────────────────────────────────────
# CLOUDFLARE BYPASS
# ──────────────────────────────────────────────

async def bypass_cloudflare(page, url, max_retries=2):
    """
    Navigate to a URL and wait for Cloudflare JS challenge
    to resolve. Returns True if the page loaded successfully.
    """

    for attempt in range(1, max_retries + 1):

        logger.info(
            f"[Cloudflare] Attempt {attempt}/{max_retries} → {url}"
        )

        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PAGE_LOAD_TIMEOUT_MS,
            )
        except Exception as e:
            logger.warning(f"[Cloudflare] Navigation error: {e}")
            if attempt == max_retries:
                return False
            continue

        # Wait for Cloudflare JS challenge to complete
        logger.info(
            f"[Cloudflare] Waiting {CLOUDFLARE_WAIT_MS}ms for JS challenge..."
        )
        await page.wait_for_timeout(CLOUDFLARE_WAIT_MS)

        # Check if page loaded successfully (not stuck on challenge)
        title = await page.title()
        body_text = await page.evaluate(
            "document.body ? document.body.innerText.substring(0, 500) : ''"
        )

        cf_blocked_signals = [
            "just a moment",
            "checking your browser",
            "ray id",
            "cloudflare",
            "attention required",
            "please wait",
        ]

        is_blocked = any(
            sig in (title + " " + body_text).lower()
            for sig in cf_blocked_signals
        )

        if not is_blocked:
            logger.info("[Cloudflare] ✓ Bypass successful!")
            return True

        logger.warning(
            f"[Cloudflare] Still blocked (title='{title}'). "
            f"Retrying..."
        )
        await page.wait_for_timeout(5000)

    logger.error("[Cloudflare] ✗ Failed to bypass after all retries.")
    return False


# ──────────────────────────────────────────────
# EPISODE URL CRAWLING
# ──────────────────────────────────────────────

async def crawl_episode_urls(page, base_domain):
    """
    Extract episode/watch-page URLs from the current page.
    Prioritizes actual watch URLs (with tap-XX, .html) over
    anime info pages (which don't have a video player).

    For SPAs / lazy-loaded pages: scrolls down 3 times before
    extracting links to trigger content card rendering.

    Returns deduplicated list of absolute URLs.
    """

    # ── Pre-scroll: trigger lazy-loaded content cards ──
    # SPAs like VTVGo only render video links after scroll
    for scroll_round in range(1, 4):
        await page.evaluate("""
            () => window.scrollBy(0, window.innerHeight * 1.5)
        """)
        logger.info(
            f"[Crawl] Content scroll round {scroll_round}/3"
        )
        await page.wait_for_timeout(1500)

    # Scroll back to top so we capture ALL links
    await page.evaluate(
        "window.scrollTo(0, 0)"
    )
    await page.wait_for_timeout(500)

    # ── Extract all <a href> links ──
    all_hrefs = await page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href]');
            return Array.from(links).map(a => a.href);
        }
    """)

    # Pattern for actual watch pages (high priority)
    watch_pattern = re.compile(
        "|".join(EPISODE_WATCH_PATTERNS),
        re.IGNORECASE,
    )

    # Broader pattern (lower priority, info pages)
    broad_pattern = re.compile(
        "|".join(EPISODE_URL_PATTERNS),
        re.IGNORECASE,
    )

    watch_urls = []     # Actual episode pages with player
    info_urls = []      # Anime info pages (no player)
    seen = set()

    for href in all_hrefs:

        if not href or href in seen:
            continue

        # Strip fragment (#cmt-XXXX etc.)
        clean_href = href.split('#')[0]
        if clean_href in seen:
            continue

        # Must belong to the same domain
        try:
            parsed = urlparse(clean_href)
            if parsed.netloc and base_domain not in parsed.netloc:
                continue
        except Exception:
            continue

        # Classify: watch page or info page?
        if watch_pattern.search(clean_href):
            seen.add(clean_href)
            watch_urls.append(clean_href)
        elif broad_pattern.search(clean_href):
            seen.add(clean_href)
            info_urls.append(clean_href)

    logger.info(
        f"[Crawl] Found {len(watch_urls)} watch URLs + "
        f"{len(info_urls)} info URLs on page."
    )

    # Return watch URLs first (they have the video player)
    # Fall back to info URLs if no watch URLs found
    if watch_urls:
        return watch_urls
    else:
        logger.warning(
            "[Crawl] No direct watch URLs found. "
            "Will try navigating into info pages to find episodes."
        )
        return info_urls


# ──────────────────────────────────────────────
# NETWORK INTERCEPTOR (Stream Catcher)
# ──────────────────────────────────────────────

def create_network_interceptor(evidence_collector):
    """
    Returns a response handler that captures:
    - Stream URLs (.m3u8, .mp4, CDN patterns)
    - Ad/banner image URLs (Case 7 of banner collection)
    """

    async def handle_response(response):

        url = response.url
        url_lower = url.lower()

        # ── Stream detection ──
        is_stream = any(
            ext in url_lower for ext in STREAM_EXTENSIONS
        )
        is_cdn = any(
            kw in url_lower for kw in CDN_KEYWORDS
        )

        if is_stream or is_cdn:

            content_type = ""
            try:
                headers = response.headers
                content_type = headers.get("content-type", "")
            except Exception:
                pass

            stream_entry = {
                "url": url,
                "content_type": content_type,
                "status": response.status,
                "matched_by": (
                    "stream_extension" if is_stream
                    else "cdn_keyword"
                ),
            }

            existing_urls = [
                s["url"]
                for s in evidence_collector["streams"]
            ]

            if url not in existing_urls:
                evidence_collector["streams"].append(stream_entry)
                logger.info(
                    f"[Stream] ★ Captured: {url[:120]}..."
                )

        # ── Case 7: Ad/banner image interception ──
        # Catch image responses whose URL path suggests an ad network
        # so we can later download them even if they weren't in the DOM.
        try:
            content_type = response.headers.get("content-type", "")
        except Exception:
            content_type = ""

        is_image_content = content_type.startswith("image/")
        has_ad_url = any(kw in url_lower for kw in AD_IMAGE_URL_KEYWORDS)
        has_image_ext = any(url_lower.split("?")[0].endswith(ext) for ext in BANNER_IMAGE_EXTENSIONS)

        if (is_image_content or has_image_ext) and has_ad_url:
            hits = evidence_collector.get("banner_network_hits", [])
            if url not in [h["url"] for h in hits]:
                hits.append({"url": url, "content_type": content_type})
                evidence_collector["banner_network_hits"] = hits
                logger.info(f"[BannerNet] ★ Ad image intercepted: {url[:120]}")

    return handle_response


# ──────────────────────────────────────────────
# POPUP BLOCKER
# ──────────────────────────────────────────────

def create_popup_blocker(evidence_collector):
    """
    Returns a handler that immediately closes any new tab/popup
    opened by the page (e.g. gambling ads).
    """

    async def handle_popup(new_page):

        popup_url = new_page.url

        logger.info(f"[Popup] Blocked & closed: {popup_url[:100]}")

        evidence_collector["popup_blocked_count"] += 1
        evidence_collector["popup_urls"].append(popup_url)

        try:
            await new_page.close()
        except Exception:
            pass

    return handle_popup


# ──────────────────────────────────────────────
# IFRAME EXTRACTION
# ──────────────────────────────────────────────

async def extract_iframes(page, base_domain):
    """
    Extract all iframe sources from the page:
    1. From Playwright's frame tree (page.frames)
    2. From DOM <iframe> elements' src attributes

    Returns list of dicts with iframe info.
    """

    iframes_found = []
    seen_srcs = set()

    # Method 1: Playwright frame tree
    for frame in page.frames:

        frame_url = frame.url

        if (
            frame_url
            and frame_url != "about:blank"
            and frame_url not in seen_srcs
        ):
            seen_srcs.add(frame_url)
            iframes_found.append({
                "iframe_src": frame_url,
                "source": "frame_tree",
                "is_external": (
                    base_domain not in frame_url
                    if base_domain else False
                ),
            })

    # Method 2: DOM query
    try:
        dom_iframes = await page.evaluate("""
            () => {
                const iframes = document.querySelectorAll('iframe');
                return Array.from(iframes).map(iframe => ({
                    src: iframe.src || '',
                    dataSrc: iframe.getAttribute('data-src') || '',
                    width: iframe.width || '',
                    height: iframe.height || '',
                }));
            }
        """)

        for iframe_info in dom_iframes:

            src = iframe_info.get("src") or iframe_info.get("dataSrc")

            if src and src != "about:blank" and src not in seen_srcs:

                seen_srcs.add(src)
                iframes_found.append({
                    "iframe_src": src,
                    "source": "dom_query",
                    "is_external": (
                        base_domain not in src
                        if base_domain else False
                    ),
                    "dimensions": (
                        f"{iframe_info.get('width', '?')}"
                        f"x{iframe_info.get('height', '?')}"
                    ),
                })

    except Exception as e:
        logger.warning(f"[iFrame] DOM query error: {e}")

    logger.info(f"[iFrame] Found {len(iframes_found)} iframe(s).")

    return iframes_found


# ──────────────────────────────────────────────
# IFRAME DEEP PIERCING (Stage 2B)
# ──────────────────────────────────────────────

async def pierce_iframes(page, evidence_collector, base_domain=""):
    """
    Stage 2B: For each iframe detected, switch context into it
    and listen for additional network requests that reveal
    the actual stream source hidden inside the player.

    Args:
        base_domain: Skip iframes belonging to the target domain
                     itself (only pierce external/player iframes).
    """

    for frame in page.frames:

        frame_url = frame.url

        if (
            not frame_url
            or frame_url == "about:blank"
            or (base_domain and base_domain in frame_url)
        ):
            continue

        logger.info(
            f"[iFrame Pierce] Entering frame: {frame_url[:100]}"
        )

        try:
            # Try to find video elements inside the iframe
            video_srcs = await frame.evaluate("""
                () => {
                    const videos = document.querySelectorAll(
                        'video, video source'
                    );
                    return Array.from(videos).map(v =>
                        v.src || v.getAttribute('src') || ''
                    ).filter(s => s && s !== '');
                }
            """)

            for src in video_srcs:

                stream_entry = {
                    "url": src,
                    "content_type": "video (from iframe)",
                    "status": 200,
                    "matched_by": "iframe_video_element",
                    "parent_iframe": frame_url,
                }

                existing = [
                    s["url"]
                    for s in evidence_collector["streams"]
                ]

                if src not in existing:
                    evidence_collector["streams"].append(stream_entry)
                    logger.info(
                        f"[iFrame Pierce] ★ Found video src: "
                        f"{src[:120]}"
                    )

        except Exception as e:
            logger.warning(
                f"[iFrame Pierce] Could not inspect frame: {e}"
            )


# ──────────────────────────────────────────────
# LEGAL IDENTITY SCANNER (formerly "Footer Scanner")
# Enhanced: meta tag scan + infinite scroll aware
# ──────────────────────────────────────────────

async def _scan_meta_tags(page):
    """
    Strategy 0: Scan <head> meta tags, <title>, Open Graph,
    and JSON-LD structured data for legal/copyright signals.
    This runs BEFORE any scrolling and works on every site
    type including infinite-scroll SPAs.
    """

    try:
        meta_result = await page.evaluate("""
            () => {
                const result = {
                    title: document.title || '',
                    meta_copyright: '',
                    meta_author: '',
                    og_site_name: '',
                    json_ld_org: '',
                    all_meta_text: '',
                };

                // Collect all <meta> tags
                const metas = document.querySelectorAll('meta');
                const metaParts = [];
                metas.forEach(m => {
                    const name = (m.name || m.getAttribute('property') || '').toLowerCase();
                    const content = m.content || '';
                    if (content) {
                        metaParts.push(content);
                    }
                    // Specific extractions
                    if (name === 'copyright' || name === 'rights') {
                        result.meta_copyright = content;
                    }
                    if (name === 'author' || name === 'publisher') {
                        result.meta_author = content;
                    }
                    if (name === 'og:site_name') {
                        result.og_site_name = content;
                    }
                });
                result.all_meta_text = metaParts.join(' ');

                // JSON-LD structured data
                const ldScripts = document.querySelectorAll(
                    'script[type="application/ld+json"]'
                );
                const ldParts = [];
                ldScripts.forEach(s => {
                    try {
                        const data = JSON.parse(s.textContent);
                        if (data['@type'] === 'Organization'
                            || data['@type'] === 'WebSite'
                            || data['@type'] === 'BroadcastService') {
                            ldParts.push(JSON.stringify(data));
                        }
                        // Also check for nested publisher
                        if (data.publisher && data.publisher.name) {
                            ldParts.push(data.publisher.name);
                        }
                    } catch(e) {}
                });
                result.json_ld_org = ldParts.join(' ');

                return JSON.stringify(result);
            }
        """)

        return json.loads(meta_result)

    except Exception as e:
        logger.warning(f"[Meta Scan] Error: {e}")
        return {}


async def _detect_infinite_scroll(page):
    """
    Detect if the page uses infinite scroll by measuring
    body height before and after a scroll action.
    Returns True if page height grew (= infinite scroll).
    """

    try:
        height_before = await page.evaluate(
            "document.body.scrollHeight"
        )
        await page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )
        await page.wait_for_timeout(2000)
        height_after = await page.evaluate(
            "document.body.scrollHeight"
        )

        is_infinite = height_after > height_before + 200
        logger.info(
            f"[Footer] Infinite scroll detection: "
            f"before={height_before}px, after={height_after}px → "
            f"{'INFINITE SCROLL' if is_infinite else 'STATIC'}"
        )
        return is_infinite

    except Exception as e:
        logger.warning(f"[Footer] Infinite scroll check error: {e}")
        return False


async def scan_footer(page):
    """
    Multi-layered legal identity scan:

    Layer 0: Meta tag scan (works on ALL sites, no scroll needed)
    Layer 1: Infinite scroll detection
    Layer 2: Deep-scroll + DOM extraction (4 strategies)

    For infinite-scroll sites (no footer exists), Layer 0
    provides the legal identity signals instead.
    """

    # ══════════════════════════════════════════
    # Layer 0: Meta Tag Scan (ALWAYS runs first)
    # ══════════════════════════════════════════

    logger.info("[Footer] Layer 0: Scanning meta tags...")
    meta_info = await _scan_meta_tags(page)

    meta_text = " ".join([
        meta_info.get("title", ""),
        meta_info.get("meta_copyright", ""),
        meta_info.get("meta_author", ""),
        meta_info.get("og_site_name", ""),
        meta_info.get("json_ld_org", ""),
        meta_info.get("all_meta_text", ""),
    ]).lower()

    meta_has_legal = any(
        kw in meta_text for kw in LEGAL_KEYWORDS
    )
    meta_has_copyright = bool(
        re.search(r"©\s*20\d{2}", meta_text)
    ) or bool(meta_info.get("meta_copyright"))
    meta_has_org = bool(
        meta_info.get("og_site_name")
        or meta_info.get("json_ld_org")
    )

    logger.info(
        f"[Footer] Meta scan: legal={meta_has_legal}, "
        f"copyright={meta_has_copyright}, org={meta_has_org}"
    )

    # ══════════════════════════════════════════
    # Layer 1: Infinite Scroll Detection
    # ══════════════════════════════════════════

    logger.info("[Footer] Layer 1: Checking for infinite scroll...")
    is_infinite_scroll = await _detect_infinite_scroll(page)

    # ══════════════════════════════════════════
    # Layer 2: DOM-based footer extraction
    # (scroll + 4 strategies)
    # ══════════════════════════════════════════

    logger.info("[Footer] Layer 2: DOM footer extraction...")

    # Deep scroll (2 more rounds — _detect_infinite_scroll
    # already did 1 scroll)
    for scroll_round in range(1, 3):
        await page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )
        logger.info(
            f"[Footer] Scroll round {scroll_round}/2"
        )
        await page.wait_for_timeout(2000)

    # ── Multi-strategy footer text extraction ──
    footer_text = ""
    extraction_method = "none"

    try:
        footer_text = await page.evaluate("""
            () => {
                // Strategy 1: Semantic <footer> tag
                const footer = document.querySelector('footer');
                if (footer && footer.innerText.trim().length > 20) {
                    return JSON.stringify({
                        text: footer.innerText.trim(),
                        method: 'semantic_footer'
                    });
                }

                // Strategy 2: Common footer CSS selectors
                const footerSelectors = [
                    '.footer',
                    '#footer',
                    '[class*="footer"]',
                    '[role="contentinfo"]',
                    '.site-footer',
                    '.page-footer',
                    '#site-footer',
                ];
                for (const sel of footerSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.trim().length > 20) {
                        return JSON.stringify({
                            text: el.innerText.trim(),
                            method: 'css_selector: ' + sel
                        });
                    }
                }

                // Strategy 3: Keyword-targeted element search
                const legalKeywords = [
                    'giấy phép', 'mã số thuế', 'mst:',
                    'cơ quan chủ quản', 'bộ thông tin',
                    'cục phát thanh', 'chịu trách nhiệm',
                    'đài truyền hình', 'tổng biên tập',
                    'bản quyền thuộc', '© 20',
                    'đăng ký kinh doanh', 'giám đốc',
                ];
                const candidates = document.querySelectorAll(
                    'div, p, span, section, aside'
                );
                for (const el of candidates) {
                    const txt = (el.innerText || '').toLowerCase();
                    if (txt.length > 30 && txt.length < 2000) {
                        const matched = legalKeywords.some(
                            kw => txt.includes(kw)
                        );
                        if (matched) {
                            return JSON.stringify({
                                text: el.innerText.trim(),
                                method: 'keyword_targeted'
                            });
                        }
                    }
                }

                // Strategy 4 (fallback): bottom 20% of body text
                const body = document.body.innerText || '';
                const lines = body.split('\n');
                const cutoff = Math.max(0,
                    Math.floor(lines.length * 0.8)
                );
                return JSON.stringify({
                    text: lines.slice(cutoff).join('\n').trim(),
                    method: 'body_bottom_20pct'
                });
            }
        """)

        # Parse the JSON result from JS
        try:
            parsed = json.loads(footer_text)
            footer_text = parsed.get("text", "")
            extraction_method = parsed.get("method", "unknown")
        except (json.JSONDecodeError, TypeError):
            extraction_method = "raw_fallback"

    except Exception as e:
        logger.warning(f"[Footer] DOM extraction error: {e}")

    logger.info(
        f"[Footer] DOM extraction method: {extraction_method}"
    )

    # ══════════════════════════════════════════
    # Combine signals from Meta (Layer 0) + DOM (Layer 2)
    # ══════════════════════════════════════════

    # Merge footer_text with meta_text for keyword scanning
    combined_text = (footer_text + " " + meta_text).lower()

    legal_notice_found = any(
        kw in combined_text for kw in LEGAL_KEYWORDS
    )

    tax_code_found = bool(
        re.search(
            r"(mã số thuế|mst)[:\s]*\d{10,13}",
            combined_text,
        )
    )

    authority_found = any(
        kw in combined_text
        for kw in [
            "cơ quan chủ quản",
            "bộ thông tin",
            "cục phát thanh",
            "sở thông tin",
            "đài truyền hình",
            "tổng biên tập",
        ]
    )

    # Copyright from footer text OR meta tags
    copyright_found = bool(
        re.search(r"©\s*20\d{2}", combined_text)
    ) or meta_has_copyright

    # Structured data signals (JSON-LD, OG)
    has_structured_identity = meta_has_org

    # Check for suspicious ad-contact-only footer
    has_telegram = "telegram" in combined_text
    has_ad_contact = any(
        kw in combined_text
        for kw in [
            "liên hệ quảng cáo",
            "liên hệ qc",
            "contact",
            "quảng cáo",
        ]
    )

    # ── Final verdict ──
    # A page is NOT anonymous if ANY of these signals fire
    footer_anonymous = (
        not legal_notice_found
        and not tax_code_found
        and not authority_found
        and not copyright_found
        and not has_structured_identity
    )

    # Build snippet for output
    if footer_text:
        snippet = footer_text[:500]
    elif meta_text.strip():
        snippet = f"[META] {meta_text[:500]}"
    else:
        snippet = ""

    result = {
        "has_legal_footer": not footer_anonymous,
        "legal_notice_found": legal_notice_found,
        "tax_code_found": tax_code_found,
        "authority_found": authority_found,
        "copyright_found": copyright_found,
        "has_structured_identity": has_structured_identity,
        "is_infinite_scroll": is_infinite_scroll,
        "has_telegram_contact": has_telegram,
        "has_ad_contact_only": (
            has_ad_contact and not legal_notice_found
        ),
        "FOOTER_ANONYMOUS": footer_anonymous,
        "extraction_method": extraction_method,
        "meta_info": {
            "title": meta_info.get("title", ""),
            "og_site_name": meta_info.get("og_site_name", ""),
            "meta_copyright": meta_info.get("meta_copyright", ""),
            "meta_author": meta_info.get("meta_author", ""),
            "has_json_ld": bool(meta_info.get("json_ld_org")),
        },
        "footer_text_snippet": snippet,
    }

    logger.info(
        f"[Footer] FOOTER_ANONYMOUS = {footer_anonymous} "
        f"(infinite_scroll={is_infinite_scroll})"
    )

    return result


# ──────────────────────────────────────────────
# BANNER IMAGE COLLECTION (All 7 Cases)
# ──────────────────────────────────────────────

async def _trigger_lazy_load(page):
    """
    Scroll the page slowly to trigger lazy-loaded images
    (IntersectionObserver / data-src swap patterns).
    Waits 800ms between each step to allow JS to fire.
    """
    try:
        total_height = await page.evaluate("document.body.scrollHeight")
        step = max(300, total_height // 6)
        current = 0
        while current < total_height:
            await page.evaluate(f"window.scrollTo(0, {current})")
            await page.wait_for_timeout(800)
            current += step
        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)
        logger.info("[Banner] Lazy-load scroll complete.")
    except Exception as e:
        logger.warning(f"[Banner] Lazy-load scroll error: {e}")


async def _scrape_banner_urls(page, domain):
    """
    DOM scraper covering Cases 1–6.

    Returns a list of dicts:
        {
            "src_url"  : str,   # absolute image URL
            "alt"      : str,   # alt attribute
            "link_href": str,   # enclosing <a> href (if any)
            "width"    : int,
            "height"   : int,
            "case"     : str,   # which case triggered this entry
        }
    """
    try:
        raw = await page.evaluate("""
            () => {
                const MIN_W = %d;
                const MIN_H = %d;
                const BANNER_KW = %s;
                const AD_IMG_KW = %s;

                // ── Helpers ──
                function absUrl(src) {
                    if (!src) return '';
                    try { return new URL(src, location.href).href; }
                    catch(e) { return src; }
                }

                function hasBannerClass(el) {
                    const cls = (el.className || '').toLowerCase();
                    const id  = (el.id || '').toLowerCase();
                    return BANNER_KW.some(k => cls.includes(k) || id.includes(k));
                }

                function isAdUrl(url) {
                    const u = url.toLowerCase();
                    return AD_IMG_KW.some(k => u.includes(k));
                }

                function imgDims(el) {
                    // Prefer natural size if rendered; fall back to attributes
                    return {
                        w: el.naturalWidth  || parseInt(el.getAttribute('width')  || el.width  || 0),
                        h: el.naturalHeight || parseInt(el.getAttribute('height') || el.height || 0),
                    };
                }

                function closestAnchor(el) {
                    let cur = el.parentElement;
                    while (cur && cur !== document.body) {
                        if (cur.tagName === 'A') return cur;
                        cur = cur.parentElement;
                    }
                    return null;
                }

                const results = [];
                const seenUrls = new Set();

                function addEntry(src, alt, link, w, h, caseLabel) {
                    const url = absUrl(src);
                    if (!url || seenUrls.has(url)) return;
                    seenUrls.add(url);
                    results.push({
                        src_url:   url,
                        alt:       alt || '',
                        link_href: link || '',
                        width:     w   || 0,
                        height:    h   || 0,
                        case:      caseLabel,
                    });
                }

                // ── Case 1: <img> inside <a rel=nofollow> or target=_blank ──
                document.querySelectorAll('a[rel*="nofollow"] img, a[target="_blank"] img').forEach(img => {
                    const {w, h} = imgDims(img);
                    const src = img.src || img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || '';
                    if (!src) return;
                    const anchor = closestAnchor(img) || img.closest('a');
                    const href = anchor ? anchor.href : '';
                    addEntry(src, img.alt, href, w, h, 'case1_nofollow_link');
                });

                // ── Case 2: All <img> with data-src / data-lazy-src (lazy-load) ──
                document.querySelectorAll('img[data-src], img[data-lazy-src], img[data-original]').forEach(img => {
                    const src = img.getAttribute('data-src')
                              || img.getAttribute('data-lazy-src')
                              || img.getAttribute('data-original');
                    if (!src) return;
                    const {w, h} = imgDims(img);
                    const anchor = closestAnchor(img);
                    addEntry(src, img.alt, anchor ? anchor.href : '', w, h, 'case2_lazy_src');
                });

                // ── Case 3: <img> inside banner/ad/sidebar containers ──
                document.querySelectorAll('img').forEach(img => {
                    // Walk up 4 levels to find a banner container
                    let el = img;
                    let foundBannerContainer = false;
                    for (let i = 0; i < 4; i++) {
                        el = el.parentElement;
                        if (!el || el === document.body) break;
                        if (hasBannerClass(el)) { foundBannerContainer = true; break; }
                    }
                    if (!foundBannerContainer) return;
                    const src = img.src || img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || '';
                    if (!src) return;
                    const {w, h} = imgDims(img);
                    const anchor = closestAnchor(img);
                    addEntry(src, img.alt, anchor ? anchor.href : '', w, h, 'case3_banner_class');
                });

                // ── Case 4: CSS background-image ──
                const allEls = document.querySelectorAll('[style]');
                allEls.forEach(el => {
                    const style = el.getAttribute('style') || '';
                    const bgMatch = style.match(/background(?:-image)?\s*:\s*url\(["']?([^"')]+)["']?\)/);
                    if (!bgMatch) return;
                    const src = bgMatch[1];
                    const rect = el.getBoundingClientRect();
                    const w = Math.round(rect.width);
                    const h = Math.round(rect.height);
                    if (w < MIN_W && h < MIN_H) return;
                    // Only include if URL or container hints at ad
                    if (!isAdUrl(src) && !hasBannerClass(el)) return;
                    addEntry(src, el.getAttribute('aria-label') || '', '', w, h, 'case4_bg_image');
                });

                // ── Case 5: iframe ad — collect src for metadata (not image itself) ──
                document.querySelectorAll('iframe').forEach(iframe => {
                    const src = iframe.src || iframe.getAttribute('data-src') || '';
                    if (!src) return;
                    if (!isAdUrl(src) && !hasBannerClass(iframe)) return;
                    // Store iframe src as link_href; no image file to download
                    if (!seenUrls.has(src)) {
                        seenUrls.add(src);
                        results.push({
                            src_url:   '',
                            alt:       'iframe-ad',
                            link_href: absUrl(src),
                            width:     parseInt(iframe.width  || 0),
                            height:    parseInt(iframe.height || 0),
                            case:      'case5_iframe_ad',
                        });
                    }
                });

                // ── Case 6: <picture><source srcset> ──
                document.querySelectorAll('picture').forEach(pic => {
                    const anchor = closestAnchor(pic);
                    const href   = anchor ? anchor.href : '';
                    // Prefer highest-res srcset
                    const sources = pic.querySelectorAll('source[srcset]');
                    sources.forEach(src => {
                        const srcset = src.getAttribute('srcset') || '';
                        // srcset can be "url 2x, url2 1x" — take first URL
                        const firstUrl = srcset.trim().split(/[,\s]+/)[0];
                        if (!firstUrl) return;
                        const img = pic.querySelector('img');
                        const {w, h} = img ? imgDims(img) : {w: 0, h: 0};
                        addEntry(firstUrl, img ? img.alt : '', href, w, h, 'case6_picture_srcset');
                    });
                    // Fallback img inside <picture>
                    const fallbackImg = pic.querySelector('img');
                    if (fallbackImg) {
                        const src = fallbackImg.src || fallbackImg.getAttribute('data-src') || '';
                        const {w, h} = imgDims(fallbackImg);
                        addEntry(src, fallbackImg.alt, href, w, h, 'case6_picture_img');
                    }
                });

                // ── General pass: any large <img> with ad-like URL ──
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src || img.getAttribute('data-src') || '';
                    if (!src) return;
                    if (!isAdUrl(src)) return;
                    const {w, h} = imgDims(img);
                    if (w < MIN_W && h < MIN_H) return;
                    const anchor = closestAnchor(img);
                    addEntry(src, img.alt, anchor ? anchor.href : '', w, h, 'case_ad_url_img');
                });

                return results;
            }
        """ % (
            MIN_BANNER_WIDTH,
            MIN_BANNER_HEIGHT,
            json.dumps(BANNER_CLASS_KEYWORDS),
            json.dumps(AD_IMAGE_URL_KEYWORDS),
        ))
        return raw if isinstance(raw, list) else []
    except Exception as e:
        logger.warning(f"[Banner] DOM scrape error: {e}")
        return []


def _url_to_filename(url: str) -> str:
    """
    Convert a URL to a safe local filename using its MD5 hash
    plus the original extension (if any).
    """
    ext = ""
    path = url.split("?")[0].split("#")[0]
    for e in BANNER_IMAGE_EXTENSIONS:
        if path.lower().endswith(e):
            ext = e
            break
    if not ext:
        ext = ".jpg"  # fallback
    return hashlib.md5(url.encode()).hexdigest() + ext


def _download_banner_image(url: str, save_dir: str, domain: str) -> str | None:
    """
    Download a banner image to `save_dir`.
    Returns the local file path on success, or None on failure.
    Uses a browser-like User-Agent and Referer to avoid hotlink protection.
    """
    filename = _url_to_filename(url)
    filepath = os.path.join(save_dir, filename)

    if os.path.exists(filepath):
        return filepath  # already downloaded

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://{domain}/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        if len(data) < 500:  # suspiciously small — skip (likely 1px tracker)
            logger.debug(f"[Banner] Skipping tiny image ({len(data)} bytes): {url[:80]}")
            return None
        with open(filepath, "wb") as f:
            f.write(data)
        logger.info(f"[Banner] ✓ Downloaded ({len(data)//1024}KB): {filename}")
        return filepath
    except URLError as e:
        logger.warning(f"[Banner] Download failed ({e}): {url[:100]}")
        return None
    except Exception as e:
        logger.warning(f"[Banner] Unexpected download error ({e}): {url[:100]}")
        return None


async def _screenshot_crop_banner(page, entry: dict, save_dir: str) -> str | None:
    """
    Fallback: find the <img> element for a banner by its src URL and
    take a cropped screenshot of its bounding box.
    Returns local file path on success, or None.
    """
    src_url = entry.get("src_url", "")
    if not src_url:
        return None

    try:
        # Find the element matching this src (or data-src)
        el = await page.query_selector(
            f'img[src="{src_url}"], img[data-src="{src_url}"], img[data-lazy-src="{src_url}"]'
        )
        if not el:
            return None

        bbox = await el.bounding_box()
        if not bbox or bbox["width"] < 10 or bbox["height"] < 10:
            return None

        filename = "crop_" + _url_to_filename(src_url) + ".png"
        filepath = os.path.join(save_dir, filename)

        await page.screenshot(
            path=filepath,
            clip={
                "x":      bbox["x"],
                "y":      bbox["y"],
                "width":  bbox["width"],
                "height": bbox["height"],
            },
        )
        logger.info(f"[Banner] ✓ Screenshot-crop fallback saved: {filename}")
        return filepath

    except Exception as e:
        logger.debug(f"[Banner] Screenshot-crop error: {e}")
        return None


async def collect_banner_images(page, domain: str, evidence_collector: dict) -> list[dict]:
    """
    Phase 5b — Banner Image Collection for OCR Branch 1.

    Orchestrates all 7 banner cases:
      Case 1–6 : DOM scraper via _scrape_banner_urls()
      Case 7   : Network-intercepted ad image URLs (already in
                 evidence_collector["banner_network_hits"])

    For each discovered image URL:
      1. Try HTTP download (with browser-like headers).
      2. On failure → screenshot-crop from the live DOM.

    Returns list of banner metadata dicts:
        {
            "local_path" : str | None,
            "src_url"    : str,
            "alt"        : str,
            "link_href"  : str,
            "width"      : int,
            "height"     : int,
            "case"       : str,
            "download_ok": bool,
        }
    """
    logger.info("[Phase 5b] Starting banner image collection...")

    safe_domain = re.sub(r'[\\/*?":.<>|]', "_", domain) if domain else "unknown"
    save_dir = os.path.join("logs", safe_domain, BANNERS_SUBDIR)
    os.makedirs(save_dir, exist_ok=True)

    # ── Step 1: Trigger lazy-load so data-src images become real src ──
    await _trigger_lazy_load(page)

    # ── Step 2: DOM scrape (Cases 1–6) ──
    dom_entries = await _scrape_banner_urls(page, domain)
    logger.info(f"[Phase 5b] DOM scraper found {len(dom_entries)} candidate(s).")

    # ── Step 3: Merge Case 7 network hits ──
    net_hits = evidence_collector.get("banner_network_hits", [])
    for hit in net_hits:
        url = hit["url"]
        # Avoid duplicates with DOM entries
        if not any(e["src_url"] == url for e in dom_entries):
            dom_entries.append({
                "src_url":   url,
                "alt":       "",
                "link_href": "",
                "width":     0,
                "height":    0,
                "case":      "case7_network_intercept",
            })
    logger.info(
        f"[Phase 5b] After merging Case 7: {len(dom_entries)} total candidate(s)."
    )

    # ── Step 4: Download / screenshot-crop each image ──
    banners = []
    for entry in dom_entries:
        src = entry.get("src_url", "")

        # Case 5 (iframe ads) have no image src — store metadata only
        if entry.get("case") == "case5_iframe_ad":
            banners.append({**entry, "local_path": None, "download_ok": False})
            continue

        if not src:
            continue

        # Try HTTP download first
        local_path = _download_banner_image(src, save_dir, domain)
        download_ok = local_path is not None

        # Fallback: screenshot-crop
        if not download_ok:
            local_path = await _screenshot_crop_banner(page, entry, save_dir)
            download_ok = local_path is not None

        banners.append({
            **entry,
            "local_path": local_path,
            "download_ok": download_ok,
        })

    ok_count = sum(1 for b in banners if b.get("download_ok"))
    logger.info(
        f"[Phase 5b] Banner collection complete: "
        f"{len(banners)} found, {ok_count} downloaded successfully."
    )
    return banners


# ──────────────────────────────────────────────
# SCREENSHOT CAPTURE
# ──────────────────────────────────────────────

async def capture_screenshot(page, domain, episode_index):
    """
    Capture a full-page screenshot and save to logs/<domain>/screenshots/.
    Returns the file path.
    """

    safe_domain = re.sub(r'[\\/*?:"<>|]', "_", domain) if domain else "unknown"
    screenshots_dir = os.path.join("logs", safe_domain, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_domain}_ep{episode_index}_{timestamp}.png"
    filepath = os.path.join(screenshots_dir, filename)

    try:
        await page.screenshot(
            path=filepath,
            full_page=True,
        )
        logger.info(f"[Screenshot] Saved: {filepath}")

    except Exception as e:
        logger.warning(f"[Screenshot] Error: {e}")
        filepath = None

    return filepath


# ──────────────────────────────────────────────
# SINGLE EPISODE INVESTIGATION
# ──────────────────────────────────────────────

async def investigate_episode(
    context,
    page,
    episode_url,
    global_evidence,
    episode_index,
    domain,
):
    """
    Investigate a single episode page:
    1. Navigate with Cloudflare wait
    2. Listen for stream network requests AND responses
    3. Inject anti-devtools scripts into player iframes
    4. Try to click player area to trigger streams
    5. Navigate into player iframe to force stream loading
    6. Extract iframes
    7. Pierce iframes for hidden video sources
    8. Capture screenshot
    """

    logger.info(
        f"\n{'='*60}\n"
        f"[Episode {episode_index}] Investigating: {episode_url}\n"
        f"{'='*60}"
    )

    # Per-episode evidence collector
    episode_evidence = {
        "episode_url": episode_url,
        "streams": [],
        "iframes": [],
        "screenshot_path": None,
    }

    # Setup network interceptor for RESPONSES
    response_interceptor = create_network_interceptor(
        episode_evidence
    )
    page.on("response", response_interceptor)

    # Also intercept REQUESTS (catches .m3u8 that may not
    # have responses logged, e.g. if CORS blocks them)
    request_interceptor = _create_request_interceptor(
        episode_evidence
    )
    page.on("request", request_interceptor)

    try:
        # Navigate to episode
        cf_ok = await bypass_cloudflare(page, episode_url)

        if not cf_ok:
            logger.warning(
                f"[Episode {episode_index}] "
                f"Cloudflare block on episode page."
            )
            episode_evidence["cloudflare_blocked"] = True
            return episode_evidence

        # ── Inject anti-devtools into player iframes ──
        await _inject_anti_devtools_into_iframes(page)

        # Wait for network to settle & streams to load
        logger.info(
            f"[Episode {episode_index}] "
            f"Waiting {NETWORK_SETTLE_MS}ms for network..."
        )
        await page.wait_for_timeout(NETWORK_SETTLE_MS)

        # ── First click attempt ──
        await _try_click_player(page)
        await page.wait_for_timeout(3000)

        # ── Navigate into player iframe to trigger stream ──
        await _enter_player_iframe(page, episode_evidence, domain)

        # Wait more for streams after iframe interaction
        await page.wait_for_timeout(5000)

        # ── Second click attempt (in case first was absorbed) ──
        if not episode_evidence["streams"]:
            logger.info(
                f"[Episode {episode_index}] "
                f"No streams yet, trying second click..."
            )
            await _try_click_player(page)
            await page.wait_for_timeout(5000)

        # Extract iframes
        iframes = await extract_iframes(page, domain)
        episode_evidence["iframes"] = iframes

        # Stage 2B: Pierce into iframes for hidden video sources
        await pierce_iframes(page, episode_evidence, domain)

        # Capture screenshot
        screenshot_path = await capture_screenshot(
            page, domain, episode_index
        )
        episode_evidence["screenshot_path"] = screenshot_path

    except Exception as e:
        logger.error(
            f"[Episode {episode_index}] Error: {e}"
        )
        episode_evidence["error"] = str(e)

    finally:
        # Remove listeners to avoid stacking
        page.remove_listener("response", response_interceptor)
        page.remove_listener("request", request_interceptor)

    # Summary
    logger.info(
        f"[Episode {episode_index}] Results: "
        f"{len(episode_evidence['streams'])} streams, "
        f"{len(episode_evidence['iframes'])} iframes"
    )

    return episode_evidence


def _create_request_interceptor(evidence_collector):
    """
    Intercept outgoing REQUESTS to catch .m3u8/.mp4 URLs
    that might not produce accessible responses (CORS etc.)
    """

    async def handle_request(request):

        url = request.url
        url_lower = url.lower()

        # Only care about actual stream files
        is_stream = any(
            ext in url_lower
            for ext in [".m3u8", ".mp4", ".mpd", ".ts"]
        )

        if is_stream:
            stream_entry = {
                "url": url,
                "content_type": "detected_from_request",
                "status": 0,
                "matched_by": "request_intercept",
            }

            existing = [
                s["url"] for s in evidence_collector["streams"]
            ]

            if url not in existing:
                evidence_collector["streams"].append(stream_entry)
                logger.info(
                    f"[Stream/Req] ★ Captured request: "
                    f"{url[:120]}..."
                )

    return handle_request


async def _inject_anti_devtools_into_iframes(page):
    """
    Inject anti-DevTools detection script into all
    player-related iframes on the page.
    """

    anti_devtools_js = """
        try {
            Object.defineProperty(window, 'outerHeight', {
                get: () => window.innerHeight
            });
            Object.defineProperty(window, 'outerWidth', {
                get: () => window.innerWidth
            });
            window.__firebug = undefined;
            window.Firebug = undefined;
        } catch(e) {}
    """

    for frame in page.frames:
        frame_url = frame.url or ""
        if (
            "player" in frame_url.lower()
            or "stream" in frame_url.lower()
            or "embed" in frame_url.lower()
        ):
            try:
                await frame.evaluate(anti_devtools_js)
                logger.info(
                    f"[Anti-DevTools] Injected into frame: "
                    f"{frame_url[:80]}"
                )
            except Exception as e:
                logger.debug(
                    f"[Anti-DevTools] Cannot inject into "
                    f"{frame_url[:60]}: {e}"
                )


async def _enter_player_iframe(page, evidence_collector, domain):
    """
    Find the main player iframe, navigate into it,
    and try to trigger video playback from within.
    This forces the player to load stream URLs even if
    the outer page's DevTools detection blocked them.
    """

    player_frame = None

    for frame in page.frames:
        frame_url = (frame.url or "").lower()
        if (
            "player" in frame_url
            or "stream" in frame_url
            or "embed" in frame_url
        ) and "youtube" not in frame_url:
            player_frame = frame
            break

    if not player_frame:
        logger.info("[iFrame Enter] No player iframe found.")
        return

    logger.info(
        f"[iFrame Enter] Entering player frame: "
        f"{player_frame.url[:100]}"
    )

    try:
        # Try to click play button inside the iframe
        play_selectors = [
            ".jw-icon-playback",
            ".vjs-big-play-button",
            ".play-button",
            ".btn-play",
            "button[aria-label*='play' i]",
            "button[aria-label*='Play' i]",
            "[class*='play']",
            "video",
        ]

        for selector in play_selectors:
            try:
                el = await player_frame.query_selector(selector)
                if el:
                    await el.click(timeout=3000)
                    logger.info(
                        f"[iFrame Enter] ▶ Clicked inside iframe: "
                        f"{selector}"
                    )
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        # Also try to extract any video/source src from
        # inside the iframe
        video_srcs = await player_frame.evaluate("""
            () => {
                const results = [];

                // Check <video> elements
                document.querySelectorAll('video').forEach(v => {
                    if (v.src) results.push(v.src);
                    if (v.currentSrc) results.push(v.currentSrc);
                });

                // Check <source> elements
                document.querySelectorAll('source').forEach(s => {
                    if (s.src) results.push(s.src);
                });

                // Check JWPlayer instance
                if (typeof jwplayer !== 'undefined') {
                    try {
                        const p = jwplayer();
                        const playlist = p.getPlaylist();
                        if (playlist) {
                            playlist.forEach(item => {
                                if (item.file) results.push(item.file);
                                if (item.sources) {
                                    item.sources.forEach(src => {
                                        if (src.file)
                                            results.push(src.file);
                                    });
                                }
                            });
                        }
                    } catch(e) {}
                }

                // Check Plyr instance
                if (typeof Plyr !== 'undefined') {
                    try {
                        const players = document.querySelectorAll(
                            '.plyr'
                        );
                        players.forEach(p => {
                            if (p.plyr && p.plyr.source)
                                results.push(p.plyr.source);
                        });
                    } catch(e) {}
                }

                return [...new Set(results.filter(r =>
                    r && r !== '' && !r.startsWith('blob:')
                ))];
            }
        """)

        for src in video_srcs:
            stream_entry = {
                "url": src,
                "content_type": "video (from iframe JS)",
                "status": 200,
                "matched_by": "iframe_js_extraction",
                "parent_iframe": player_frame.url,
            }
            existing = [
                s["url"] for s in evidence_collector["streams"]
            ]
            if src not in existing:
                evidence_collector["streams"].append(stream_entry)
                logger.info(
                    f"[iFrame Enter] ★ Found stream via JS: "
                    f"{src[:120]}"
                )

    except Exception as e:
        logger.warning(
            f"[iFrame Enter] Error interacting with "
            f"player frame: {e}"
        )


async def _try_click_player(page):
    """
    Attempt to click on common player selectors
    to trigger video loading and potential popup ads.
    """

    player_selectors = [
        ".player",
        "#player",
        ".video-player",
        "#video-player",
        "video",
        ".play-btn",
        ".btn-play",
        '[class*="player"]',
        '[id*="player"]',
        ".watch-video",
        ".movie-player",
    ]

    for selector in player_selectors:

        try:
            element = await page.query_selector(selector)

            if element:
                await element.click(timeout=3000)
                logger.info(
                    f"[Player] Clicked: {selector}"
                )
                await page.wait_for_timeout(2000)
                return True

        except Exception:
            continue

    # Fallback: click center of the page
    try:
        viewport = page.viewport_size
        if viewport:
            await page.mouse.click(
                viewport["width"] // 2,
                viewport["height"] // 2,
            )
            logger.info("[Player] Clicked center of viewport.")
            await page.wait_for_timeout(2000)
    except Exception:
        pass

    return False


# ──────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ──────────────────────────────────────────────

async def _run_step2_async(domain, url):
    """
    Async orchestrator for Step 2 evidence collection.
    """

    logger.info(
        f"\n{'#'*60}\n"
        f"  STEP 2: Deep Browser Evidence Collection\n"
        f"  Target: {url}\n"
        f"{'#'*60}\n"
    )

    # Global evidence collector
    evidence = {
        "target_url": url,
        "target_domain": domain,
        "timestamp": datetime.now().isoformat(),
        "cloudflare_bypassed": False,
        "episodes_found_total": 0,
        "episodes_checked": 0,
        "popup_blocked_count": 0,
        "popup_urls": [],
        "episodes_detail": [],
        "all_streams": [],
        "all_iframes": [],
        "footer_analysis": {},
        "technical_flags": {},
        "dom_text": "",     # Full body text for Content Model (Step 3 Branch 2)
        "banners": [],      # Banner images for OCR Engine (Step 3 Branch 1)
        "banner_network_hits": [],  # Case 7: network-intercepted ad image URLs
    }

    stealth = Stealth(
        navigator_languages_override=("vi-VN", "vi"),
    )

    async with stealth.use_async(async_playwright()) as pw:

        browser, context, page = await launch_stealth_browser(pw)

        # ── Setup popup blocker on the context ──
        popup_blocker = create_popup_blocker(evidence)
        context.on("page", popup_blocker)

        try:

            # ────────────────────────────────
            # Phase 1: Bypass Cloudflare on homepage
            # ────────────────────────────────

            logger.info("[Phase 1] Bypassing Cloudflare...")

            cf_ok = await bypass_cloudflare(page, url)
            evidence["cloudflare_bypassed"] = cf_ok

            if not cf_ok:
                logger.error(
                    "[Phase 1] Cannot bypass Cloudflare. "
                    "Evidence will be limited."
                )
                evidence["technical_flags"]["cloudflare_bypassed"] = False

                # Still try to capture whatever we can
                footer = await scan_footer(page)
                evidence["footer_analysis"] = footer
                await capture_screenshot(page, domain, 0)

                return evidence

            # ────────────────────────────────
            # Phase 2: Crawl episode URLs
            # ────────────────────────────────

            logger.info("[Phase 2] Crawling episode URLs...")

            episode_urls = await crawl_episode_urls(page, domain)
            evidence["episodes_found_total"] = len(episode_urls)

            if not episode_urls:
                logger.warning(
                    "[Phase 2] No episode URLs found. "
                    "Trying to find sub-pages..."
                )
                # Fallback: grab any internal links
                episode_urls = await _fallback_crawl(page, domain)
                evidence["episodes_found_total"] = len(episode_urls)

            # ────────────────────────────────
            # Phase 3: Select sample episodes
            # ────────────────────────────────

            sample_count = min(
                MAX_EPISODES_TO_CHECK, len(episode_urls)
            )

            if sample_count > 0:
                sampled = random.sample(episode_urls, sample_count)
            else:
                sampled = []

            logger.info(
                f"[Phase 3] Selected {len(sampled)} episodes "
                f"from {len(episode_urls)} total."
            )

            evidence["episodes_checked"] = len(sampled)

            # ────────────────────────────────
            # Phase 4: Investigate each episode
            # ────────────────────────────────

            for idx, ep_url in enumerate(sampled, start=1):

                ep_evidence = await investigate_episode(
                    context, page, ep_url,
                    evidence, idx, domain,
                )

                evidence["episodes_detail"].append(ep_evidence)

                # Aggregate streams and iframes
                for stream in ep_evidence.get("streams", []):
                    if stream["url"] not in evidence["all_streams"]:
                        evidence["all_streams"].append(stream["url"])

                for iframe in ep_evidence.get("iframes", []):
                    src = iframe.get("iframe_src", "")
                    if src not in evidence["all_iframes"]:
                        evidence["all_iframes"].append(src)

            # ────────────────────────────────
            # Phase 5: Footer scan
            # ────────────────────────────────

            logger.info("[Phase 5] Scanning footer...")

            # Navigate back to homepage for footer scan
            await bypass_cloudflare(page, url)
            footer = await scan_footer(page)
            evidence["footer_analysis"] = footer

            # ── Extract full DOM HTML and clean it for Content Model (Step 3) ──
            logger.info("[Phase 5] Extracting and cleaning DOM text for Content Model...")
            try:
                html_content = await page.content()
                dom_text = get_clean_text_from_html(html_content)
                evidence["dom_text"] = dom_text
                logger.info(
                    f"[Phase 5] DOM text extracted and cleaned: {len(dom_text)} chars"
                )
            except Exception as e:
                logger.warning(f"[Phase 5] DOM text extraction error: {e}")

            # ────────────────────────────────
            # Phase 5b: Banner Image Collection (for OCR Branch 1)
            # ────────────────────────────────

            logger.info("[Phase 5b] Collecting banner images for OCR engine...")
            try:
                banners = await collect_banner_images(page, domain, evidence)
                evidence["banners"] = banners
            except Exception as e:
                logger.warning(f"[Phase 5b] Banner collection error: {e}")


            # ────────────────────────────────
            # Phase 6: Compile technical flags
            # ────────────────────────────────

            evidence["technical_flags"] = {
                "cloudflare_bypassed": cf_ok,
                "is_drm_protected": _check_drm(evidence),
                "iframe_detected": len(evidence["all_iframes"]) > 0,
                "stream_intercepted": (
                    len(evidence["all_streams"]) > 0
                ),
                "has_legal_footer": (
                    not footer.get("FOOTER_ANONYMOUS", True)
                ),
                "popup_detected": (
                    evidence["popup_blocked_count"] > 0
                ),
            }

        except Exception as e:
            logger.error(f"[Step2] Fatal error: {e}")
            evidence["error"] = str(e)

        finally:
            await browser.close()

    # ── Summary log ──
    banners_ok = sum(1 for b in evidence.get("banners", []) if b.get("download_ok"))
    logger.info(
        f"\n{'='*60}\n"
        f"  STEP 2 COMPLETE\n"
        f"  Episodes checked  : {evidence['episodes_checked']}\n"
        f"  Streams found     : {len(evidence['all_streams'])}\n"
        f"  Iframes found     : {len(evidence['all_iframes'])}\n"
        f"  Popups blocked    : {evidence['popup_blocked_count']}\n"
        f"  Banners collected : {len(evidence.get('banners', []))} "
        f"({banners_ok} downloaded)\n"
        f"  Footer anonymous  : "
        f"{evidence.get('footer_analysis', {}).get('FOOTER_ANONYMOUS', 'N/A')}\n"
        f"{'='*60}\n"
    )

    return evidence


async def _fallback_crawl(page, domain):
    """
    Fallback: if no episode-pattern URLs found,
    grab any internal links that look like content pages
    (not static assets, not social media links).
    """

    all_hrefs = await page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href]');
            return Array.from(links).map(a => a.href);
        }
    """)

    internal_links = []
    seen = set()

    skip_patterns = [
        r"\.(css|js|png|jpg|jpeg|gif|svg|ico|woff)",
        r"(facebook|twitter|telegram|youtube|tiktok)",
        r"#$",
        r"javascript:",
    ]
    skip_re = re.compile(
        "|".join(skip_patterns), re.IGNORECASE
    )

    for href in all_hrefs:

        if not href or href in seen:
            continue

        try:
            parsed = urlparse(href)
            if parsed.netloc and domain not in parsed.netloc:
                continue
        except Exception:
            continue

        if skip_re.search(href):
            continue

        # Must have a meaningful path (not just "/")
        path = parsed.path.strip("/")
        if path and len(path) > 3:
            seen.add(href)
            internal_links.append(href)

    logger.info(
        f"[Fallback Crawl] Found {len(internal_links)} "
        f"internal links."
    )

    return internal_links[:20]  # Cap at 20


def _check_drm(evidence):
    """
    Check if any intercepted streams suggest DRM protection.
    """

    drm_signals = [
        "widevine", "playready", "fairplay",
        "clearkey", "drm", "license",
    ]

    for stream_url in evidence.get("all_streams", []):

        if any(sig in stream_url.lower() for sig in drm_signals):
            return True

    return False


# ──────────────────────────────────────────────
# SYNC WRAPPER (for main.py)
# ──────────────────────────────────────────────

def run_step2(domain, url):
    """
    Synchronous entry point for Step 2.
    Call this from main.py.

    Args:
        domain: Normalized domain (e.g. "animevietsub.by")
        url: Full URL (e.g. "https://animevietsub.by/")

    Returns:
        dict: Step 2 evidence buffer
    """

    # Ensure URL has scheme
    if not url.startswith("http"):
        url = "https://" + url

    return asyncio.run(_run_step2_async(domain, url))


# ──────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":

    import sys

    target_domain = "animevietsub.by"
    target_url = "https://animevietsub.by/"

    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        target_domain = urlparse(target_url).netloc
        if target_domain.startswith("www."):
            target_domain = target_domain[4:]

    result = run_step2(target_domain, target_url)

    # Save output
    safe = re.sub(r'[\\/*?:"<>|]', "_", target_domain) if target_domain else "unknown"
    domain_logs_dir = os.path.join("logs", safe)
    os.makedirs(domain_logs_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(domain_logs_dir, f"{safe}_step2_{ts}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            result, f,
            indent=4, ensure_ascii=False, default=str,
        )

    print(f"\n[OUTPUT] Saved to: {out_path}")
    try:
        print(
            json.dumps(
                result, indent=2,
                ensure_ascii=False, default=str,
            )
        )
    except UnicodeEncodeError:
        # Fallback for Windows cp1252 console
        print(
            json.dumps(
                result, indent=2,
                ensure_ascii=True, default=str,
            )
        )

