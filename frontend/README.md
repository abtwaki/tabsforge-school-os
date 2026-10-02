# TabsForge School OS Frontend

React 18 + Vite administration portal for TabsForge School OS.

## Development

```bash
npm install
npm run dev
```

The Django API is expected at `/api/` on the same origin. During local development, serve/proxy that path from Django or configure your reverse proxy accordingly.

## Production build

```bash
npm install
npm run build
```

Deploy the generated `dist/` directory to `/var/www/tabsforge-app/frontend/dist`. Configure the web server to fall back to `dist/index.html` for client-side routes while proxying `/api/` to Django.

## API assumptions

Login returns a token as `token`, `key`, or `access`, plus optional user data. `/api/auth/me/` is used to refresh the user role and school tier. Screens call conventional REST endpoints and gracefully show representative demo data when an endpoint is unavailable. Supported tiers are Sprout, Roots, Bloom, and Summit.
