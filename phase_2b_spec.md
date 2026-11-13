# Phase 2B Spec: Onboarding UI

> **Owner:** UI Agent (`.claudebots/ui_ux_agent.md`)
> **Status:** Approved, not started. **Depends on:** Phase 2A (complete: `accounts/services.py`, `User.is_onboarded`, tier range rule).
> **Iteration note:** the visual direction is a starting point. It may be iterated or pivoted after real use, so every colour, font and size comes from the theme tokens below, never from hard-coded values in templates.

---

## 1. Scope

**In scope:** sign up, log in, log out, password reset, one-step profile onboarding, profile view with inline edit, the base layout, and a home page.

**Out of scope:**
- **Not yet modelled:** subbing availability, subbing leagues and organizer registrations.
- **Needs a token model:** guest magic links. Converting a guest to a full account is a dedicated magic-link workflow in a future sprint.
- **Later sprints:** notification preferences, the league finder and open-spot results.

## 2. Decisions on record

| Topic | Decision |
|---|---|
| Sign-up with an email already used by a guest | Show the standard "An account with this email already exists" error. No conversion yet. |
| Password reset | Included, using Django's built-in views. Emails print to the console in development. |
| Packages | `django-htmx` and `django-tailwind-cli` (standalone Tailwind CLI, no Node). Pinned htmx 2.x and Alpine.js 3.x are copied into `static/vendor/`. |
| Raw CSS exception | The only CSS allowed is the `@theme { … }` block (plus `@import "tailwindcss";`) in the Tailwind input file. Everything else uses Tailwind utility classes. |
| Theme | Light theme only in Phase 2B. Dark mode comes later, built on the same tokens. |

---

## 3. Visual direction

**Sources:**
- **PowerLeague** for structure: what to find, and how to get there fast.
- **Reflexion** for spacing.
- **Mas Oyama** for hierarchy and restraint.

Colours and imagery from all three are deliberately not copied.

**Brief:**
- **Audience:** adults in recreational volleyball leagues, mostly on phones and often deciding the same day.
- **Main job:** fill a spot, or find a game to sub in, within a minute.

### 3.1 Principles
1. **Time and status are the loudest things on screen.** Dates and times use the condensed numeral style, and status uses the highlight colour.
2. **Bold choices go in one place:** the serif heading against the light sans body, plus condensed times. Everything else stays quiet.
3. **Lists, not cards.** Repeated items such as spots, games and profile fields are rows separated by hairlines. Use a panel only for something that really is a separate object, such as a form or the home finder.
4. **One idea per section,** with generous space between sections and tight space inside them.
5. **No decorative motion.** Motion only responds to an action: an HTMX swap settling, a toast appearing, a section expanding.
6. **No imagery.** Avatars show initials until profile photos exist.

### 3.2 Colour tokens

| Token | Hex | Role | Contrast |
|---|---|---|---|
| `paper` | `#FAF7F2` | Page background | — |
| `surface` | `#FFFFFF` | Inputs and panels | — |
| `ink` | `#23262B` | Main text | 14.2:1 on paper |
| `slate` | `#5B6472` | Secondary text, meta lines, help text | 5.6:1 on paper |
| `court` | `#1E6B52` | Primary buttons, links, focus ring, selected state | 6.4:1 white on court, 6.0:1 as text |
| `court-dark` | `#16503D` | Hover and pressed for `court` | 9.3:1 white on it |
| `ball` | `#F5C518` | Highlight only: "Open", urgent, tonight. Always with `ink` text, never as text colour. | 9.3:1 ink on ball |
| `danger` | `#B42318` | Form errors and destructive actions | 6.2:1 on paper |
| `hairline` | `#E4DED3` | Dividers between rows. Decorative only. | — |
| `field` | `#8A8478` | Input borders | 3.5:1 on paper (non-text minimum is 3:1) |

### 3.3 Type

| Role | Family | Settings |
|---|---|---|
| Headings | **Source Serif 4** | Weight 600–700, slightly tight letter spacing at display sizes |
| Body and controls | **Archivo** | Weight 300 (light) for long text, 400 for UI, 500–600 for buttons and labels |
| Dates, times, counts | **Archivo**, condensed width (about 75–80) | Weight 600, numbers that line up in columns (`tabular-nums`) |

