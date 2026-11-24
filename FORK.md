# aspectra.gallery: what differs from Aperture

aspectra.gallery is a fork of [Aperture](https://github.com/lucya-astralis/gallery) by
[lucya.systems](https://lucya.systems), AGPL-3.0 with the additional terms in `NOTICE`.
Updates from the original come in by git with `tools/upstream.sh` (see below), which is
why the Python package is still called `aperture` inside: only what a person sees carries
the fork's name.

## Taking in updates

`tools/upstream.sh` shows what is new upstream and merges it on a branch of its own
(`update/upstream-<version>`), so it can be looked at and adapted before it reaches main:

    tools/upstream.sh            what is new, and which files both sides changed
    tools/upstream.sh start      branch off main, merge upstream/main into it
    tools/upstream.sh continue   after resolving conflicts: checks, tests, commit
    tools/upstream.sh finish     main fast-forwards to the branch (nothing is pushed)
    tools/upstream.sh abort      drop the update

`start upstream/<branch>` takes in another upstream branch instead of main. Files this
fork removed stay removed. Before the commit the script checks what an update must not
undo (name, `REPO_URL`, `UPDATE_URL`, attribution, licence files, the aspectra sheets and
the starfield, no workflow beside `ci.yml`) and runs the tests in a throwaway container.
Git remembers each resolved conflict (`rerere`) and replays it the next time.

To keep merges quiet, the fork's changes stay where they are now: in files of its own
(`aspectra*.css`, `starfield.js`, this file) or in commented blocks. Notes on the fork go
here, never into `CHANGELOG.md`, which stays upstream's.

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
- Look of the admin: dressed like the aspectra.home dashboard (`console/static/aspectra.css`,
  after `style.css`, before the look sheet): kit colours and faces, the wide sidebar with
  the accent edge on the current place, panels as separate cards, the kit's buttons and the
  dot grid as backdrop. The wordmark is written in lower case.
- Header logo: the Saturn of aspectra.world (`logo/saturn.png`) unless gallery.cfg names a
  logo; the tab icon stays the gallery icon of the brand kit.

## Upstream updates

- 2026-11-22: merged upstream 3.3.0 (security release: auth bypass via the Host header, DNS rebinding, HTML in descriptions, dependencies) and 3.4.0 (Facet 1.8). Kept here: the aspectra starfield instead of Nova, "admin" in the password message. Not taken: `.github/workflows/image.yml`, which pushes an image to ghcr.io on every push; this fork's `ci.yml` only tests and builds, with its actions pinned to commits like upstream's.

## Planned

- In the admin: scan interval and folder watcher, GPS hiding/stripping, image sizes.
