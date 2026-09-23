# Along Dashboard UI (`@along/dashboard-ui`)

The Along Dashboard UI is the internal web interface for inspecting repository entities, dependency DAGs, issues, decisions, and system diagnostics. It is served by `/along-dash` (FastAPI backend).

---

## Architecture & Ecosystem Standards

The dashboard frontend is built strictly on the ActDim component and messaging ecosystem:

### 1. Core Ecosystem Components

1. **`@actdim/dynstruct`**
   - **Pattern**: Structure-first component definition via `ComponentStruct<AppMsgStruct, ...>` with explicit `props`, `actions`, `children`, `events`, and `effects`.
   - **Zero React Boilerplate**: All component state lives in observable `c.model` (MobX under the hood). No raw React `useState`, `useMemo`, `useCallback`, or hook spaghetti.

2. **`@actdim/dynstruct-mui`**
   - **Pattern**: Material UI components adapted as Dynstruct hook-constructors (`useButton`, `useDrawer`, `useCard`, `useTabs`, `useChip`, `useTextField`, `useDialog`, `useTable`, etc.).

3. **`@actdim/msgmesh`**
   - **Pattern**: Type-safe async messaging mesh for API communication and inter-component signaling.

4. **`@actdim/utico`**
   - **Pattern**: Foundation type utilities (`KeysOf`, `ToMsgChannelPrefix`, `ToMsgStruct`).

---

## Mandatory Architectural Rules & Invariants

### 1. Zero Manual API Channels & No Manual `fetch` Handlers
- **NEVER** write manual `MsgStruct` channel maps (`{ in: ..., out: ... }`) for backend REST/OpenAPI endpoints.
- **NEVER** write manual `fetch` or `axios` handlers inside `provide()`.
- All backend API clients are generated automatically from FastAPI OpenAPI schemas via NSwag:
  ```bash
  pnpm run generate:api
  ```
  This creates [src/api/client.ts](./src/api/client.ts) containing `DashboardApiClient`.

### 2. Dynamic Bus Struct via `@actdim/msgmesh/adapters`
- Use `ToMsgChannelPrefix` and `ToMsgStruct` to generate typed channels at compile-time directly from `DashboardApiClient`:
  ```typescript
  export type ApiPrefix = 'API';
  export type DashboardApiClientName = 'DashboardApiClient';

  export type DashboardChannelPrefix = ToMsgChannelPrefix<
    DashboardApiClientName,
    ApiPrefix,
    BaseServiceSuffix
  >; // 'API.DASHBOARD.'

  export type DashboardApiStruct = ToMsgStruct<
    DashboardApiClient,
    DashboardChannelPrefix
  >;
  ```
- Resulting channels are compile-time verified:
  - `getFullData()` -> `"API.DASHBOARD.GETFULLDATA"`
  - `searchKb(q, tag, type)` -> `"API.DASHBOARD.SEARCHKB"`
  - `listIssues(status, ...)` -> `"API.DASHBOARD.LISTISSUES"`

### 3. Automated Runtime Registration via `registerAdapters`
- Use `getMsgChannelSelector(services)` and `registerAdapters`:
  ```typescript
  const services: Record<DashboardChannelPrefix, any> = {
    'API.DASHBOARD.': new DashboardApiClient(),
  };

  const adapters = Object.entries(services).map(([_, service]) => ({
    service,
    channelSelector: getMsgChannelSelector(services),
  })) as MsgProviderAdapter[];

  registerAdapters(dashboardBus, adapters);
  ```

### 4. Implicit Bus Injection via React Context & Component Proxies
- Create the bus once in `src/bus.ts` (`dashboardBus`).
- Inject it at the application root via `<ComponentContextProvider value={{ msgBus: dashboardBus }}>`.
- Components **never** create local buses or accept buses via manual props. Components access the bus implicitly via `c.msgBus`.
- `c.msgBus` inside a Dynstruct component is a specialized proxy that integrates with the component lifecycle, handles error scoping, and manages `msgScope` permissions.

### 5. Clear Interaction Points & Observability
- All published and subscribed channels of a component must be declared in its `msgScope`:
  ```typescript
  export type MyViewStruct = ComponentStruct<
    DashboardAppMsgStruct,
    {
      msgScope: {
        subscribe: DashboardMsgChannels<'APP.DATA.UPDATED' | 'APP.SSE.STATUS'>;
        publish: DashboardMsgChannels<'API.DASHBOARD.GETFULLDATA' | 'APP.ENTITY.SELECT'>;
      };
      // ...
    }
  >;
  ```

### 6. 100% Strict Type Safety (Zero `any` & Zero `window` State Hacks)
- No `any` type casting.
- No `as ...` type assertions.
- No storing state on `window` (`window.__ALONG_DATA__`).
- All payloads are strictly typed through channel definitions and NSwag DTO interfaces.

### 7. Content Security & Markdown Sanitization
- Markdown rendering (e.g. in `EntityDrawer.tsx`) must always be sanitized via `DOMPurify.sanitize(marked.parse(...))` to prevent XSS vulnerabilities.
- Mermaid diagrams must be configured with `securityLevel: 'strict'` under Content Security Policy (CSP).

### 8. Testing & Quality Gates
- Component and unit tests use `vitest` with `happy-dom`:
  ```bash
  pnpm test
  ```
- Type checking is enforced via `tsc --noEmit`:
  ```bash
  pnpm run typecheck
  ```
- Production build:
  ```bash
  pnpm run build
  ```