- Fonts are self-hosted as WOFF2 in `static/vendor/fonts/`. Both are SIL Open Font License.
- **Scale** (ratios follow Mas Oyama): `display` 52px / 1.1 · `h1` 36px / 1.2 · `h2` 22px / 1.3 · `base` 16px / 1.55 · `meta` 13px / 1.4. These are defined in `@theme`.
- **Line length:** body text stays at or below about 70 characters (`max-w-prose`).
- **Casing:** sentence case everywhere. No all-caps labels, no tracked-out eyebrow labels above headings, and no middle-dot meta strings. Use line breaks or chips instead.

### 3.4 Spacing, shape and layout

| Element | Value (from Reflexion) | Tailwind |
|---|---|---|
| Content width | About 1150px | `max-w-6xl mx-auto px-5` |
| Section padding (top and bottom) | 56–80px | `py-14 md:py-20` |
| Intro width / gap below intro | 640–720px / 48px | `max-w-2xl` / parent `flex flex-col gap-12` |
| Rows in a list | Hairline between rows, 16–20px padding | `divide-y divide-hairline`, `py-4 md:py-5` |
| Panel (forms, finder) | 28–32px padding | `p-7 md:p-8` |
| Columns | One column on mobile; 2 at `md`; text-and-panel split `lg:grid-cols-[1.4fr_1fr]` with `gap-10` | — |

**Corner radius encodes what kind of element it is:**
- Panels and list rows: 0–2px (`rounded-none` / `rounded-xs`).
- Inputs, selects, option tiles and option lists: 8px (`rounded-lg`).
- Buttons and chips: fully rounded (`rounded-full`).

**Inputs** (`core.forms.INPUT_CLASSES`, applied by `TailwindFormMixin`):
- 48px tall (`min-h-12`), `px-4`, `field` border that darkens to `ink` on hover.
- Focus: `court` border (the 3:1 indicator) plus a soft `ring-4 ring-court/15` glow; `outline-hidden` keeps an outline in high-contrast mode.
- Errors: `danger` border and a `danger` glow when focused. Disabled: `paper` background, `slate` text.
- Selects use a drawn chevron instead of the browser arrow; number inputs hide the up/down arrows.

**Alignment:** left-aligned throughout. Only the empty-state message is centred.

**Building rules** (from `.claudebots/ui_ux_agent.md`):
- **Mobile first.** Base classes target phones, and `md:` / `lg:` add the wider layouts.
- **Spacing between siblings** uses `flex`/`grid` with `gap-*`, not margins on the children.
- **Tailwind 4 utilities only.** No deprecated v3 names: for example `shrink-0`, not `flex-shrink-0`, and `rounded-xs` for 2px.

**Quality floor:**
- Responsive down to 360px.
- Visible keyboard focus (`focus-visible:ring-2 ring-court ring-offset-2 ring-offset-paper`).
- Respects reduced motion (`motion-reduce:`).
- Hit targets at least 44px tall.

### 3.5 The repeated row (reference, used later by the finder)

```
Thu 14 Nov  7:40 pm   Tuesday Coed B                    [Open]
                      Riverside Rec Centre, Court 3
                      Middle   Needs a woman   Intermediate (B)
──────────────────────────────────────────────────────────────── hairline
```
- **Left column:** condensed date and time.
- **League name:** serif, `h2`.
- **Venue:** Archivo light, `slate`.
- **Requirements:** chips.
- **Status:** a `ball` chip for "Open", outlined for "Tentative", `slate` text for "Filled".

Phase 2B uses this pattern for the profile's field rows.

### 3.6 Copy
- **Buttons say exactly what happens:** "Create account", "Log in", "Save profile", "Send reset link", "Set new password".
- **Use the same word through a flow.** Clicking "Save profile" shows a toast that says "Profile saved".
- **Errors say what went wrong and how to fix it.** They don't apologise.
- **Empty states invite an action.**
- **Use the people's own vocabulary:** "sub", "spot", "league night", "tier".

---

## 4. Setup (settings and tooling)

