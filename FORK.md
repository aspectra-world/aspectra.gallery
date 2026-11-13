# aspectra.gallery: what differs from Aperture

aspectra.gallery is a fork of [Aperture](https://github.com/lucya-astralis/gallery) by
[lucya.systems](https://lucya.systems), AGPL-3.0 with the additional terms in `NOTICE`.
Updates from the original come in by git (`git fetch upstream && git merge upstream/main`),
which is why the Python package is still called `aperture` inside: only what a person sees
carries the fork's name.

## Kept, because the licence asks for it

- `NOTICE`, `LICENSE`, `TRADEMARKS.md` and the copyright lines at the top of the source files.
- The attribution "based on Aperture by lucya.systems" with links, in the gallery's footer,
  in the admin's footer and about page, and in `/humans.txt`.
- The source of this version is linked from every page (AGPL section 13): the product name
  in the footer leads to this repository.

## Changed (2026-11-13)

- Name: aspectra.gallery everywhere a person sees it (`aperture/brand.py`, the admin's
  titles and texts, the command line). The admin calls itself "the admin", not "Aperture".
- Marks: the aspectra Saturn instead of the original's wing and aperture marks, in the admin
  (`console/templates/_mark.html`, boot animation in `splash.js`), as its favicon and as the
  gallery's default logo; the Saturn PNG for the command line. The original's logo files and
  its author's picture are removed.
- Update check: asks nobody by default (`UPDATE_URL` empty = off); the original asked its
  author's gallery.

- Look of the public gallery: the brand kit's dark ground, text and Blue Bell accent
  (`static/f/aspectra-tokens.css`, before the theme sheet, so an accent from gallery.cfg or
  album.cfg still wins), Manrope for text and Space Grotesk for headings and the wordmark
  (`static/f/aspectra.css`; a site face from gallery.cfg still wins). The backdrop without a
  wallpaper is the moving starfield of aspectra.world (`static/f/starfield.js`, built from
  its `starfield.ts`, dark scheme only) instead of Nova; wallpapers per album stay.

## Planned

- A card for aspectra.home (`GET /api/home`, contract 1).
- In the admin: scan interval and folder watcher, GPS hiding/stripping, image sizes.
