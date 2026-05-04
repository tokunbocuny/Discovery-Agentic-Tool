# Resource Sharing GIS Visualization

**Bronx Community College (BCC) — CUNY Library**
Interactive animated map of BCC's interlibrary loan (ILL) and resource-sharing partner network.

---

## What It Does

A standalone HTML map that cycles through **770 partner library locations** with a pulsing marker that pans smoothly between stops. Built for presentations, lobby displays, and library communications.

- Dark-themed world map (CartoDB Dark Matter + Leaflet.js)
- Locations sequenced geographically — west-to-east sweep across the US, no chaotic jumps
- Single active marker — color matches the library type legend at every stop
- Pulse ring inherits the same type color at 35% opacity
- 6-second cycle per location: fly in → dwell → pan to next stop (constant zoom level 10)
- Info panel with library name, type, address, and progress bar
- Play / Pause / Prev / Next controls

---

## Quick Start

Open the map in any browser — no server or installation required:

```
file:///Users/tokunboadeshinajr/Desktop/Agentic%20Project/Resource%20Sharing%20GIS%20Visualization/resource_sharing_map.html
```

Or double-click `resource_sharing_map.html` in Finder.

---

## Files

| File | Description |
|------|-------------|
| `resource_sharing_map.html` | Standalone interactive map (open in browser) |
| `locations.json` | 770 geocoded partner library locations |
| `ungeocodeable_libraries.csv` | Original 69 unresolved entries — all resolved in v4 |
| `Resource_Sharing_GIS_Visualization_Documentation.docx` | Full project documentation (v4) |
| `README.md` | This file |

---

## Partner Network Summary

| Layer | Description | Count |
|-------|-------------|-------|
| Who We Borrow From | Libraries that lend materials to BCC | 198 |
| Who We Lend To | Libraries that borrow from BCC | 572 |
| **Total** | | **770** |

All 770 institutions are geocoded and shown on the map — matching the original Google Maps dataset exactly.

---

## Library Types & Colors

The active marker and its pulse ring change color at every stop to match the library type. These colors appear in the on-screen legend. The former "Active Stop" fixed-blue entry has been removed — the marker color is already represented by whichever type entry is currently active.

| Type | Color |
|------|-------|
| Academic | Salmon `#f78166` |
| Public | Green `#3fb950` |
| Federal / National Govt | Gold `#e3b341` |
| State Library | Sky Blue `#79c0ff` |
| Law Library | Lime `#56d364` |
| Medical | Pink-Red `#ff7b72` |
| Corporate | Orange `#ffa657` |
| Major Academic Research | Purple `#d2a8ff` |
| Schools Below College Level | Lavender `#bc8cff` |

---

## Animation Settings

Edit these constants near the top of the `<script>` block in `resource_sharing_map.html`:

```javascript
const CYCLE_MS    = 6000;  // total ms per location (6 seconds)
const ZOOM_IN     = 10;    // zoom level on arrival (neighborhood view)
const ZOOM_OUT    = 10;    // same as ZOOM_IN — smooth pan, no zoom change
const ZOOM_OUT_AT = 3500;  // ms after arrival to begin flying to next stop
```

---

## Data Source & Geocoding

Source data: Google My Maps project (exported as KMZ/KML).

Geocoding pipeline (Nominatim / OpenStreetMap API):

| Round | Method | Locations |
|-------|--------|-----------|
| KML original | Explicit coordinates from Google My Maps | 13 |
| Round 1 | Nominatim direct name search | 501 |
| Round 2 | Manual corrections dictionary (typos, abbreviations, CUNY/SUNY names) | 145 |
| Round 3 | Known addresses + city/county fallback | 69 |
| Layer fix | Restored 80 dual-layer entries lost to name-deduplication | 80 |
| **Total** | | **770** |

---

## Location Sequence

Stops are ordered using a **longitude-band snake sort** for smooth, visually coherent animation:

1. The longitude range is divided into 30 bands
2. Within each band, libraries are sorted by latitude — bands alternate direction (boustrophedon)
3. The result is a west-to-east geographic sweep: Hawaii → Alaska → Pacific Northwest → Rockies → Midwest → South → Northeast
4. 8 international libraries are redistributed evenly throughout (~every 86 stops)

| Metric | Before | After |
|--------|--------|-------|
| Wild jumps (>20°) | 202 | 16 |
| Avg pan distance | 17.78° | 4.17° |
| Median pan distance | — | 0.77° |

---

## International Locations

Eight international partners are evenly distributed throughout the sequence (~every 86th stop):

| Institution | Country |
|-------------|---------|
| University of Cape Town | South Africa |
| University of Fort Hare | South Africa |
| University of Auckland Library | New Zealand |
| Technical Knowledge Center Denmark | Denmark |
| Northumbria University | United Kingdom |
| Nasjonalbiblioteket, Avdeling Oslo | Norway |
| Royal Danish Library | Denmark |

---

## Maintenance

To add new libraries:
1. Add an entry to `locations.json` with `name`, `type`, `layer`, `address`, `lat`, `lng`
2. Paste the corresponding entry into the `locations` array in `resource_sharing_map.html`

---

**Author:** Tokunbo Adeshina Jr.
**Institution:** Bronx Community College (BCC), CUNY
**Email:** adetokunbojunior@gmail.com
**Version:** 8.0 — May 2026
