// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createMsgBus } from '@actdim/msgmesh/core';
import type { MsgBus } from '@actdim/msgmesh/contracts';
import type { Component, ComponentParams } from '@actdim/dynstruct/componentModel/contracts';
import { ComponentContextProvider } from '@actdim/dynstruct/componentModel/react/componentContext';
import { useIssuesView, type IssuesViewStruct } from './IssuesKanbanView';
import type { DashboardAppMsgStruct } from '../bus';
import type { Issue } from '../types';

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mockIssues: Issue[] = [
  {
    id: 'feat--search',
    slug: 'search',
    protocol: 'along',
    type: 'feat',
    status: 'in-progress',
    priority: 'high',
    title: 'Workspace search system',
    body: 'Implement search across KB, issues, decisions, and sessions',
    file_path: '.along/ISSUES/feat--search.md',
    tags: ['search', 'indexing'],
    created: '2026-10-01',
    updated: '2026-10-02',
    completed: undefined,
    agent: 'antigravity',
    milestone: undefined,
    blocked_by: [],
    related: [],
    parent: undefined,
    superseded_by: undefined,
    duplicate_of: undefined,
  },
  {
    id: 'bug--render-crash',
    slug: 'render-crash',
    protocol: 'along',
    type: 'bug',
    status: 'open',
    priority: 'critical',
    title: 'Fix render crash on empty collection',
    body: 'Component crashes when data is null or empty array',
    file_path: '.along/ISSUES/bug--render-crash.md',
    tags: ['bug', 'ui'],
    created: '2026-10-03',
    updated: '2026-10-03',
    completed: undefined,
    agent: 'antigravity',
    milestone: undefined,
    blocked_by: [],
    related: [],
    parent: undefined,
    superseded_by: undefined,
    duplicate_of: undefined,
  },
  {
    id: 'debt--legacy-types',
    slug: 'legacy-types',
    protocol: 'along',
    type: 'debt',
    status: 'done',
    priority: 'low',
    title: 'Remove legacy types and unused imports',
    body: 'Clean up deprecated type definitions and imports',
    file_path: '.along/ISSUES/debt--legacy-types.md',
    tags: ['refactor', 'cleanup'],
    created: '2026-10-04',
    updated: '2026-10-05',
    completed: '2026-10-05',
    agent: 'antigravity',
    milestone: undefined,
    blocked_by: [],
    related: [],
    parent: undefined,
    superseded_by: undefined,
    duplicate_of: undefined,
  },
];

describe('IssuesKanbanView component', () => {
  let container: HTMLDivElement;
  let root: Root;
  let capturedComponent: Component<IssuesViewStruct> | null = null;
  let testBus: MsgBus<DashboardAppMsgStruct>;

  const Harness: React.FC<{ params: ComponentParams<IssuesViewStruct> }> = (props) => {
    const c = useIssuesView(props.params);
    capturedComponent = c;
    return <c.View />;
  };

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    capturedComponent = null;
    testBus = createMsgBus<DashboardAppMsgStruct>();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    capturedComponent = null;
  });

  it('initializes model state with default filter values', () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              issues: mockIssues,
            }}
          />
        </ComponentContextProvider>
      );
    });

    expect(capturedComponent).not.toBeNull();
    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }

    const m = capturedComponent.model;
    expect(m.searchQuery).toBe('');
    expect(m.statusFilter).toBe('all');
    expect(m.typeFilter).toBe('all');
    expect(m.priorityFilter).toBe('all');
    expect(m.viewMode).toBe('table');
    expect(m.issues.length).toBe(3);
    expect(m.filteredIssues.length).toBe(3);
  });

  it('filters issues by search query across title, slug, id, and tags', () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              issues: mockIssues,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    // Search by title keyword
    act(() => {
      m.searchQuery = 'workspace';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['feat--search']);

    // Search by slug
    act(() => {
      m.searchQuery = 'render-crash';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['bug--render-crash']);

    // Search by tag
    act(() => {
      m.searchQuery = 'cleanup';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['debt--legacy-types']);

    // Search case-insensitive
    act(() => {
      m.searchQuery = 'SEARCH';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['feat--search']);

    // Reset search
    act(() => {
      m.searchQuery = '';
    });
    expect(m.filteredIssues.length).toBe(3);
  });

  it('filters issues by status, type, priority, and their intersection', () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              issues: mockIssues,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    // Filter by status
    act(() => {
      m.statusFilter = 'in-progress';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['feat--search']);

    act(() => {
      m.statusFilter = 'done';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['debt--legacy-types']);

    // Reset status and filter by type
    act(() => {
      m.statusFilter = 'all';
      m.typeFilter = 'bug';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['bug--render-crash']);

    // Reset type and filter by priority
    act(() => {
      m.typeFilter = 'all';
      m.priorityFilter = 'critical';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['bug--render-crash']);

    // Test intersection: matching all 4 filters
    act(() => {
      m.searchQuery = 'crash';
      m.statusFilter = 'open';
      m.typeFilter = 'bug';
      m.priorityFilter = 'critical';
    });
    expect(m.filteredIssues.map((i) => i.id)).toEqual(['bug--render-crash']);

    // Test intersection: non-matching priority eliminates result
    act(() => {
      m.priorityFilter = 'low';
    });
    expect(m.filteredIssues.length).toBe(0);
  });

  it('publishes APP.ENTITY.SELECT with { id, type } on selectIssue action', async () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              issues: mockIssues,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    const eventPromise = testBus.once({ channel: 'APP.ENTITY.SELECT' });

    act(() => {
      m.selectIssue('feat--search', 'feat');
    });

    const received = await eventPromise;
    expect(received.payload).toEqual({ id: 'feat--search', type: 'feat' });
  });

  it('renders filter controls and view mode toggles in DOM', () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              issues: mockIssues,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }

    // Check search input exists
    const searchInput = container.querySelector('input[placeholder="Filter issues..."]');
    expect(searchInput).not.toBeNull();

    // Check select dropdowns exist (Status, Type, Priority)
    const selectElements = container.querySelectorAll('select');
    expect(selectElements.length).toBe(3);

    // Check view mode buttons exist by title
    const tableButton = container.querySelector('button[title="Table View"]');
    const kanbanButton = container.querySelector('button[title="Kanban Board"]');
    expect(tableButton).not.toBeNull();
    expect(kanbanButton).not.toBeNull();

    // Check switching view mode to kanban
    act(() => {
      if (capturedComponent) {
        capturedComponent.model.viewMode = 'kanban';
      }
    });

    expect(capturedComponent.model.viewMode).toBe('kanban');
    const columnHeadings = container.querySelectorAll('h3');
    expect(columnHeadings.length).toBe(4);
  });
});
