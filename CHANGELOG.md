# Changelog

## 1.4.0 - 2026-11-01

### Added
- A new first screen: a scrolling collage of product photos behind the logo, with an Explore button.
- A sign-in page (`/enter`): one form for everyone (admin accounts go to the admin app, shoppers to the app),
  sign-up, and "Enter without signing in" to the original app.
- The original app's Home, History, Wishlist, About and FAQ are one scrolling page; the side menu is floating
  icons that scroll between the parts, and Settings is in the top bar.

### Changed
- Home is tidier: a centred welcome on the page texture, one wider link box, soft panels for each part.
- The original app's own campus-photo splash screen is removed.

## 1.3.0 - 2026-10-31

### Changed
- New brand colours: deep navy blue (main buttons, links, switches, scan progress, focus ring) and burnt mustard
  yellow (logo check mark; decoration only, never a verdict, count or warning).
- Dark mode uses a brighter navy so it passes the colour-blind distance check against the "no warnings" teal.
- `npm run check:colors` passes for light and dark.

### Earlier in this app
- Separate admin app replacing the DTI view (402956d).
- DTI view: filters, printable reports and charts (e29c748).
- Public deployment layer, browser extension and UI/UX pass (04ee1a0).
