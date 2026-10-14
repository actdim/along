---
protocol: along
slug: frontend-conventions
title: Frontend Coding Conventions (Dynstruct + MsgMesh)
type: reference
created: 2026-10-14
updated: 2026-10-14
tags: [conventions, dynstruct, msgmesh, dynstruct-mui, utico, routing, rules]
---

# Frontend Coding Conventions (Dynstruct + MsgMesh)

Rules for writing dashboard UI code on the ActDim component and messaging ecosystem. They extend the generic Along rule packs (`.along/rules/**`).

---

## 1. Component Model

1. **Every UI element is a Dynstruct component** (`@actdim/dynstruct`): `ComponentStruct` + `ComponentDef` + `useComponent` + `toReact`.
2. **Public vs. internal struct** (`ComponentStructExt<PublicStruct, InternalState>`):
   - Public `ComponentStruct`: only props passed by parents and the public `msgScope`. No loading flags, caches, or internal indices.
   - Internal state: private reactive `props`, private `actions`, private `effects`.
3. **Self-documenting `msgScope`**: the struct shows the component's bus interface:
   - `provide` - channels the component serves (`msgBroker.provide`).
   - `subscribe` - channels/events it listens to (`msgBroker.subscribe`).
   - `publish` - channels it sends to or requests from (`c.msgBus.send`, `c.msgBus.request`).