- **`requirements.txt`:** add `django-htmx` and `django-tailwind-cli`, pinned.
- **`INSTALLED_APPS`:** add `django_htmx` and `django_tailwind_cli`.
- **`MIDDLEWARE`:** add `django_htmx.middleware.HtmxMiddleware`.
- **Templates and static files:** `TEMPLATES["DIRS"] = [BASE_DIR / "templates"]`, `STATICFILES_DIRS = [BASE_DIR / "static"]`.
- **Login and logout:** set `LOGIN_URL = "accounts:login"`, `LOGIN_REDIRECT_URL = "home"`, `LOGOUT_REDIRECT_URL = "home"`.
- **Password similarity:** set `UserAttributeSimilarityValidator` `OPTIONS = {"user_attributes": ("email", "display_name")}`.
- **Tailwind input file:** contains only `@import "tailwindcss";`, `@source` lines if needed, and the `@theme` block holding the tokens from section 3. Configure its path through `django-tailwind-cli` settings.
- **`static/vendor/`:** `htmx.min.js`, `alpine.min.js` and `fonts/*.woff2`, with each version noted in `static/vendor/VERSIONS.md`.
- **CSRF for HTMX:** `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>`.
- **Font loading:** `@font-face` rules for the self-hosted fonts sit in the same Tailwind input file, under the `@theme` exception.

## 5. Templates and fragments

| Template | Purpose |
|---|---|
| `templates/base.html` | Page skeleton on `paper`. Loads CSS, htmx and Alpine. Includes the nav and messages, and a `main` block in the standard container. |
| `templates/partials/_nav.html` | Serif "SubSet" wordmark. **Signed out:** "Log in" link and a "Sign up" button. **Signed in:** "Profile" and a "Log out" POST form. The finder, teams and requests links arrive with their features. Alpine toggles the mobile menu (`x-data="{ open: false }"`). |
| `templates/partials/_messages.html` | `<div id="messages">` holding toasts. Alpine closes each one after 4 seconds (`x-data="{ show: true }" x-init="setTimeout(() => show = false, 4000)" x-show="show"`). Also the target for out-of-band swaps. |
| `templates/partials/_field.html` | Label (Archivo 500), input (`surface`, `field` border, 2px radius), help text (`meta`, `slate`), errors (`meta`, `danger`), with `aria-describedby` wiring. |
| `templates/partials/_form_errors.html` | Errors that belong to the whole form (for example the tier range rule), in a `danger` panel at the top of the form. |
| `templates/home.html` (`core`) | **Signed out:** a hero split with the headline and short intro on the left and a panel on the right. The panel has an Alpine toggle between "I need a sub" and "I want to sub" with matching copy, and its button goes to sign-up until the finder exists. Below it: "How it works" in three numbered steps (a real sequence). **Signed in but not onboarded:** redirect to onboarding. **Onboarded:** a placeholder dashboard with an empty state ("No games yet. When your league opens spots, they'll show up here."). |
| `accounts/signup.html` + `partials/_signup_form.html` | Narrow single column (`max-w-md`), serif `h1`, then the form. |
| `accounts/login.html` + `partials/_login_form.html` | Same layout as sign-up, with a "Forgot your password?" link. |
| `accounts/onboarding.html` + `partials/_onboarding_form.html` | One page in sections separated by hairlines: **About you** (display name, gender), **Your level** (skill tier as five radio rows; the selected row gets a `court` left border), **Range you'll sub** (tier flex), **Getting there** (travel radius, optional phone). |
| `accounts/profile.html` | Includes the profile card. |
| `accounts/partials/_profile_card.html` | `id="profile-card"`. A label-and-value list with hairline rows, and an "Edit profile" button. |
| `accounts/partials/_profile_form.html` | The inline edit form that replaces the card in place. |
| `registration/password_reset_form.html`, `_done`, `_confirm`, `_complete` | Same layout as sign-up. Full pages with no HTMX. |
| `registration/password_reset_email.txt`, `password_reset_subject.txt` | Plain-text email. |

## 6. HTMX and Alpine interactions

**Sign up, log in, onboarding (one pattern for all three):**
```html
<form method="post" action="{% url 'accounts:signup' %}"
      hx-post="{% url 'accounts:signup' %}"
      hx-target="this" hx-swap="outerHTML"
      hx-disabled-elt="find button[type=submit]"
      hx-indicator="#signup-spinner">
```
- **Invalid:** return the form fragment with status **200**. htmx 2 doesn't swap 4xx responses by default.
- **Valid:** return a client redirect (`HX-Redirect`) using `django_htmx.http.HttpResponseClientRedirect`, so the next page loads in full.
- **Not an HTMX request:** return the full page or a 302. Every form also has `method` and `action`, so it works without JavaScript.

**Profile inline edit:**

| Element | Attributes |
|---|---|
| "Edit profile" | `hx-get="{% url 'accounts:profile_edit' %}" hx-target="#profile-card" hx-swap="outerHTML"` |
| Edit form | `hx-post="{% url 'accounts:profile_edit' %}" hx-target="this" hx-swap="outerHTML"`. On success it returns `_profile_card.html` plus `<div id="messages" hx-swap-oob="true">` carrying a "Profile saved" toast. |
| "Cancel" | `hx-get="{% url 'accounts:profile_card' %}" hx-target="#profile-card" hx-swap="outerHTML"` |

