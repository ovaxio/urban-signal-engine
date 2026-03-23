# Frontend — context/frontend.md

Loaded for: component, page, dashboard, UI, map, chart, style, layout, theme.

## Critical rules
- All fetch calls through `frontend/lib/api.ts` — NEVER call fetch() in components
- Backend base URL: `NEXT_PUBLIC_API_BASE` env var
- No "use client" without written justification
- Prefer Server Components for data display, Client Components only for interactivity

## Styling
CSS Modules + inline styles. Tailwind migration planned but NOT started.
Do not begin Tailwind migration without explicit instruction.

## Key directories
```
frontend/
├── app/            # Pages (App Router)
├── components/
│   ├── zone/       # ZoneCard, ZoneGrid, ZoneForecast, ZoneSignals, ZoneTransportDetail
│   ├── chart/      # ZoneHistoryChart (recharts)
│   ├── map/        # ZoneMap (react-leaflet)
│   ├── report/     # ImpactReportView, ReportViewer
│   ├── alert/      # AlertPanel
│   ├── layout/     # AppHeader, AppNav, DashboardHeader, FilterBar, SimBanner
│   ├── theme/      # ThemeProvider, ThemeToggle
│   └── ui/         # ScoreBar, StatCard, ErrorState
├── domain/
│   ├── types.ts    # All domain types
│   ├── constants.ts # SIGNAL_LABELS, EVENT_ICONS, ZONE_CENTROIDS, COMPONENT_KEYS
│   └── scoring.ts  # Frontend scoring utilities
├── hooks/          # useCountUp
└── lib/api.ts      # ALL API calls — single source of truth
```

## Dependencies
recharts, react-leaflet, leaflet, Sentry, PostHog

## Server/Client boundary
Not yet audited. Most components are "use client" by default.
Do not add "use client" without justification.
