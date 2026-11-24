#!/usr/bin/env bash
# Brings updates from the original (Aperture by lucya.systems, remote "upstream")
# into this fork, on a branch of their own, so they can be looked at and adapted
# before they reach main. Pushes nothing.
#
#   tools/upstream.sh                 what is new upstream, and which of it touches
#                                     files this fork has changed (changes nothing)
#   tools/upstream.sh start [ref]     branch update/upstream-<version> off main and
#                                     merge upstream/main (or ref, e.g.
#                                     upstream/beta/lucent) into it
#   tools/upstream.sh continue        after resolving conflicts: checks, tests, commit
#   tools/upstream.sh finish          after adapting on the branch: tests, then
#                                     main fast-forwards to the branch
#   tools/upstream.sh abort           drop the update, back to main
#
# SKIP_TESTS=1 skips the test run (it runs in a throwaway python:3.12-slim container).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

UPSTREAM_URL="https://github.com/lucya-astralis/gallery.git"
PREFIX="update/upstream-"
# Workflows this fork keeps. Upstream's image.yml pushes to ghcr.io and is left out.
ALLOWED_WORKFLOWS="ci.yml"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[31mx %s\033[0m\n' "$*" >&2; exit 1; }

branch() { git symbolic-ref --short -q HEAD || echo ""; }
merging() { git rev-parse -q --verify MERGE_HEAD >/dev/null; }

setup() {
  git remote get-url upstream >/dev/null 2>&1 || git remote add upstream "$UPSTREAM_URL"
  # Never push to the original by accident.
  git remote set-url --push upstream DISABLED
  # Remember how a conflict was resolved and replay it the next time it comes up.
  git config rerere.enabled true
  git config rerere.autoupdate true
}

fetch() {
  say "Hole upstream ..."
  git fetch -q upstream --prune
}

upstream_version() { # ref
  git show "$1:aperture/brand.py" | sed -n 's/^VERSION = "\(.*\)"/\1/p'
}

# Files this fork changed against the last upstream state it took in.
fork_changed() { git diff --name-only "$1" main | sort; }
fork_deleted() { git diff --name-only --diff-filter=D "$1" main | sort; }

overview() { # ref
  local ref=$1 base new
  base=$(git merge-base main "$ref")
  new=$(git rev-list --count "main..$ref")
  if [ "$new" = 0 ]; then
    say "Nichts Neues: main enthält $ref schon (Version $(upstream_version main))."
    return 1
  fi
  say "$new neue Commits in $ref (Version $(upstream_version main) -> $(upstream_version "$ref")):"
  git log --oneline --no-merges "main..$ref" | sed 's/^/  /'
  echo
  say "Changelog von upstream dazu:"
  git diff "$base" "$ref" -- CHANGELOG.md | sed -n 's/^+\(## .*\)/  \1/p'
  echo
  local up both added
  up=$(git diff --name-only "$base" "$ref" | sort)
  both=$(comm -12 <(echo "$up") <(fork_changed "$base"))
  added=$(git diff --name-only --diff-filter=A "$base" "$ref" | sort)
  if [ -n "$both" ]; then
    say "Diese Dateien hat upstream geändert UND der Fork angepasst (hier genau hinsehen):"
    echo "$both" | sed 's/^/  /'
  else
    say "Keine der geänderten Dateien hat der Fork angepasst: sollte glatt durchgehen."
  fi
  if [ -n "$added" ]; then
    echo
    say "Neue Dateien von upstream:"
    echo "$added" | sed 's/^/  /'
  fi
  echo
  echo "Übernehmen: tools/upstream.sh start${2:+ $ref}"
}

# Things an update must not undo. Each line says what broke if it fails.
fork_checks() {
  local bad=0 f
  check() { if ! eval "$1"; then warn "$2"; bad=1; fi; }
  check 'grep -q "^PRODUCT = \"aspectra.gallery\"" aperture/brand.py' \
    'brand.py: PRODUCT ist nicht mehr "aspectra.gallery".'
  check 'grep -q "^REPO_URL = \"https://github.com/aspectra-world/aspectra.gallery\"" aperture/brand.py' \
    'brand.py: REPO_URL zeigt nicht mehr auf dieses Repo (AGPL §13).'
  check 'grep -q "^UPDATE_URL = \"\"" aperture/brand.py' \
    'brand.py: UPDATE_URL ist wieder gesetzt, die Galerie würde beim Original nachfragen.'
  check 'grep -q "^NAME = \"lucya.systems\"" aperture/brand.py' \
    'brand.py: die Zuschreibung an lucya.systems fehlt.'
  for f in LICENSE NOTICE TRADEMARKS.md FORK.md; do
    check "[ -f $f ]" "$f fehlt."
  done
  for f in aperture/console/static/aspectra.css aperture/gallery/static/f/aspectra-tokens.css \
           aperture/gallery/static/f/aspectra.css aperture/gallery/static/f/starfield.js \
           aperture/gallery/static/logo/saturn.png; do
    check "[ -f $f ]" "$f fehlt (aspectra-Look)."
  done
  check 'grep -q "aspectra.css" aperture/console/templates/index.html' \
    'Admin bindet aspectra.css nicht mehr ein.'
  check 'grep -q "data-starfield" aperture/gallery/templates_facet/base.html' \
    'Galerie: das Sternenfeld ist aus templates_facet/base.html verschwunden.'
  for f in .github/workflows/*.yml; do
    [ -e "$f" ] || continue
    case " $ALLOWED_WORKFLOWS " in *" $(basename "$f") "*) ;; *)
      warn "$f kam von upstream. Löschen (git rm $f) oder in ALLOWED_WORKFLOWS aufnehmen."; bad=1 ;;
    esac
  done
  return $bad
}

run_tests() {
  [ "${SKIP_TESTS:-0}" = 1 ] && { warn "Tests übersprungen (SKIP_TESTS=1)."; return 0; }
  command -v docker >/dev/null && docker info >/dev/null 2>&1 \
    || die "Docker läuft nicht. Starten oder SKIP_TESTS=1 setzen."
  say "Tests laufen (im Wegwerf-Container) ..."
  docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD":/src -w /src python:3.12-slim \
    sh -c 'pip install -q --disable-pip-version-check --root-user-action=ignore -r requirements-dev.txt >/dev/null \
           && python -m pytest -q -p no:warnings -p no:cacheprovider' \
    || die "Tests schlagen fehl. Beheben, dann nochmal."
}

note_in_fork_md() { # version
  local line="- $(date +%F): merged upstream $1."
  grep -qF "$line" FORK.md && return 0
  # Appended to the list under "## Upstream updates", i.e. before the blank
  # lines that lead to the next heading.
  awk -v l="$line" '
    /^$/ { held = held "\n"; next }
    /^## / && sect && !done { print l; done = 1 }
    { printf "%s", held; held = ""; print }
    /^## Upstream updates/ { sect = 1 }
    END { if (sect && !done) print l; printf "%s", held }
  ' FORK.md >FORK.md.tmp && mv FORK.md.tmp FORK.md
  git add FORK.md
}

unmerged() { git diff --name-only --diff-filter=U; }

conclude() {
  # Files this fork removed on purpose stay removed when upstream changed them.
  local base f
  base=$(git merge-base main MERGE_HEAD)
  for f in $(fork_deleted "$base"); do
    if git ls-files -u -- "$f" | grep -q .; then git rm -q -- "$f"; echo "  bleibt gelöscht: $f"; fi
  done
  if [ -n "$(unmerged)" ]; then
    say "Konflikte, bitte von Hand lösen:"
    unmerged | sed 's/^/  /'
    cat <<EOF

So geht's: Datei öffnen, zwischen <<<<<<< (Fork) und >>>>>>> (upstream) den
richtigen Stand herstellen, dann "git add <datei>". Wenn alle gelöst sind:
  tools/upstream.sh continue
Abbrechen: tools/upstream.sh abort
EOF
    exit 1
  fi
  if git grep --cached -l -E '^(<<<<<<<|>>>>>>>) '; then
    die "In den Dateien oben stehen noch Konfliktmarker."
  fi
  fork_checks || die "Die Fork-Prüfung schlägt fehl (siehe oben). Beheben, git add, dann continue."
  run_tests
  local v; v=$(upstream_version MERGE_HEAD)
  note_in_fork_md "$v"
  git commit -q --no-edit -m "Upstream $v übernommen" \
    -m "Merge von $(git rev-parse --short MERGE_HEAD) aus lucya-astralis/gallery."
  say "Übernommen auf $(branch)."
  cat <<EOF

Jetzt in Ruhe ansehen und anpassen (normal committen), z. B.:
  docker compose up --build        Galerie lokal ansehen
  git diff main                    alles, was das Update ändert
Den Eintrag in FORK.md unter "Upstream updates" ergänzen: was übernommen,
was angepasst, was weggelassen wurde.
Fertig: tools/upstream.sh finish
EOF
}

cmd=${1:-check}
case $cmd in
  check)
    setup; fetch
    overview "${2:-upstream/main}" ${2:+x} || true
    ;;
  start)
    ref=${2:-upstream/main}
    [ "$(branch)" = main ] || die "Erst auf main wechseln (gerade: $(branch))."
    [ -z "$(git status --porcelain)" ] || die "Es gibt offene Änderungen. Erst committen oder wegräumen."
    setup; fetch
    overview "$ref" ${2:+x} || exit 0
    b="$PREFIX$(upstream_version "$ref")"
    git rev-parse -q --verify "refs/heads/$b" >/dev/null && die "Branch $b gibt es schon (finish oder abort)."
    git checkout -q -b "$b"
    say "Merge $ref in $b ..."
    git merge --no-ff --no-commit "$ref" >/dev/null 2>&1 || true
    merging || die "Der Merge hat nicht angefangen (git status ansehen)."
    conclude
    ;;
  continue)
    merging || die "Gerade läuft kein Upstream-Merge."
    case $(branch) in "$PREFIX"*) ;; *) die "Nicht auf einem $PREFIX… Branch.";; esac
    conclude
    ;;
  finish)
    b=$(branch)
    case $b in "$PREFIX"*) ;; *) die "Nicht auf einem $PREFIX… Branch.";; esac
    merging && die "Der Merge ist noch offen: erst tools/upstream.sh continue."
    [ -z "$(git status --porcelain)" ] || die "Es gibt offene Änderungen. Erst committen."
    fork_checks || die "Die Fork-Prüfung schlägt fehl (siehe oben)."
    run_tests
    git checkout -q main
    git merge -q --ff-only "$b" || { git checkout -q "$b"; die "main hat sich bewegt. main in $b mergen, dann nochmal finish."; }
    git branch -q -d "$b"
    say "main steht jetzt auf dem Update. Nichts gepusht."
    echo "Hochladen: git push origin main   (danach auf dem Server neu bauen)"
    ;;
  abort)
    b=$(branch)
    case $b in "$PREFIX"*) ;; *) die "Nicht auf einem $PREFIX… Branch.";; esac
    merging && git merge --abort
    [ -z "$(git status --porcelain)" ] || die "Es gibt offene Änderungen auf $b. Erst wegräumen."
    git checkout -q main
    git branch -q -D "$b"
    say "Abgebrochen, zurück auf main. $b ist gelöscht."
    ;;
  *)
    sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
