---
protocol: along
slug: frontend-dynstruct-architecture-and-msgmesh-adapters
title: "Frontend Architecture: Dynstruct Component Architecture, MessageMesh Integration, and NSwag Adapters"
date: 2026-08-28
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-28--frontend-dynstruct-architecture-and-msgmesh-adapters - Frontend Architecture: Dynstruct Component Architecture, MessageMesh Integration, and NSwag Adapters

- Date: 2026-08-28
- Status: accepted
- Context: The web dashboard UI for Along required clear architectural guidelines for frontend components, state management, and backend communication. Ad-hoc React hooks, manual fetch calls, unstructured global variables, and loose `any` typing create boilerplate, high maintenance overhead, and obscure component communication.
- Decision:
  1. **Strict Dynstruct Component Architecture**: All UI components must use `@actdim/dynstruct` (`ComponentStruct`, `ComponentDef`, `useComponent`, MobX reactivity) and `@actdim/dynstruct-mui`. Avoid ad-hoc React hooks (`useState`, `useEffect`, `useMemo`), manual callback plumbing, or global `window` state storage.
  2. **Implicit Contextual Bus Integration**: The Message Mesh bus (`msgBus`) is created once and injected at the root via React context (`ComponentContextProvider`). Components access the bus implicitly via `c.msgBus` proxy, which provides built-in Dynstruct error handling, lifecycle management, and scoped messaging (`msgScope`, `msgBroker`).
  3. **Zero Manual API Channels & Fetch Handlers**: Do not manually write `MsgStruct` channel maps or manual `fetch` calls in `provide()`. All backend REST API clients are generated automatically from OpenAPI schemas via NSwag (`pnpm run generate:api`).
  4. **Dynamic Adapter Wiring via `@actdim/msgmesh/adapters`**:
     - Compute the channel prefix from the client literal type via `ToMsgChannelPrefix<'DashboardApiClient', 'API'>` (`API.DASHBOARD.`).
     - Dynamically map all client methods to typed message channels at compile-time via `ToMsgStruct<DashboardApiClient, DashboardChannelPrefix>`.
     - Register the client instance on the bus automatically at runtime using `getMsgChannelSelector(services)` and `registerAdapters(msgBus, adapters)`.
  5. **100% Strict Type Safety**: No `any` casting, no type assertions (`as ...`), and strict channel typing. All interaction points, emitted events, and subscriptions must be fully visible and traceable through component structs (`ComponentStruct<AppMsgStruct, ...>`).
- Consequences: Zero boilerplate, clean separation between UI components and backend transport, fully automated API client maintenance via NSwag, and transparent, declarative message routing with compile-time type safety.
