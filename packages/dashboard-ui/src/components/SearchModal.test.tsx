// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createMsgBus } from '@actdim/msgmesh/core';
import type { MsgBus } from '@actdim/msgmesh/contracts';
import type { Component, ComponentParams } from '@actdim/dynstruct/componentModel/contracts';
import { ComponentContextProvider } from '@actdim/dynstruct/componentModel/react/componentContext';
import { useSearchModal, type SearchModalStruct } from './SearchModal';
import type { DashboardAppMsgStruct } from '../bus';
import type { FullDashboardData, SearchResultItem } from '../types';

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mockData: FullDashboardData = {
  repo_name: 'along',
  metrics: {
    total_issues: 1,
    open_issues: 1,
    in_progress_issues: 0,
    blocked_issues: 0,
    done_issues: 0,
    completion_pct: 0,
    bug_debt_ratio: 0,
    active_risks: 0,
    active_milestones: 0,
    total_kb_articles: 1,
    total_decisions: 1,
    total_sessions: 1,
    by_status: {
      open: 1,
      in_progress: 0,
      blocked: 0,
      done: 0,
      superseded: 0,
      cancelled: 0,
      duplicate: 0,
    },
    by_type: { feat: 1, bug: 0, debt: 0, task: 0, docs: 0 },
    by_priority: { critical: 0, high: 1, medium: 0, low: 0 },
    scan_timestamp: '2026-11-09 00:00:00',
    protocol_version: '4.7.0',
  },
  issues: [
    {
      id: 'feat--search-filter',
      slug: 'search-filter',
      protocol: 'along',
      type: 'feat',
      status: 'open',
      priority: 'high',
      title: 'Search Filtering System',
      body: 'Filter results by source type and keyword scoring',
      file_path: '.along/ISSUES/feat--search-filter.md',
      tags: ['search', 'filter'],
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
  ],
  milestones: [],
  risks: [],
  spikes: [],
  sessions: [
    {
      id: 'session--2026-10-01',
      slug: '2026-10-01--initial-arch',
      protocol: 'along',
      title: 'Initial Architecture Session',
      body: 'Discussion on search indexing and performance optimizations',
      file_path: '.along/SESSIONS/2026-10-01.md',
      date: '2026-10-01',
      agent: 'antigravity',
      branch: 'main',
      commit: 'abcdef1',
      summary: 'Reviewing reactive layout and search indexing',
      milestone: undefined,
      issues_advanced: ['feat--search-filter'],
      issues_completed: [],
      decisions: ['ADR-001'],
      risks_logged: [],
      spikes_conducted: [],
    },
  ],
  decisions: [
    {
      id: 'ADR-001',
      slug: 'adopt-dynstruct',
      number: 1,
      title: 'Adopt Dynstruct Framework',
      date: '2026-10-01',
      status: 'accepted',
      context: 'Component model abstraction without direct MobX',
      decision: 'Use dynstruct for reactive UI state',
      consequences: 'Clean separation of state and view',
      file_path: '.along/DECISIONS/ADR-001.md',
      raw_markdown: 'Adopt Dynstruct Framework for reactive UI state',
      superseded_by: undefined,
    },
  ],
  kb_articles: [
    {
      id: 'topic--architecture',
      slug: 'topic--architecture',
      title: 'System Architecture',
      type: 'architecture',
      created: '2026-10-01',
      updated: '2026-10-02',
      tags: ['architecture', 'design'],
      file_path: 'docs/topic--architecture.md',
      body: 'System overview and message bus topology specifications',
      headings: ['Architecture', 'Bus Topology'],
      outgoing_links: [],
      incoming_links: [],
    },
  ],
  graph: null,
  context_text: '',
  issues_board_text: '',
};

describe('SearchModal component', () => {
  let container: HTMLDivElement;
  let root: Root;
  let capturedComponent: Component<SearchModalStruct> | null = null;
  let testBus: MsgBus<DashboardAppMsgStruct>;

  const Harness: React.FC<{ params: ComponentParams<SearchModalStruct> }> = (props) => {
    const c = useSearchModal(props.params);
    capturedComponent = c;
    return <c.View />;
  };

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    capturedComponent = null;
    testBus = createMsgBus<DashboardAppMsgStruct>();
    testBus.provide({
      channel: 'API.DASHBOARD.SEARCHKB',
      callback: () => {
        return { query: '', total: 0, results: [] };
      },
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    capturedComponent = null;
  });

  it('controls open and close state via model actions', () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              data: mockData,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    expect(m.isOpen).toBe(false);

    act(() => {
      m.open();
    });
    expect(m.isOpen).toBe(true);

    act(() => {
      m.close();
    });
    expect(m.isOpen).toBe(false);
  });

  it('performs search over m.data matching kb, issues, decisions, and sessions', async () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              data: mockData,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    // Search matching KB article
    await act(async () => {
      await m.performSearch('architecture');
    });
    const kbMatch = m.results.find((r) => r.id === 'topic--architecture');
    expect(kbMatch).toBeDefined();
    expect(kbMatch?.type).toBe('kb');

    // Search matching Issue
    await act(async () => {
      await m.performSearch('filter');
    });
    const issueMatch = m.results.find((r) => r.id === 'feat--search-filter');
    expect(issueMatch).toBeDefined();
    expect(issueMatch?.type).toBe('issue');

    // Search matching Decision
    await act(async () => {
      await m.performSearch('dynstruct');
    });
    const decisionMatch = m.results.find((r) => r.id === 'ADR-001');
    expect(decisionMatch).toBeDefined();
    expect(decisionMatch?.type).toBe('decision');

    // Search matching Session
    await act(async () => {
      await m.performSearch('indexing');
    });
    const sessionMatch = m.results.find((r) => r.id === 'session--2026-10-01');
    expect(sessionMatch).toBeDefined();
    expect(sessionMatch?.type).toBe('session');
  });

  it('resets results on empty query or whitespace query', async () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              data: mockData,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    // First populate results
    await act(async () => {
      await m.performSearch('architecture');
    });
    expect(m.results.length).toBeGreaterThan(0);

    // Empty string resets results
    await act(async () => {
      await m.performSearch('');
    });
    expect(m.results).toEqual([]);

    // Whitespace query resets results
    await act(async () => {
      await m.performSearch('   ');
    });
    expect(m.results).toEqual([]);
  });

  it('filters results by activeTypeFilter', async () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              data: mockData,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    // Filter by 'kb' only
    act(() => {
      m.activeTypeFilter = 'kb';
    });
    await act(async () => {
      await m.performSearch('search');
    });
    // feat--search-filter is an issue, not kb; so it should not appear
    for (const r of m.results) {
      expect(r.type).toBe('kb');
    }

    // Filter by 'issue' only
    act(() => {
      m.activeTypeFilter = 'issue';
    });
    await act(async () => {
      await m.performSearch('search');
    });
    expect(m.results.length).toBeGreaterThan(0);
    for (const r of m.results) {
      expect(r.type).toBe('issue');
    }
  });

  it('selectResult closes modal and publishes APP.ENTITY.SELECT', async () => {
    act(() => {
      root.render(
        <ComponentContextProvider value={{ msgBus: testBus }}>
          <Harness
            params={{
              data: mockData,
            }}
          />
        </ComponentContextProvider>
      );
    });

    if (!capturedComponent) {
      throw new Error('Component was not captured');
    }
    const m = capturedComponent.model;

    act(() => {
      m.open();
    });
    expect(m.isOpen).toBe(true);

    const eventPromise = testBus.once({ channel: 'APP.ENTITY.SELECT' });

    const selectedItem: SearchResultItem = {
      id: 'feat--search-filter',
      type: 'issue',
      title: 'Search Filtering System',
      file_path: '.along/ISSUES/feat--search-filter.md',
      score: 1.0,
      snippet: 'Filter results by source type',
      tags: ['search', 'filter'],
    };

    act(() => {
      m.selectResult(selectedItem);
    });

    const received = await eventPromise;
    expect(received.payload).toEqual({
      id: 'feat--search-filter',
      type: 'issue',
    });
    expect(m.isOpen).toBe(false);
  });
});
