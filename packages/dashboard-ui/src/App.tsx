import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { bind } from '@actdim/dynstruct/componentModel/core';
import { useTabs, type TabsStruct } from '@actdim/dynstruct-mui/Tabs';
import { Icon } from '@iconify/react';
import { FullDashboardData } from './types';
import { DashboardAppMsgStruct, DashboardMsgChannels } from './bus';
import { DashboardApiService } from './services/apiService';
import { useHeader, type HeaderStruct } from './components/Header';
import { useOverviewView, type OverviewViewStruct } from './components/OverviewView';
import { useIssuesView, type IssuesViewStruct } from './components/IssuesKanbanView';
import { useGraphView, type GraphViewStruct } from './components/DAGGraphView';
import { useKBView, type KBViewStruct } from './components/KBExplorerView';
import { useSessionsView, type SessionsViewStruct } from './components/SessionsDecisionsView';
import { useEntityDrawer, type EntityDrawerStruct } from './components/EntityDrawer';
import { useSearchModal, type SearchModalStruct } from './components/SearchModal';

export type DashboardAppStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      data: FullDashboardData | null;
      loading: boolean;
      error: string | null;
      activeTab: string;
      selectedEntityId: string | null;
      searchModalOpen: boolean;
      sseConnected: boolean;
    };
    msgScope: {
      subscribe: DashboardMsgChannels<
        | 'APP.TAB.SET'
        | 'APP.ENTITY.SELECT'
        | 'APP.ENTITY.CLOSE'
        | 'APP.DATA.UPDATED'
        | 'APP.SSE.STATUS'
        | 'APP.SEARCH.OPEN'
        | 'APP.SEARCH.CLOSE'
      >;
      publish: DashboardMsgChannels<'API.DASHBOARD.GETFULLDATA'>;
    };
    actions: {
      loadData: () => Promise<void>;
      selectEntity: (id: string) => void;
      closeEntity: () => void;
      switchTab: (tab: string) => void;
      openSearch: () => void;
      closeSearch: () => void;
    };
    children: {
      header: HeaderStruct;
      tabs: TabsStruct;
      overviewView: OverviewViewStruct;
      issuesView: IssuesViewStruct;
      graphView: GraphViewStruct;
      kbView: KBViewStruct;
      sessionsView: SessionsViewStruct;
      entityDrawer: EntityDrawerStruct;
      searchModal: SearchModalStruct;
    };
  }
>;

