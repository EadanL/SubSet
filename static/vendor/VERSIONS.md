# Vendored front-end assets

Pinned copies served from `static/vendor/`. To upgrade, download the new version from the same source, replace the file, and update this table.

| File | Package | Version | Source |
|---|---|---|---|
| `htmx.min.js` | htmx.org | 2.0.11 | `https://cdn.jsdelivr.net/npm/htmx.org@2.0.11/dist/htmx.min.js` |
| `alpine.min.js` | alpinejs | 3.17.5 | `https://cdn.jsdelivr.net/npm/alpinejs@3.17.5/dist/cdn.min.js` |
| `fonts/archivo-latin-wdth-normal.woff2` | @fontsource-variable/archivo | 5.3.0 | Latin subset, `wght` 100–900 and `wdth` 62–125% axes |
| `fonts/source-serif-4-latin-wght-normal.woff2` | @fontsource-variable/source-serif-4 | 5.3.1 | Latin subset, `wght` 200–900 axis |

Both fonts are licensed under the SIL Open Font License 1.1 (`fonts/OFL-*.txt`).

The Tailwind CLI itself is not vendored. `django-tailwind-cli` downloads the version pinned in `TAILWIND_CLI_VERSION` (settings) into `.django_tailwind_cli/`.
