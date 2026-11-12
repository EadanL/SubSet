# Volleyball Sub Finder

A web app that helps players in recreational adult volleyball leagues find substitutes when they can't make a game, and lets players pick up sub spots in leagues they're eligible for.

> **Status:** MVP in progress. Phase 1 (project foundation and custom user model) is complete; see [Build Progress](#build-progress). This document captures the agreed feature set and design decisions.

---

## Table of Contents

1. [Core Concept](#core-concept)
2. [Data Model Overview](#data-model-overview)
3. [Users & Profiles](#users--profiles)
4. [Leagues, Organizers & Eligibility](#leagues-organizers--eligibility)
5. [Teams, Rosters & Roles](#teams-rosters--roles)
6. [Games & Schedules](#games--schedules)
7. [Absences & Sub Slots](#absences--sub-slots)
8. [Sub Requests & Responses](#sub-requests--responses)
9. [Matching & Alerts](#matching--alerts)
10. [On-Call Lists](#on-call-lists)
11. [Last-Minute Mode](#last-minute-mode)
12. [Guest Accounts & Shareable Links](#guest-accounts--shareable-links)
13. [Double-Booking Protection](#double-booking-protection)
14. [Ratings, Reliability & Attendance](#ratings-reliability--attendance)
15. [Safety: Reporting & Blocking](#safety-reporting--blocking)
16. [Privacy & Anonymous Rosters](#privacy--anonymous-rosters)
17. [Calendar Sync](#calendar-sync)
18. [Roadmap](#roadmap)
19. [Build Progress](#build-progress)
20. [Launch Strategy & Open Questions](#launch-strategy--open-questions)

---

## Core Concept

- Players sign in and set up a profile with the leagues they play in, the leagues they're willing to sub for, and the days/positions they're available.
- Teams are created inside the app, and players are invited to them. League details auto-populate from team membership so nobody enters the same information twice.
- When a player can't make a game, they mark themselves absent and request a sub. Matching players are alerted, respond, and the team picks who to bring.
- Players without accounts can still claim a spot through a shareable link as a guest.

---

## Data Model Overview

Core entities:

| Entity | Purpose |
|---|---|
| **User** | Account holder (full account or guest) |
| **Organizer** | Runs one or more leagues; holds player registrations |
| **League** | Location, night, time, tier, format, gender rules, sub-registration flag |
| **Team** | Belongs to a league; has captain and co-captain |
| **Roster membership** | Links users (or placeholders) to teams, with position(s) |
| **Game** | A scheduled match with start and end time |
| **Absence** | A specific player being out for a specific game |
| **Sub slot** | One open spot, tied to one absence |
| **Response** | A potential sub's accept / decline / tentative on a slot |
| **Rating** | Blind, simultaneous feedback between sub and team |
| **Attendance record** | Captain-confirmed show / no-show (disputable) |

Every entity uses a UUID primary key. The full schema lives in `db_erd.mermaid`.

---

## Users & Profiles

- Sign-in with a full account using **email and password**. Emails are case-insensitive (`Jordan@Example.com` and `jordan@example.com` are the same account). Guest accounts are covered below.
- **Playing profile:** leagues played in, teams, positions, self-reported skill tier, gender.
- **Skill tier scale** (shared by players and leagues): 1 Beginner · 2 Novice (C) · 3 Intermediate (B) · 4 Advanced (BB) · 5 Elite (A/AA).
- **Gender options:** Woman, Man, Non-binary, Prefer not to say.
- **Onboarding:** a new full account is onboarded once it has a skill tier and a gender ("Prefer not to say" counts). Display name, phone, tier range and travel radius are optional.
- **Subbing profile:**
  - Days of the week open to subbing
  - Positions willing to sub
  - Leagues they can or want to sub for
  - Skill tier flexibility (a range, e.g. willing to sub one tier down or a stretch up), stored as a number of tiers down and up from the player's own tier. The range must stay on the 1–5 scale (a Beginner can't go down, an Elite can't go up), and a range needs a skill tier set first.
  - Travel radius
  - **Organizer registrations** (which organizers they are registered with)
- Notification preferences, including quiet hours and opt-in to urgent alerts.

---

## Leagues, Organizers & Eligibility

### Entry
- League data is **manually entered** by users, with moderation to limit duplicates.
- While filling out a league entry, the app **suggests existing leagues** on the same night/location, which reduces duplicates and helps people discover leagues they missed.
- Required fields include location, night and times, game duration (and match slots for multi-match nights), tier, format (4s, 6s, co-ed, reverse co-ed, etc.), and **gender/format rules** (e.g. minimum number of women on court).
- Only players whose gender is **Woman** count toward a women minimum. Every other value, including unset, does not.

### Organizer → League
- Registration requirements live on the **organizer/league**, not the player.
- Each league has a flag such as **"subs must be registered."**
  - If set, this is a **hard, blocking eligibility filter**. Players not registered with that organizer cannot be matched or respond (guests are blocked with an explanation).
  - If not set (many leagues allow outside subs), anyone otherwise eligible can sub.
- Player registrations are stored at the **organizer level**, so registering with an organizer makes a player eligible for all of that organizer's restricted leagues at once.
- Registration is self-declared; captains can flag incorrect claims.

---

## Teams, Rosters & Roles

- Users **create teams** and invite players. Rostered players inherit league details automatically.
- **Roles:**
  - **Captain** and **Co-captain** share the same admin powers, so the team keeps running if the captain is absent.
  - **Ownership transfer** lets a team survive a captain leaving.
- **Placeholder roster spots** let captains add players who haven't signed up, so a team isn't blocked.
- Any rostered player can submit a sub request (subject to the absence-based cap below).

---

## Games & Schedules

- Teams have a **generated schedule** (imported, pasted in, or created by the captain), with a **"create game manually"** fallback.
- Schedules make absences and overlap detection reliable.
- Each game has a start and end time, derived from league game duration and match slots.

---

## Absences & Sub Slots

Each sub slot belongs to **one specific absent player for one specific game**.

- **Cap rule:** one open sub slot per absent player per game.
  - One middle absent → a second middle request from a teammate is blocked ("Jordan's spot already has a request").
  - Two middles absent → two requests are allowed.
- **Position** is a field on the slot. It defaults to the absent player's primary position but is editable (e.g. an outside who can shuffle over is acceptable).
- **Gender/format requirements** derive from the absent player. If a woman is out in a co-ed league with a minimum, the slot is flagged as needing a woman. Subs see only the requirement, not who is absent.
- **Who can mark someone absent:**
  - The player themselves via an **"I can't make it"** button, which prompts "request a sub?"
  - Captains/co-captains can mark a teammate absent; the player is notified and can **dispute** it.
  - Other teammates can nudge but not mark.
- **Absent player returns:** the slot cancels and any accepted sub is notified.
- **Multi-game absences:** "out for 3 weeks" creates three absences, each with its own slot.

---

## Sub Requests & Responses

- A request is **one request containing multiple date slots**, each with its own status: **open**, **tentative**, or **filled**.
- Requests can be **recurring** (specify how many occurrences are needed).
- **Partial fills:** a sub can accept only some dates. Once accepted, the request auto-updates so only uncovered dates remain open. Different subs can cover different dates. Teams see a "3 of 5 dates covered" view.
- **Responses:** accept, decline, or mark tentative.
- **Direct requests:** browse available players and request someone specifically (for yourself or a teammate).
- **Open postings:** post a general request; available players respond, and the team chooses.
- **Waitlist:** when multiple subs respond, the team picks one and keeps the others as backups.
- **Cancellation flow:** if a confirmed sub drops out, the affected slot reopens automatically and the team is re-notified.
- **Messaging:** simple per-request chat, or easy sharing of details (court, time, jersey color, parking).

---

## Matching & Alerts

Auto-matching has two stages.

**Hard filters** (must pass):
- Availability
- League eligibility (including organizer registration requirement)
- Gender/format requirements
- Schedule conflicts, including already being rostered in that league that night

**Soft scoring** (ranks the remaining candidates):
- Skill proximity (weighted by the player's tier flexibility range)
- Position fit
- Distance and travel radius
- Reliability score
- Past history with the team

Skill is self-reported, so ratings gradually calibrate it. Matching players are notified via push/email.

---

## On-Call Lists

- Teams keep a **backup ("on call") list** of preferred subs, since teams often prefer playing with familiar people.
- Teams can notify **all on-call players** at once. Responses are collected and the captain picks.
- **Optional first-dibs timer:** if enabled, on-call players get first access, and after the timer (e.g. 12 hours) the request opens to the public.
- On-call entries can be **guest contacts** (friends not yet on the app).
- Subs can mark teams they'll always say yes to.
- The timer is shortened or skipped inside the last-minute window.

---

## Last-Minute Mode

- Available only for requests **within 12 hours** of game time.
- Blasts to matching available players, bypassing the normal flow.
- **Rate limits and quiet hours** prevent notification burnout.
- Players can **opt in to urgent alerts** that bypass quiet hours; everything else is queued.

---

## Guest Accounts & Shareable Links

- Captains can generate a **shareable request link** to drop in a group chat or Facebook group.
- Anyone can claim a spot as a **guest** without creating an account:
  - Provides a name and a phone or email (at least one is required; guests have no password)
  - Receives a **magic link** to manage or cancel their spot
  - Is clearly labeled **"guest, no history"** to the captain
  - Is **blocked from leagues requiring registration**, with an explanation
- After the game, guests are prompted to **convert to a full account**, with their rating attached so they see the benefit.
- Conversion happens only through a **dedicated magic-link workflow** (future sprint). Until then, signing up normally with an email a guest already used shows the standard "an account with this email already exists" error.

---

## Double-Booking Protection

- A player cannot sub for two teams at overlapping times, or sub while playing for their own team (including their own team's game in the same league).
- **Overlap tolerance:** overlaps up to **20 minutes** are allowed with a prominent warning, shown to both the sub and the captain; the sub must acknowledge before confirming. Overlaps **over 20 minutes are a hard block**.
- Accepting a slot automatically marks the sub unavailable for overlapping times.

---

## Ratings, Reliability & Attendance

- **Post-game ratings go both ways:** the team rates the sub, and the **sub rates the team**.
- Ratings are **blind and simultaneous**: neither side sees the other's rating until both submit or a time window closes.
- Keep it lightweight: thumbs up/down ("would sub/play with again") plus an optional skill-accuracy check.
- Aggregates are shown only after a **minimum number of ratings**.
- **Reliability score** tracks show-up rate and last-minute cancellations.
- **Attendance source of truth:** the captain confirms "showed up / no-show"; the sub can dispute.

---

## Safety: Reporting & Blocking

- Players can **report** and **block** other users.
- Blocked users are excluded from matching and requests between the two parties.

---

## Privacy & Anonymous Rosters

- **Teammates** see each other fully.
- The **public** sees only team name and league.
- **Interested subs** can request a **roster reveal** showing first names, skill levels, and gender split.
  - Captain approves the reveal before confirmation; reveal is automatic after the sub is confirmed.

---

## Calendar Sync

- Google / Apple calendar sync for confirmed sub games and team schedules.
- Optionally import availability from calendars.
- A comfort feature, not part of the first release.

---

## Roadmap

### MVP
- Accounts, profiles, availability
- Organizers, leagues (with registration flag), teams, rosters, captain/co-captain
- Schedules/games with manual fallback
- Absences and sub slots (with the one-slot-per-absent-player cap)
- Requests with multiple date slots, accept / decline / tentative, partial fills
- Open postings and direct requests
- Hard-filter matching with basic scoring
- Push/email notifications
- Double-booking protection with 20-minute overlap warning
- Shareable links with guest accounts
- Simple feedback system

### Next layer
- Blind ratings and reliability scores, attendance confirmation
- On-call lists with first-dibs timer
- Last-minute mode with rate limits and quiet hours
- Reporting and blocking
- Waitlist and per-request messaging
- League entry suggestions and moderation

### Later
- Roster reveal flow
- Calendar sync
- Schedule import from league platforms
- Referral / invite-a-friend perks
- **Tournament teams** (a separate section from league nights, for forming teams for tournaments; to be designed after the core features)

### Possible monetization (not committed)
- Free for players; paid tier for captains/leagues (advanced matching, team management)
- League/organizer partnerships
- Local sponsorships (gear shops, bars)

---

## Build Progress

### Phase 1: Foundation (complete)
- **`core` app:** abstract base models (UUID primary key, created/updated timestamps) and shared choices (skill tier scale, gender). It creates no tables.
- **`accounts` app:** custom User model with email login, used as Django's `AUTH_USER_MODEL`.
  - Full accounts require an email; guest accounts require an email or a phone and have no password.
  - The database enforces case-insensitive unique emails, valid account types, and non-negative tier flex and travel radius.
  - Django Admin manages users.
- **Deferred User fields:** `home_location` (waits for PostGIS) and `reliability_score` (computed by the feedback app).
- **Local development:** PostgreSQL runs in Docker on host port **5433**, to avoid clashing with a locally installed Postgres on 5432.

### Phase 2A: Onboarding backend (complete)
- **Tier range rule:** the model gives field-specific errors (e.g. "From Novice (C) you can go at most 1 tier(s) down"), and a database check constraint backs it up.
- **`is_onboarded`:** true for a full account with skill tier and gender set. It's computed, so there's no extra column.
- **`accounts/services.py`:**
  - `register_full_account` validates email, display name and password strength.
  - `complete_onboarding` requires gender and skill tier, and rejects guests.
- **Email handling:** emails are trimmed and lowercased before validation, and a full account with no email gets a clear field error.

### Phase 2B: Onboarding UI (approved, not started)
- **Full spec:** [`phase_2b_spec.md`](phase_2b_spec.md).
- **Pages:** sign up, log in, log out, password reset, one-step profile onboarding, and profile view with inline edit.
- **Tooling:** `django-htmx`, Tailwind through `django-tailwind-cli` (no Node), and pinned htmx and Alpine.js copied into `static/vendor/`.
- **Forms:** submit with HTMX and re-render errors in place. They also work without JavaScript.
- **Visual direction:**
  - Warm paper background, charcoal text, court green (`#1E6B52`) as the primary colour, and ball yellow only for "Open" and urgent.
  - Source Serif 4 headings over light Archivo body text, with condensed numbers for dates and times.
  - Hairline lists instead of cards, and mostly square corners.
  - It draws on PowerLeague (structure), Reflexion (spacing) and Mas Oyama (hierarchy). The direction may be iterated after real use, so templates use theme tokens only.

---

## Launch Strategy & Open Questions

- **Cold start:** launch in one city, facility, or league first to build density before going broad.
- **Liability:** decide whether a waiver or just a disclaimer is needed, and how to handle leagues that require organizer approval or rating caps for subs.
- **Open decision:** this README assumes games come from **generated schedules** with a manual fallback (the recommended default). Confirm before finalizing the data model.
- **Next step:** design the notification logic and permissions. The data model is drafted in `db_erd.mermaid` and is implemented app by app (see [Build Progress](#build-progress)).
