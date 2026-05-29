# CineSound Frontend

Next.js 14 chat UI for CineSound.

## Quickstart

```bash
cd frontend
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev
```

Open http://localhost:3000.

## Layout

```
frontend/
  app/
    layout.tsx        # root layout (dark mode default)
    page.tsx          # landing placeholder
    globals.css       # Tailwind base + design tokens
  lib/
    utils.ts          # cn() helper for shadcn
  components.json     # shadcn config
  tailwind.config.ts
  next.config.mjs
```

shadcn/ui components are added on-demand via `npx shadcn@latest add <component>` in later tasks.