4. **Children, not inline JSX**: nested dynstruct components (including `@actdim/dynstruct-mui` wrappers) go into `def.children` via their `useXxx` constructor and render as `<c.children.Name />`.
5. **Bindings**: `bindProp(() => m, 'prop')` for two-way binding; `bind(() => expr)` for read-only values; `bind(get, set)` only for custom getter/setter logic.
6. **Params semantics**: plain params are initial values (applied once by `useComponent`); live input goes only through bindings. Never read `params.x` in a hook-constructor (`def.props` holds defaults only; live values for children come from `m` via `bindProp` / `bind`); bind factory-child props per value (`bind(() => p.item)`), never pass `p` whole. Details: [dynstruct Params Semantics](https://github.com/actdim/dynstruct/blob/main/AGENTS.md).
7. **No callback props**: never pass `onSelect*`, `onNavigate*`, `onOpen*`, `onClose*`, `onChange*` between components to coordinate state (dual sources of truth, timing races, desynchronization). `props` configure a component; `actions` are transactional mutators of its own state; cross-component coordination goes through typed MsgMesh channels (`c.msgBus.send`, `msgBroker.subscribe`), open/close state through two-way bindings. `on*` props are fine only on primitive wrappers over DOM events (button click, input change).

## 2. State, Lifecycle & Reactivity

1. **Hooks policy (Dynstruct-first, not a ban)**: built-in React hooks are not needed in typical components. Use the component model instead:
   - State -> `props: { ... }`, mutate via `m.prop = value`.
   - Mount / unmount -> `events: { onReady, onInit, onDestroy, onCatch, onValidate }`. Async loading on mount goes into `events.onReady`.
   - Side effects -> `effects: { ... }` (auto-tracks accessed model props).
   - Callbacks -> `actions: { ... }`.
   - Form inputs -> `c.mapToEdit('fieldPath')`.
   - A built-in hook is allowed only for a non-typical case; mark it with `// eslint-disable-next-line -- <reason>`. Custom and third-party hooks are allowed if app-visible state stays in the model. Details: [Hooks Policy](https://github.com/actdim/dynstruct/blob/main/docs/topic--04-react-integration.md).
2. **No direct MobX anywhere in application code** (features, components, pages): no imports from `mobx` / `mobx-react-lite` (`runInAction`, `action`, `observable`, `makeObservable`, `makeAutoObservable`, `observer`, `useLocalObservable`). Dynstruct encapsulates reactivity: mutate model props directly (`m.foo = bar`) or through `actions`.
3. **Reactivity granularity** (`ComponentProp.reactive?: true | false | 'shallow'`):
   - `'shallow'` - for large collections, read-only arrays: container mutations are tracked, items are not proxied.
   - `false` - for static configuration.

## 3. Communication (`@actdim/msgmesh`)

1. **Bus-first**: inter-component interaction, backend calls, notifications, and navigation go through `c.msgBus`. No prop drilling across features, no cross-component ref mutation.
2. **Backend API via bus adapters**: the API client is generated from FastAPI OpenAPI schemas via NSwag (`pnpm run generate:api`) producing `src/api/client.ts` with `DashboardApiClient`. Components call typed channels (e.g. `'API.DASHBOARD.GETFULLDATA'`), never `fetch()` / `axios` directly. Raw `fetch` is allowed only inside the generated client under `src/api/`.
3. **Channel groups**:
   - `in` - request payloads for request/response calls (`c.msgBus.request({ channel, group: 'in' })`).
   - `out` - provider responses and broadcast events (`msgBroker.subscribe`).
   - `ex` - fire-and-forget commands (e.g. `APP.NAV.GOTO`).
4. **Hierarchical filtering**: to receive messages only from descendants or ancestors, set `componentFilter: ComponentMsgFilter.FromDescendants` (or `FromAncestors`) in `msgBroker`. Used for intents of child items instead of callback props.
5. **Payloads through `c.msgBus`** are normalized (observables -> plain values); class instances (`File`, `Blob`, `Date`) are passed by reference.

### 3a. Dynamic Bus Struct via `@actdim/msgmesh/adapters`

Use `ToMsgChannelPrefix` and `ToMsgStruct` to generate typed channels at compile-time directly from `DashboardApiClient`:

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

Resulting channels are compile-time verified:
- `getFullData()` -> `"API.DASHBOARD.GETFULLDATA"`
- `searchKb(q, tag, type)` -> `"API.DASHBOARD.SEARCHKB"`
- `listIssues(status, ...)` -> `"API.DASHBOARD.LISTISSUES"`

### 3b. Automated Runtime Registration via `registerAdapters`

Use `getMsgChannelSelector(services)` and `registerAdapters`:

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

### 3c. Implicit Bus Injection via React Context & Component Proxies

- Create the bus once in `src/bus.ts` (`dashboardBus`).
- Inject it at the application root via `<ComponentContextProvider value={{ msgBus: dashboardBus }}>`.
- Components **never** create local buses or accept buses via manual props. Components access the bus implicitly via `c.msgBus`.
- `c.msgBus` inside a Dynstruct component is a specialized proxy that integrates with the component lifecycle, handles error scoping, and manages `msgScope` permissions.

### 3d. Clear Interaction Points & Observability

All published and subscribed channels of a component must be declared in its `msgScope`:

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

## 4. Overlays & Modal UI (Dialogs, Drawers, Sheets, Menus)

All overlay components (dialogs, bottom sheets, menus, drawers, popovers) must follow Dynstruct child and two-way binding conventions rather than React callback props. Never add `onClose`, `onOpen`, or `onDismiss` callback props.

1. **Declared as children of the host**: overlays are instantiated in `def.children` via their hook constructor (e.g. `useDrawer`, `useDialog`, `useAdaptiveMenu`, `useActionSheet`) and rendered in `view` as `<c.children.OverlayName />`.
2. **No `onClose` callback props**: the overlay dismisses itself internally (backdrop click, escape key, cancel button sets model `open = false`). The host observes and coordinates state through a two-way binding on `open`:
   - `bindProp(() => m, 'dialogOpen')` for direct model flag synchronization.
   - `bind(get, set)` when closing requires additional host state cleanup (e.g. resetting an anchor element):
     ```typescript
     open: bind(
         () => Boolean(m.anchorEl),
         (nextOpen) => {
             if (!nextOpen) {
                 m.anchorEl = null;
             }
         },
     ),
     ```
   - A host setter may veto or defer closing (for example, while submitting an asynchronous operation).
   - At boundaries with plain React components, closing events arrive via `$events.onChangeOpen(false)`.
3. **Live content via fragment children**: overlay content (`children`, `body`, custom `actions`) passed through bindings must be rendered through a host fragment child:
   ```typescript
   children: bind(() => <c.children.DialogBody />)
   ```
   where `dialogBody` is declared as a fragment child (`React.FC`) on the host. Fragment children are rendered as observers, keeping content reactive and synchronized while the overlay is visible. Inside, drawer or dialog content is a fragment child for the same reason.
4. **Hardware Back button and Escape lifecycle**: overlays handling navigation back events (Android `APP.HOST.BACK`, `APP.NAV.BACK`, or Escape key) register the handler in `def.effects` while `open` is true, and unregister on close and in `events.onDestroy`. (Never use bare React `useEffect` for overlay lifecycle inside hook constructors; nested child components do not run effect cleanups properly on mount/unmount).
5. **Canonical primitives and wrappers**: reuse existing core primitives from `@actdim/dynstruct-mui` (`useDrawer`, `useDialog`, `useMenu`) or shared components in `src/components/core/`. Menu and action icons (`MenuItemAction.icon`) support icon class strings (`'iconify tabler--upload'`) or React nodes (`renderMenuIcon`).

## 5. Routing & Navigation

1. Routes are declared with `createNavigationRoute` (`@actdim/dynstruct/appDomain/navigation`) and checked with `satisfies NavRoutes` (`@actdim/dynstruct/appDomain/commonContracts`). Patterns use `path-to-regexp` syntax.
2. Never call `useNavigate()` or change `window.location` for internal routes. Send a bus command:

```typescript
c.msgBus.send({
    channel: 'APP.NAV.GOTO',
    group: 'ex',
    payload: { route: 'explorer' },
});
```

## 6. TypeScript & Styling

1. No `any` (`@typescript-eslint/no-explicit-any` is an error). No `as ...` type assertions. No `interface`, no `class` - use `type`, pure functions, closures, plain objects.
2. No single-line control flow: always multi-line `{ ... }` blocks.
3. Tailwind CSS v4 for layouts, grids, flexbox, spacing, responsive structure, typography, transitions and visual styling. Icons: Iconify CSS classes via `@iconify/tailwind4` (`iconify <prefix>--<icon-name>`, e.g. `iconify mdi--database`, `iconify tabler--chevron-down`), never custom SVG or image tags; preferred prefixes `mdi`, `tabler`, `material-symbols`, `ph`, `devicon`, `logos`, `tdesign`, `vscode-icons`.
4. MUI through `@actdim/dynstruct-mui` wrappers (or custom dynstruct wrappers) for interactive behavior: menus, modals / dialogs, drawers, dropdowns, form inputs.
5. No storing state on `window` (`window.__ALONG_DATA__`). All payloads are strictly typed through channel definitions and NSwag DTO interfaces.

## 7. Content Security & Markdown Sanitization

- Markdown rendering (e.g. in `EntityDrawer.tsx`) must always be sanitized via `DOMPurify.sanitize(marked.parse(...))` to prevent XSS vulnerabilities.
- Mermaid diagrams must be configured with `securityLevel: 'strict'` under Content Security Policy (CSP).

## 8. Testing & Quality Gates

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

## 9. Component Ecosystem References

- Dynstruct Component Architecture: [`@actdim/dynstruct`](https://github.com/actdim/dynstruct)
- Message Mesh Adapter Protocol: [`@actdim/msgmesh`](https://github.com/actdim/msgmesh)
- Material UI Component Wrappers: [`@actdim/dynstruct-mui`](https://github.com/actdim/dynstruct-mui)
- Type Foundations & Helpers: [`@actdim/utico`](https://github.com/actdim/utico)

