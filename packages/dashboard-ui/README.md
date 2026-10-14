# Along Dashboard UI (`@along/dashboard-ui`)

The Along Dashboard UI is the internal web interface for inspecting repository entities, dependency DAGs, issues, decisions, and system diagnostics. It is served by `/along-dash` (FastAPI backend).

---

## Overview

The dashboard frontend is built strictly on the ActDim component and messaging ecosystem:

- **`@actdim/dynstruct`**: Structure-first component definition via `ComponentStruct` with explicit `props`, `actions`, `children`, `events`, and `effects`. Zero React boilerplate; all state lives in observable models.
- **`@actdim/dynstruct-mui`**: Material UI components adapted as Dynstruct hook-constructors (`useButton`, `useDrawer`, `useCard`, etc.).
- **`@actdim/msgmesh`**: Type-safe async messaging mesh for API communication and inter-component signaling.
- **`@actdim/utico`**: Foundation type utilities (`KeysOf`, `ToMsgChannelPrefix`, `ToMsgStruct`).

---

## Documentation & Conventions

Detailed technical specifications, coding conventions, and architectural contracts live in the Knowledge Base:

- **[Knowledge Base Index](./docs/INDEX.md)**: Documentation catalog and topic graph.
- **[Frontend Coding Conventions](./docs/topic--frontend-conventions.md)**: Mandatory Dynstruct and MsgMesh conventions, reactivity rules, component model, styling, and overlays.
- **[System Architecture & Flow](./docs/topic--architecture.md)**: System topology and backend integration.
- **[Domain Model & Entity Ecosystem](./docs/topic--domain-model.md)**: Entity schemas and DAG relationships.
- **[Setup & Workflow](./docs/topic--setup-and-workflow.md)**: Developer setup and verification lifecycle.

---

## Quick Start & Verification

### Scripts

- `pnpm run dev`: Start local Vite development server.
- `pnpm run build`: Production typecheck and bundle build (`tsc --noEmit && vite build`).
- `pnpm run generate:api`: Generate TypeScript client from FastAPI OpenAPI schema via NSwag.
- `pnpm run typecheck`: Run strict TypeScript validation (`tsc --noEmit`).
- `pnpm test`: Execute automated test suite via Vitest (`vitest run`).
