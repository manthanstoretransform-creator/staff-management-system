docs/steering/design.md

# Design System — StaffTrack

## Layout
- Fixed dark sidebar (left, ~290px wide) + light content area (right, fluid width)
- Content area uses white cards on a light gray (#F8FAFC) page background
- Cards: white background, subtle border/shadow, rounded corners (~8-12px)

## Color Palette
Sidebar (dark theme):
- Background: #0B1220 (near-black navy)
- Active/selected item background: #2563EB (blue) with white text
- Inactive item text: #94A3B8 (slate gray)
- Inactive item hover: slightly lighter navy

Content area (light theme):
- Page background: #F8FAFC
- Card background: #FFFFFF
- Primary text: #0F172A
- Secondary/muted text: #64748B

Accent / brand:
- Primary blue: #2563EB (buttons, active nav, links, progress bars)
- Logo gradient: blue-to-purple circular mark

Status colors:
- Active/working (green dot + badge): #22C55E
- Activity % badge (on screenshots): dark background (#0F172A) pill with green (#16A34A) or white text depending on %
- Warning/pending banner (Offline Sync): background #FEF3C7, icon/accent #F59E0B, text #78350F
- Progress bars: blue fill (#2563EB) on light gray track (#E2E8F0)

Project color dots (per-project identity, left sidebar):
- Website Redesign: blue
- Mobile App Development: purple
- Marketing Campaign: orange
- Client Support: green
- Research & Planning: yellow
- Internal Meetings: cyan
- Design System: red
(Assign a consistent, distinguishable color per project — rotate through a fixed palette rather than random colors, so it stays consistent across sessions.)

## Typography
- Font family: clean sans-serif (system UI stack — Inter or similar is a safe match)
- Headings/section titles (e.g. "My Tasks", "Recent Screenshots"): semi-bold, ~16-18px
- Body/table text: regular, ~14px
- Numeric/time values (e.g. "05:42:18", tracked time column): tabular/monospace-leaning numerals, medium weight
- Muted labels (e.g. "PROJECTS", "TASK", "PROJECT" column headers): uppercase, small (~11-12px), letter-spaced, #94A3B8

## Components
- **Buttons:** primary = solid blue, white text, rounded (~6px); secondary/outline = white bg, gray border; success action (Start Timer) = solid green
- **Badges/pills:** rounded-full, small padding, used for counts (blue circle with white number) and activity % (dark pill, green/white text)
- **Progress bars:** thin, rounded, blue fill over light gray track, used both for total time-today context and per-task completion
- **Cards:** consistent padding (~20-24px), white background, subtle shadow, rounded corners
- **Empty states:** centered icon illustration + heading + short description + single primary CTA button (see "No tasks yet" state)
- **Data table (My Tasks):** columns = Task (with subtask/tag label beneath), Project (color dot + name), Budget, Tracked Time (value + % + progress bar), Action (Start Timer button + overflow menu)
- **Screenshot grid cards:** thumbnail image, timestamp badge (top-left) + activity % badge (top-right) overlaid on image, app/site icon + domain link + label beneath

## Interaction Notes
- Sidebar item shows a live running timer value beneath the project name for whichever project is active
- Empty and populated states of the same panel should share the exact same container/heading treatment, just swap the body content