# SCALA TUI Design System

## 1. Atmosphere & Identity

SCALA is a focused security operations console for terminal users. It should feel like a clear command surface: high contrast, compact, and calm while agents are running. The signature is a bright blue frame and status language over a black terminal background.

## 2. Color

### Palette

| Role | Token | Light | Dark | Usage |
|------|-------|-------|------|-------|
| Surface/primary | --surface-primary | terminal default | terminal black | Terminal background |
| Text/primary | --text-primary | bright white | bright white | Main content |
| Text/secondary | --text-secondary | bright cyan | bright cyan | Hints and secondary metadata |
| Border/default | --border-default | bright blue | bright blue | Shared frame and dividers |
| Accent/primary | --accent-primary | bright cyan | bright cyan | Brand, active cursor, links |
| Accent/strong | --accent-strong | bright blue | bright blue | Running state and spinner |
| Status/success | --status-success | bright green | bright green | Completion and confirmations |
| Status/warning | --status-warning | bright yellow | bright yellow | Idle, waiting, pending restart |
| Status/error | --status-error | bright red | bright red | Errors and invalid input |

### Rules

- Prefer bright blue and cyan accents on the black terminal background.
- Keep status colors semantic: green for success, yellow for idle or waiting, red for errors.
- Do not use dark gray or dark blue for text that must be read on a black terminal.

## 3. Typography

### Scale

| Level | Size | Weight | Line Height | Tracking | Usage |
|-------|------|--------|-------------|----------|-------|
| Body | terminal default | regular | terminal default | 0 | Default text |
| Label | terminal default | bold where supported | terminal default | 0 | Header, status, active cursor |
| Mono | terminal default | regular | terminal default | 0 | Tables, IDs, URLs |

### Font Stack

- Primary: user's terminal font
- Mono: user's terminal font
- Serif: not used

### Rules

- Text must remain readable without custom fonts.
- Use symbols and spacing for meaning so the interface still works without color.

## 4. Spacing & Layout

### Base Unit

Terminal layout uses character cells. Padding maps to 2 spaces inside the shared frame.

| Token | Value | Usage |
|-------|-------|-------|
| --space-1 | 1 cell | Cursor and compact separators |
| --space-2 | 2 cells | Frame inner padding |
| --space-4 | 4 cells | Menu nesting and table grouping |

### Grid

- Max content width: current terminal width
- Column system: fixed-width terminal cells
- Breakpoints: none; content truncates to the terminal width

### Rules

- Preserve the four-region layout from `scala-docs/TUI-DESIGN.md`.
- Do not let ANSI color codes affect measured layout width.

## 5. Components

### Shared TUI frame

- **Structure**: header, content rows, separator, input row, footer.
- **Variants**: idle, running, waiting, success, error.
- **Spacing**: 2-cell inner padding.
- **States**: status text changes by route and agent state.
- **Accessibility**: all meanings are also expressed through text or markers.
- **Motion**: spinner only while work is running.

### Selection menu

- **Structure**: `▸ item` for active rows, blank marker for inactive rows.
- **Variants**: single-select and multi-select.
- **Spacing**: 2 to 6 cells depending on nesting.
- **States**: active cursor uses the accent token.
- **Accessibility**: active row keeps the `▸` marker.
- **Motion**: none.

## 6. Motion & Interaction

### Timing

| Type | Duration | Easing | Usage |
|------|----------|--------|-------|
| Spinner | 350ms | linear | Agent and loading progress |

### Rules

- Motion is limited to terminal spinner frames.
- Route changes should be immediate.

## 7. Depth & Surface

### Strategy

Tonal-shift through color only. The shared frame uses bright blue borders; inner content stays on the terminal background without shadows.
