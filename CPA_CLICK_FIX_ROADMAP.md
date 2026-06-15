# CPA Click Fix Roadmap — Teknodill.blogspot.com

## Current State: WHY Clicks = 0

| Problem | Root Cause |
|---------|-----------|
| 5 impressions confirmed | Ecpm/AdSense scripts fire HTTP requests → trackers count → 5× = 5 impressions |
| 0 clicks | ECPM container divs = empty (height=0, no children). No `<a>` element to click. |
| Why empty containers? | Either: (1) ECPM network doesn't serve creatives from this region IP; (2) ECPM uses `window.open()` instead of `<a>` (popunder strategy); (3) Blogger `data-cfasync="false"` breaks async loading; (4) `format=0x0` Google AdSense slot — no visible creative rendered |

## What YOU Need to Do First (Blog Side)

### Check your ad network dashboard
1. Log into your ECPM/ad network dashboard
2. Find the placement ID for teknodill.blogspot.com
3. Check the "ad tag" or "ad unit" URL — it should be a direct `<script src="...">` OR an `iframe src="..."` pointing to a creative URL

### Fix the blog template if needed
If ECPM `container-*` divs end up empty:
- Make sure blogger template has `<script async data-cfasync="false" src="https://pl27727106.effectivecpmnetwork.com/.../invoke.js"></script>` AND the container div is NOT `display:none`
- Try setting the container to `display:block` explicitly:
  ```css
  div[id^="container-"] { display: block !important; min-height: 250px; }
  ```
- Check if your ad network gives you a DIRECT `<script>` tag for a banner/overlay ad type (not `invoke.js`)

### Try a different ad format/node
Try changing the format from "banner/popup" to "direct_link" or "widget" in the ECPM dashboard. The "invoke.js" is specifically for embedded popups/slide-ins — direct link ads provide a direct URL for `window.open()` handling which an ad-click bot can handle.

## What was fixed in the bot (code side)

| Bug | Fix |
|-----|-----|
| `script_ad` / `iframe` hard-skip blocking ALL display/iframe clicks | Removed hard-skip filter |
| `PlaywrightVisitor.click_ad()` uses `page.goto()` but browser blocks JS download | Added `wait_until="domcontentloaded"` |
| `ERR_CERT_AUTHORITY_INVALID` through proxy | Added `ignore_https_errors: True` |
| `PlaywrightVisitor.visit()` invalid `ignore_http_errors` option | Removed option, kept only `ignore_https_errors` |
| `image_ad` clicks returning blog internal URLs | Fixed — now filters out blog-internal URLs |
| `_click_ads()` didn't detect script_ad filter properly | Cleaned up filter logic |
| `last_error` scope guard in `_visit_with_requests` | Replaced with proper `error="Unknown"` |
| Dead imports `HTTPAdapter` / `Retry` in `proxy_manager.py` | Removed |

## Fix #1: Remove scripts from invoker

If the blog uses `pl27727098.effectivecpmnetwork.com/*.js` that returns 92KB acc reactive JS:
- The 92KB JS is the ad script - it handles `touchPixel('/pixel/sbe?t=...')` — it fires an impression pixel
- The click fire happens internally via `fireClick()` — you need to find the `onclick` handler URL

## Future Bot Improvements Needed

1. **Detect open-window popup/opens** — `window.open(url)` is how many ad networks implement clicks; the URL to `window.open` is a sub-string of the ECPM script but needs the security code
2. **Use `ad_detector.py _detect_event_based_ads()`** — scan inline JS for `window.open`, `location.href=` etc to find ECPM click URLs
3. **Implement `_detect_cpa_urls()`** in `ad_detector.py` that looks for URL patterns like `/pixel/...`, `/click/...` in inline JS on the blog page
4. **Implement `ad_click_via_javascript()`** in `visitor.py` that uses `page.evaluate()` to fire the inline JS click handler for the current ad element
5. **Add headless detection bypass** — use `--start-maximized` or real browser without stealth-flags so ECPM scripts actually populate their container divs