export const useDashboardApp = (
  params?: ComponentParams<DashboardAppStruct>
): Component<DashboardAppStruct> => {
  let c: Component<DashboardAppStruct>;
  let m: ComponentModel<DashboardAppStruct>;

  const handleKeyDown = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      m.openSearch();
    } else if (
      e.key === '/' &&
      (e.target as HTMLElement).tagName !== 'INPUT' &&
      (e.target as HTMLElement).tagName !== 'TEXTAREA'
    ) {
      e.preventDefault();
      m.openSearch();
    }
  };

  const def: ComponentDef<DashboardAppStruct> = {
    regType: 'DashboardApp',
    props: {
      data: null,
      loading: true,
      error: null,
      activeTab: 'overview',
      selectedEntityId: null,
      searchModalOpen: false,
      sseConnected: false,
    },
    actions: {
      loadData: async () => {
        m.loading = true;
        try {
          const msgResp = await c.msgBus.request({
            channel: 'API.DASHBOARD.GETFULLDATA',
            options: {
              timeout: 10000,
              abortSignal: new AbortController().signal,
            },
          });
          m.data = msgResp.payload || null;
          m.error = null;
        } catch (err: any) {
          console.error('Failed to load dashboard data:', err);
          m.error = err.message || 'Error fetching data';
        } finally {
          m.loading = false;
        }
      },
      selectEntity: (id: string) => {
        m.selectedEntityId = id;
      },
      closeEntity: () => {
        m.selectedEntityId = null;
      },
      switchTab: (tab: string) => {
        m.activeTab = tab;
      },
      openSearch: () => {
        m.searchModalOpen = true;
      },
      closeSearch: () => {
        m.searchModalOpen = false;
      },
    },
    msgBroker: {
      subscribe: {
        'APP.TAB.SET': {
          in: {
            callback: (msg) => {
              if (msg.payload) m.switchTab(msg.payload);
            },
          },
        },
        'APP.ENTITY.SELECT': {
          in: {
            callback: (msg) => {
              if (msg.payload?.id) m.selectEntity(msg.payload.id);
            },
          },
        },
        'APP.ENTITY.CLOSE': {
          in: {
            callback: () => {
              m.closeEntity();
            },
          },
        },
        'APP.DATA.UPDATED': {
          in: {
            callback: (msg) => {
              if (msg.payload) {
                m.data = msg.payload;
                m.error = null;
              }
            },
          },
        },
        'APP.SSE.STATUS': {
          in: {
            callback: (msg) => {
              m.sseConnected = Boolean(msg.payload?.connected);
            },
          },
        },
        'APP.SEARCH.OPEN': {
          in: {
            callback: () => {
              m.openSearch();
            },
          },
        },
        'APP.SEARCH.CLOSE': {
          in: {
            callback: () => {
              m.closeSearch();
            },
          },
        },
      },
    },
    events: {
      onReady: async () => {
        // 1. Start API service provider on the bus
        DashboardApiService.start();

        // 2. Global keyboard shortcut (Ctrl+K or /)
        window.addEventListener('keydown', handleKeyDown);

        // 3. Initial data load via c.msgBus
        await m.loadData();
      },
      onDestroy: () => {
        window.removeEventListener('keydown', handleKeyDown);
        DashboardApiService.stop();
      },
    },
    children: {
      header: useHeader({
        repoName: bind(() => m.data?.repo_name || 'Along'),
        scanTimestamp: bind(() => m.data?.metrics.scan_timestamp || ''),
        sseConnected: bind(() => m.sseConnected),
        protocolVersion: bind(() => m.data?.metrics.protocol_version || '3.9.4'),
        onSearchClick: () => m.openSearch(),
      }),
      tabs: useTabs({
        value: bind(() => m.activeTab),
        onChange: (v: string) => m.switchTab(v),
        variant: 'scrollable',
        tabs: [
          { value: 'overview', label: 'Overview' },
          { value: 'issues', label: 'Issues & Kanban' },
          { value: 'graph', label: 'DAG Graph' },
          { value: 'kb', label: 'Knowledge Base' },
          { value: 'sessions', label: 'Sessions & ADR' },
        ],
        sx: {
          minHeight: '44px',
          '& .MuiTab-root': {
            color: '#94a3b8',
            fontSize: '0.8125rem',
            fontWeight: 600,
            textTransform: 'none',
            minHeight: '44px',
            padding: '8px 16px',
            borderRadius: '8px',
            transition: 'all 0.2s',
            '&.Mui-selected': {
              color: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
            },
          },
          '& .MuiTabs-indicator': {
            backgroundColor: '#38bdf8',
            height: '3px',
            borderRadius: '3px',
          },
        },
      }),
      overviewView: useOverviewView({
        data: bind(() => m.data),
      }),
      issuesView: useIssuesView({
        issues: bind(() => m.data?.issues || []),
      }),
      graphView: useGraphView({
        graphData: bind(() => m.data?.graph || { nodes: [], edges: [] }),
      }),
      kbView: useKBView({
        articles: bind(() => m.data?.kb_articles || []),
      }),
      sessionsView: useSessionsView({
        sessions: bind(() => m.data?.sessions || []),
        decisions: bind(() => m.data?.decisions || []),
      }),
      entityDrawer: useEntityDrawer({
        data: bind(() => m.data),
        selectedEntityId: bind(() => m.selectedEntityId),
        onClose: () => m.closeEntity(),
      }),
      searchModal: useSearchModal({
        isOpen: bind(() => m.searchModalOpen),
        onClose: () => m.closeSearch(),
        data: bind(() => m.data),
      }),
    },
    view: () => {
      if (m.loading && !m.data) {
        return (
          <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 space-y-4">
            <Icon icon="lucide:loader-2" className="w-8 h-8 text-sky-400 animate-spin" />
            <p className="text-sm font-mono">Loading Along Dashboard & KB Engine via MsgMesh...</p>
          </div>
        );
      }

      if (m.error && !m.data) {
        return (
          <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-300 p-6">
            <div className="bg-slate-900 border border-rose-800/80 rounded-2xl p-6 max-w-md w-full text-center space-y-4 shadow-xl">
              <Icon icon="lucide:alert-triangle" className="w-10 h-10 text-rose-400 mx-auto" />
              <h2 className="text-lg font-bold text-slate-100">Failed to Connect to Dashboard API</h2>
              <p className="text-xs text-slate-400 font-mono">{m.error}</p>
              <button
                onClick={() => m.loadData()}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-500 rounded-xl text-xs font-semibold text-white transition"
              >
                Retry Connection
              </button>
            </div>
          </div>
        );
      }

      return (
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-sky-500/30 selection:text-sky-200">
          {/* Header */}
          <c.children.Header />

          {/* Subheader Navigation with Material UI Tabs */}
          <div className="bg-slate-900/90 border-b border-slate-800">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <c.children.Tabs />
            </div>
          </div>

          {/* Main View Area */}
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
            {m.data && (
              <>
                {m.activeTab === 'overview' && <c.children.OverviewView />}
                {m.activeTab === 'issues' && <c.children.IssuesView />}
                {m.activeTab === 'graph' && <c.children.GraphView />}
                {m.activeTab === 'kb' && <c.children.KbView />}
                {m.activeTab === 'sessions' && <c.children.SessionsView />}
              </>
            )}
          </main>

          {/* Drawers and Modals */}
          <c.children.EntityDrawer />
          <c.children.SearchModal />
        </div>
      );
    },
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const App = toReact(useDashboardApp);
