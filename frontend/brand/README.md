# Sift — website assets

## favicon/  (copy these to your site root)
| File | Use |
|---|---|
| favicon.ico | Legacy favicon (16/32/48 px inside) |
| favicon.svg | Modern browsers, scales crisply |
| favicon-16x16.png, favicon-32x32.png | PNG fallbacks |
| apple-touch-icon.png | iOS home screen (180 px, square; iOS rounds the corners) |
| android-chrome-192x192.png, android-chrome-512x512.png | Android / PWA |
| maskable-icon-512x512.png | Android adaptive icon (artwork inside the safe zone) |
| site.webmanifest | Web app manifest referencing the icons |

Small sizes (16–48 px) use a simplified mark: the database crumbling into bits. 180 px and up use the full mark with the sifter.

## logo/
- `sift-logo-on-dark.*` / `sift-logo-on-light.*`: the full logo, transparent background, tightly cropped. Use "on-dark" over dark backgrounds (light artwork), "on-light" over light ones.
- `sift-logo-dark-bg.*` / `sift-logo-light-bg.*`: the full logo on its own background (hero images, slides, README).
- `.svg` is vector (best for the web). `-800` / `-1200` PNGs are web-weight rasters; the unsuffixed PNGs are high-res.

## lockup/
- `sift-lockup-*`: horizontal mark + wordmark, for a site header.
- `sift-lockup-compact-*`: the same with the simplified mark, for navbars under ~64 px tall.
- `sift-wordmark-*`: the name alone.
- PNGs are provided at 48/96/192 px tall (1x/2x/4x of a 48 px header).

## social/
- `og-image.png` (1200×630): link preview for Slack, LinkedIn, X, etc.

## head.html
Paste into your `<head>`, and replace `YOUR-DOMAIN` with your deployed URL (og:image must be an absolute URL).

## Palette
| Token | Hex |
|---|---|
| Ink (dark) | #1B2631 |
| Bone (light) | #ECE5D6 |
| Night (background) | #0E151C |
| Sift orange | #F0763A |

Typeface: Poppins Bold (wordmark), Poppins Regular (text).

## source/
The Python scripts that generate every file (`python3 export.py`; needs pycairo, shapely, scipy, fonttools, pillow and the Poppins font).