**Alpine-only:**
- **Tier range preview:** `x-data="{ tier, down, up }"` reads the current form values. It shows a live sentence ("You'll sub from Novice (C) to Advanced (BB)"), and the flex inputs limit themselves with `:max="tier - 1"` and `:max="5 - tier"`. The server still validates.
- **Password field:** a show/hide toggle and a live "passwords match" hint.

**Rejected on purpose:** a live "is this email taken?" check. Anyone could use it to discover which emails have accounts, and there's no rate limiting yet.

## 7. Views, URLs and validation

Views are thin. They call `accounts/services.py` (`register_full_account`, `complete_onboarding`). A small `HtmxFormMixin` in `core/htmx.py` chooses between fragment and full page, and between `HX-Redirect` and a 302.

| URL name | Methods | Access |
|---|---|---|
| `home` | GET | Anyone |
| `accounts:signup` | GET, POST | Signed out only. Signed-in users are redirected. |
| `accounts:login` | GET, POST | Signed out only. Built on `LoginView`, which checks `next` with `url_has_allowed_host_and_scheme`. |
| `accounts:logout` | POST | Built on `LogoutView` |
| `accounts:onboarding` | GET, POST | Logged in and a full account |
| `accounts:profile`, `accounts:profile_card` | GET | Logged in |
| `accounts:profile_edit` | GET, POST | Logged in |
| `accounts:password_reset` (and the done, confirm and complete pages) | GET, POST | Django built-ins. They skip users with an unusable password, so guests never get reset emails. The email lookup ignores case. |

**`SignupForm`** (built on `BaseUserCreationForm`: email, display name, two password fields)
- **Email:** required and must look valid. It's trimmed and lowercased, and a case-insensitive duplicate is an error, including an email held by a guest.
- **Display name:** required, trimmed, 2–100 characters.
- **Passwords:** both fields match and pass all four password validators. Similarity is checked against email and display name.
- Saves through `register_full_account`.

**`EmailAuthenticationForm`** (built on `AuthenticationForm`)
- The field is labelled "Email" and the lookup ignores case (already in place from Phase 1).
- One generic error covers a wrong email, a wrong password, an inactive account or a guest, so the form doesn't reveal which accounts exist.

**`OnboardingForm` / `ProfileForm`** (model form)
- **Fields:** display name, phone, gender, skill tier, both flex fields, travel radius. All three tier fields must be in the same form: see the Validation convention in CLAUDE.md.
- **Required during onboarding:** gender ("Prefer not to say" counts) and skill tier.
- **Tier range rule:** comes from `User.clean()` and appears as field errors. The form doesn't repeat it.
- **Travel radius:** optional, 1–250 km.
- **Phone:** optional and trimmed. Allowed characters are digits, spaces and `+ - ( )`, with 7–15 digits.
- Saves through `complete_onboarding`.

**Security:**
- CSRF on every POST.
- Each view accepts only the methods listed above.
- Logging in starts a fresh session (Django's `login()` does this).
- **Known gap:** there's no rate limiting on failed logins or reset emails yet (for example, `django-axes`). This is planned for a later sprint.

## 8. Tests (UI Agent)

- **GET** returns the full page with the base layout.
- **HTMX POST with errors** returns 200 with only the fragment (no `<html>`) and the error text present.
- **Valid HTMX POST** returns the `HX-Redirect` header to the right destination.
- **Valid normal POST** returns a 302.
- **Signed-in-only views** redirect visitors who aren't logged in to log in with `next`. An unsafe `next` is ignored.
- **Signed-in users** are redirected away from sign-up and log in.
- **Users who haven't finished onboarding** are sent to onboarding from home.
- **Profile edit** responses include the `#messages` out-of-band block.
- **Password reset:**
  - It sends one console email for a full account with a mixed-case email.
  - It sends none for a guest or an unknown email.
  - The page looks the same in every case.

## 9. Definition of done

- `python manage.py check`, `makemigrations --check --dry-run`, `pytest`, `black . --check` and `flake8` all pass.
- The Tailwind build produces the CSS file, and no template uses a hex value or arbitrary colour.
- Spot-check at 360px and 1280px: no horizontal scroll, keyboard focus visible on every interactive element.
