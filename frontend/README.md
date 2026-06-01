# AlphaTrade AI — Frontend

Next.js PWA scaffold for the human-in-the-loop paper trading copilot.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
```

Ensure the backend is running at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Development

```bash
npm run dev
```

Open http://localhost:3000

## Quality checks

```bash
npm run lint
npm run typecheck
npm run test
npm run build
```

## Safety UX

The UI always surfaces paper mode, disabled real trading, and mock provider mode.
Trading actions use paper-safe labels such as “Close paper position” and “Approve proposal”.

## Docker note

The frontend is not yet added to `docker-compose.yml`. Run it locally with `npm run dev`
while the backend stack runs via Docker Compose.
