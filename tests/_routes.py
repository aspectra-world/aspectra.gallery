# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright © 2026 lucya.systems — https://lucya.systems
"""Every route an app dispatches to, included routers flattened.

Since FastAPI 0.16x `include_router` leaves ONE entry in `app.routes` that
wraps the router (`_IncludedRouter`), instead of copying its routes in. A
test that walked `app.routes` then saw only the routes declared on the app
itself -- and "no console route is on the public app" passed for the wrong
reason. Aperture includes its routers without a prefix, so the paths are the
router's own.
"""


def all_routes(app_or_routes):
    routes = getattr(app_or_routes, "routes", app_or_routes)
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from all_routes(inner.routes)
        else:
            yield route
