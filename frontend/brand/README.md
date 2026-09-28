# Sift: website assets

The logo is the word **sift**. The dot of the i is a small database (orange top) whose bottom disk
crumbles into bits; the bits fall and stack up to form the top of the i's stem.

## logo/
- `sift-logo-on-light.*`: dark ink, transparent background, for light pages.
- `sift-logo-on-dark.*`: light ink, transparent background, for dark pages.
- `sift-logo-{light,dark}-bg.*`: the same on its own background.
- `.svg` is vector (use this on the web). PNGs are named by pixel height (`-h96` = 96 px tall, so 2x of a 48 px header).

## mark/
The i on its own, for tight spaces (avatars, loading states, watermark).

## favicon/  (copy to your site root)
| File | Use |
|---|---|
| favicon.ico, favicon.svg, favicon-16x16.png, favicon-32x32.png | Browser tab. At these sizes the full i is too thin, so they use just the crumbling database dot. |
| apple-touch-icon.png | iOS home screen, 180 px, square (iOS rounds the corners) |
| android-chrome-192x192.png, android-chrome-512x512.png | Android / PWA, full i on a rounded tile |
| maskable-icon-512x512.png | Android adaptive icon, artwork kept inside the safe zone |
| app-icon.svg | Vector version of the rounded app icon |
| site.webmanifest | Web app manifest |

## social/
`og-image.png` (1200 x 630) for link previews. The tagline is a placeholder based on the project brief; change it in `source/export_mini.py`.

## alternates/
The two other variants: A (all-ink database) and C (stem still filling).

## head.html
Paste into your `<head>` and replace `YOUR-DOMAIN` with the deployed URL (og:image needs an absolute URL).

## Palette & type
| Token | Hex |
|---|---|
| Ink | #16202A |
| Paper | #F7F3EC |
| Night | #0F161D |
| Bone (ink on dark) | #EFE9DC |
| Sift orange | #F0763A |

Typeface: Poppins Bold (wordmark), Poppins Regular (supporting text).

## source/
`python3 export_mini.py` regenerates everything (needs pycairo, shapely, fonttools, pillow and Poppins).
