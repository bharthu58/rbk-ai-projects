# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run setup        # Install deps + generate Prisma client + run migrations
npm run dev          # Dev server at http://localhost:3000 (Turbopack)
npm run build        # Production build
npm test             # Vitest unit tests
npm test -- <file>   # Run a single test file
npm run lint         # ESLint
npm run db:reset     # Reset SQLite database (destructive)
```

Requires `ANTHROPIC_API_KEY` in `.env` for live AI generation; falls back to `MockLanguageModel` without it.

## Architecture

UIGen is a Next.js 15 app where users describe React components in a chat and see them rendered live in a sandboxed iframe. No files are ever written to disk — everything runs in a **VirtualFileSystem** (in-memory `Map`-based tree).

### Request Flow

1. User message → `ChatContext` → POST `/api/chat` with serialized file system state
2. `route.ts` calls Claude (`claude-haiku-4-5`) via Vercel AI SDK `streamText()` with two tools: `str_replace_editor` and `file_manager`
3. Tool calls execute server-side, mutating a reconstructed `VirtualFileSystem`
4. Client-side `handleToolCall()` in `FileSystemContext` mirrors those mutations locally
5. `PreviewFrame` detects changes → calls `createImportMap()` → rebuilds iframe HTML with blob URLs + import map → re-renders live preview

### Key Abstractions

- **`src/lib/file-system.ts`** — `VirtualFileSystem` class. All file operations go through here. Serializes to `Record<path, content>` JSON for DB persistence.
- **`src/lib/contexts/file-system-context.tsx`** — React context wrapping `VirtualFileSystem`; exposes `handleToolCall()` which maps AI tool invocations to file system mutations and triggers re-renders.
- **`src/lib/contexts/chat-context.tsx`** — Wraps Vercel AI SDK `useChat()`; watches message stream for tool-call parts and applies them to `FileSystemContext`.
- **`src/lib/transform/jsx-transformer.ts`** — Transpiles JSX via Babel Standalone, resolves `@/` aliases to blob URLs, and maps third-party imports to `esm.sh` CDN. Produces the full HTML document injected into the preview iframe.
- **`src/lib/provider.ts`** — `getLanguageModel()` returns real Anthropic client or `MockLanguageModel` based on `ANTHROPIC_API_KEY`. `MockLanguageModel` streams fake tool calls to demonstrate the UI without an API key.
- **`src/lib/tools/`** — Zod-typed tool definitions (`str-replace.ts`, `file-manager.ts`) passed to `streamText()`. Their `execute` functions run server-side.
- **`src/lib/prompts/generation.tsx`** — System prompt instructing Claude to use `/App.jsx` as root entry, Tailwind CSS for styling, and `@/` for local imports.

### Persistence

- **Authenticated users:** On AI response completion (`onFinish`), `/api/chat/route.ts` saves `messages` JSON + `fileSystem.serialize()` to the `Project` model in SQLite via Prisma.
- **Anonymous users:** `anon-work-tracker.ts` stores state in localStorage.
- Prisma schema: `prisma/schema.prisma` — reference it whenever you need to understand the structure of data stored in the database. Client generated to `src/generated/prisma/`.

### Authentication

JWT-based via `jose`. `src/lib/auth.ts` issues 7-day tokens stored as httpOnly cookies. Server actions in `src/actions/index.ts` handle sign-up/sign-in (bcrypt) and sign-out.

## Code Style

- Use comments sparingly. Only comment complex code.

### App Router Structure

- `src/app/page.tsx` — Home: redirects authenticated users to their latest project; anonymous users see MainContent without a `projectId`.
- `src/app/[projectId]/page.tsx` — Loads project from DB, hydrates `MainContent` with saved messages and file system data.
- `src/app/api/chat/route.ts` — Streaming AI endpoint. Max duration 120s, max 40 tool steps.
- `src/app/main-content.tsx` — 3-panel layout: Chat (left 35%) + Preview/Code toggle (right 65%).
