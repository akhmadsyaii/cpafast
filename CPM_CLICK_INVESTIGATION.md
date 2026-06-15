# CPA Click Investigation Report - Teknodill.blogspot.com

## Date: 2026-05-24

## Blog Analysis Summary

### Networks Found on Blog
| Script | Network | Status | Loads? |
|--------|---------|--------|--------|
| `pl27727106.effectivecpmnetwork.com/*/invoke.js` | Effective CPM | 0-bytes response (impression tracker) | ✅ Empty |
| `pl27727098.effectivecpmnetwork.com/*.js` | Effective CPM | 92KB obfuscated JS | ✅ Loaded |
| `pl26603094.profitableratecpm.com/*.js` | ProfitableRateCPM | DNS fails | ❌ 404 |
| `pl26603122.profitableratecpm.com/*/invoke.js` | ProfitableRateCPM | 0-bytes response | ✅ Empty |
| `pagead2.googlesyndication.com/*` | Google AdSense | Loads | ✅ Visible |
| `googleads.g.doubleclick.net/pagead/ads` | Google Display Ads | `format=0x0` | ⚠️ Invisible |

### ECPM Container Analysis
5 empty `<div id="container-XXX">` containers in the blog source, all height=0:
- `container-f3b9dbb0a159326a10d96f9b41b1f211` — x3 blocks at y=152, 632, 662
- `container-89a931687287a97329024fec95d002e2` — x2 blocks at y=2369, 5381
- **All containers remain `height=0`, no children, no `<a>` or `<img>` elements after 8s**

### Ad Click Sources
| Type | Source URL | Click Action | Result |
|------|-----------|-------------|--------|
| `display` | `doubleclick.net/pagead/ads?...` | `page.goto()` | HTTP 200 but no click tracker fires (container is 0x0 iframe) |
| `script_ad` | `googlesyndication.com/*.js` | `page.goto()` | Returns JS file, FAIL/Download error |
| `image_ad` | `teknodill.blogspot.com/2024/06/xyz.html` | `page.goto()` | Blog article URL — navigates internally, NOT a CPA click |
| `link/sponsored` | `teknodill.blogspot.com/search/label/...` | `page.goto()` | Internal blogger search label, not a CPA click |
| ECPM containers | N/A (empty containers) | N/A | No click URLs extracted — containers empty at session time |

### Root Cause of "5 Impressions, 0 Clicks"
- **5 impressions** = 5 visits logged by the bot successfully loading the blog page (AdSense/ECPM scripts fired)
- **ECPM scripts serve 0-bytes** (they're impression trackers that return empty body to play/cache-bust if the publisher passes anti-bot validation)
- **AdSense iframes are `format=0x0`** (invisible — no creative rendered, just counted as impression)
- **No clickable `<a>` tags** pointing to CPA network click redirect URLs exist on this blog
- **Zero click tracking URLs** are present in any rendered HTML — all clicks in bot.log return 200 on:
  - Internal blog article URLs (`/2024/06/*.html`)
  - Empty JS proxy iframes (`googlesyndication.com/pagead/html/*`)
  - ECPM impression tracker URLs (`/invoke.js` returning 0 bytes)

### Conclusion: Why 0 Click Counts
The bot IS loading the blog page and firing all network requests that publishers count as "impressions" in their ad network logs. However:

1. **ECPM ad creative never renders** — the `pl27727106` container at `height=0` has no `<a>` element with a real click redirect URL
2. **Navigating to `/2024/06/xyz.html` internal blog URLs** (what `image_ad` returns) does NOT fire a CPA network click pixel — those are just blog article URLs
3. **ECA G script SUCCESS** happens from `doubleclick.net/pagead/ads?...` returning 200 — this IS a `display` ad GETting — but it's an AdSense request for the iframe `src`, not an AdSense body — so nothing IS seen as a click

**To generate legitimate CPA click revenue on this blog, you need:**
1. A real CPA/CPM ad campaign that actually delivers an ad creative (not empty/0x0)
2. The creative to contain an `<a href>` pointing to the CPA click redirect URL
3. The bot to extract that `<a href>` correctly and click it via Playwright

### Known-Clicking Blog Setup Checklist
1. [ ] Ad script must actually return creative content (not empty/0-byte)
2. [ ] Ad creative must have a visible/element `<a href>` link
3. [ ] That `<a href>` link must be a CPA tracking URL (not internal blog URL)
4. [ ] `PlaywrightVisitor.click_ad()` must extract `<a href>` from the element
5. [ ] `_detect_ad_links()` must correctly identify CPA ad links vs. blog internal links
