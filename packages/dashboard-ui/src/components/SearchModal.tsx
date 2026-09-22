import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { Dialog } from '@mui/material';
import { Icon } from '@iconify/react';
import { SearchResultItem, FullDashboardData } from '../types';
import { DashboardAppMsgStruct, DashboardMsgChannels } from '../bus';

export type SearchModalStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      isOpen: boolean;
      onClose: () => void;
      query: string;
      activeTypeFilter: string;
      results: SearchResultItem[];
      loading: boolean;
      data?: FullDashboardData | null;
    };
    msgScope: {
      publish: DashboardMsgChannels<'API.DASHBOARD.SEARCHKB' | 'APP.ENTITY.SELECT'>;
      subscribe: DashboardMsgChannels<'APP.SEARCH.OPEN' | 'APP.SEARCH.CLOSE'>;
    };
    actions: {
      performSearch: (queryText: string) => Promise<void>;
      selectResult: (r: SearchResultItem) => void;
      open: () => void;
      close: () => void;
    };
  }
>;

export const useSearchModal = (
  params?: ComponentParams<SearchModalStruct>
): Component<SearchModalStruct> => {
  let c: Component<SearchModalStruct>;
  let m: ComponentModel<SearchModalStruct>;

  const def: ComponentDef<SearchModalStruct> = {
    regType: 'SearchModal',
    props: {
      isOpen: false,
      onClose: () => {},
      query: '',
      activeTypeFilter: 'all',
      results: [],
      loading: false,
      data: null,
    },
    actions: {
      open: () => {
        m.isOpen = true;
      },
      close: () => {
        m.isOpen = false;
        m.onClose();
      },
      performSearch: async (queryText: string) => {
        m.query = queryText;
        const q = queryText.trim().toLowerCase();
        if (!q) {
          m.results = [];
          return;
        }
        m.loading = true;

        const localResults: SearchResultItem[] = [];
        if (m.data) {
          const typeFilter = m.activeTypeFilter;

          // 1. Search KB Articles
          if (typeFilter === 'all' || typeFilter === 'kb') {
            for (const kb of m.data.kb_articles || []) {
              const title = kb.title || kb.slug || kb.id;
              if (
                title.toLowerCase().includes(q) ||
                kb.slug.toLowerCase().includes(q) ||
                (kb.tags && kb.tags.some((t) => t.toLowerCase().includes(q))) ||
                (kb.body && kb.body.toLowerCase().includes(q))
              ) {
                localResults.push({
                  id: kb.id,
                  type: 'kb',
                  title,
                  file_path: kb.file_path || '',
                  score: title.toLowerCase().includes(q) ? 1.0 : 0.7,
                  snippet: kb.body ? kb.body.slice(0, 150) + '...' : title,
                  tags: kb.tags || [],
                });
              }
            }
          }

          // 2. Search Issues
          if (typeFilter === 'all' || typeFilter === 'issue') {
            for (const iss of m.data.issues || []) {
              const title = iss.title || iss.slug || iss.id;
              if (
                title.toLowerCase().includes(q) ||
                iss.slug.toLowerCase().includes(q) ||
                (iss.tags && iss.tags.some((t) => t.toLowerCase().includes(q))) ||
                (iss.body && iss.body.toLowerCase().includes(q))
              ) {
                localResults.push({
                  id: iss.id,
                  type: 'issue',
                  title,
                  file_path: iss.file_path || '',
                  score: title.toLowerCase().includes(q) ? 1.0 : 0.7,
                  snippet: iss.body ? iss.body.slice(0, 150) + '...' : title,
                  tags: iss.tags || [],
                });
              }
            }
          }

          // 3. Search Decisions
          if (typeFilter === 'all' || typeFilter === 'decision') {
            for (const dec of m.data.decisions || []) {
              const title = dec.title || dec.id;
              if (
                title.toLowerCase().includes(q) ||
                dec.id.toLowerCase().includes(q) ||
                (dec.raw_markdown && dec.raw_markdown.toLowerCase().includes(q))
              ) {
                localResults.push({
                  id: dec.id,
                  type: 'decision',
                  title,
                  file_path: dec.file_path || '.along/DECISIONS.md',
                  score: title.toLowerCase().includes(q) ? 1.0 : 0.7,
                  snippet: dec.decision || (dec.raw_markdown ? dec.raw_markdown.slice(0, 150) + '...' : title),
                  tags: [],
                });
              }
            }
          }

          // 4. Search Sessions
          if (typeFilter === 'all' || typeFilter === 'session') {
            for (const sess of m.data.sessions || []) {
              const title = sess.slug || sess.id;
              if (
                title.toLowerCase().includes(q) ||
                sess.slug.toLowerCase().includes(q) ||
                (sess.summary && sess.summary.toLowerCase().includes(q)) ||
                (sess.body && sess.body.toLowerCase().includes(q))
              ) {
                localResults.push({
                  id: sess.id,
                  type: 'session',
                  title,
                  file_path: sess.file_path || '',
                  score: title.toLowerCase().includes(q) ? 1.0 : 0.7,
                  snippet: sess.summary || (sess.body ? sess.body.slice(0, 150) + '...' : title),
                  tags: [],
                });
              }
            }
          }
        }

        try {
          const typeParam = m.activeTypeFilter === 'all' ? undefined : m.activeTypeFilter;
          const msgResp = await c.msgBus.request({
            channel: 'API.DASHBOARD.SEARCHKB',
            payload: [queryText, undefined, typeParam as any],
          });
          const resp = msgResp.payload;
          if (resp?.results && resp.results.length > 0) {
            m.results = resp.results;
          } else {
            m.results = localResults;
          }
        } catch {
          m.results = localResults;
        } finally {
          m.loading = false;
        }
      },
      selectResult: (r: SearchResultItem) => {
        c.msgBus.send({
          channel: 'APP.ENTITY.SELECT',
          payload: { id: r.id, type: r.type },
        });
        m.close();
      },
    },
    msgBroker: {
      subscribe: {
        'APP.SEARCH.OPEN': {
          in: {
            callback: () => {
              m.isOpen = true;
            },
          },
        },
        'APP.SEARCH.CLOSE': {
          in: {
            callback: () => {
              m.isOpen = false;
            },
          },
        },
      },
    },
    view: () => {
      return (
        <Dialog
          open={Boolean(m.isOpen)}
          onClose={() => m.close()}
          maxWidth="md"
          fullWidth
          sx={{
            zIndex: 1400,
            '& .MuiDialog-paper': {
              backgroundColor: '#0f172a',
              color: '#f8fafc',
              backgroundImage: 'none',
              borderRadius: '16px',
              border: '1px solid #1e293b',
              overflow: 'hidden',
              margin: '16px',
            },
            '& .MuiBackdrop-root': {
              backgroundColor: 'rgba(2, 6, 23, 0.8)',
              backdropFilter: 'blur(4px)',
            },
          }}
        >
          <div className="bg-slate-900 text-slate-100 p-0 flex flex-col max-h-[80vh]">
            {/* Search Bar Input */}
            <div className="flex items-center px-4 py-3.5 border-b border-slate-800 gap-3">
              <Icon icon="lucide:search" className="w-5 h-5 text-sky-400 shrink-0" />
              <input
                type="text"
                autoFocus
                value={m.query}
                onChange={(e) => m.performSearch(e.target.value)}
                placeholder="Search across Knowledge Base, Issues, ADR decisions..."
                className="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm focus:outline-none"
              />
              {m.loading && (
                <Icon icon="lucide:loader-2" className="w-4 h-4 text-sky-400 animate-spin shrink-0" />
              )}
              <button
                type="button"
                onClick={() => m.close()}
                className="text-slate-500 hover:text-slate-300 p-1 rounded-lg cursor-pointer transition"
                title="Close modal (Esc)"
              >
                <Icon icon="lucide:x" className="w-4 h-4" />
              </button>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 px-4 py-2 bg-slate-950/60 border-b border-slate-800 text-[10px] font-mono">
              <span className="text-slate-500 mr-1">Filter:</span>
              {['all', 'kb', 'issue', 'decision', 'session'].map((t) => (
                <button
                  type="button"
                  key={t}
                  onClick={() => {
                    m.activeTypeFilter = t;
                    if (m.query) {
                      m.performSearch(m.query);
                    }
                  }}
                  className={`px-2 py-0.5 rounded uppercase cursor-pointer transition ${
                    m.activeTypeFilter === t
                      ? 'bg-sky-600 text-white font-bold'
                      : 'bg-slate-900 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>

            {/* Results List */}
            <div className="overflow-y-auto p-3 space-y-2 flex-1 max-h-[55vh]">
              {m.results.map((r) => (
                <div
                  key={r.id}
                  onClick={() => m.selectResult(r)}
                  className="p-3 bg-slate-950 border border-slate-800/80 hover:border-sky-500/50 rounded-xl cursor-pointer transition group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono uppercase px-1.5 py-0.2 rounded bg-slate-900 text-sky-400 border border-slate-800">
                        {r.type}
                      </span>
                      <h4 className="text-xs font-bold text-slate-200 group-hover:text-sky-300 transition">
                        {r.title}
                      </h4>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono">{r.file_path}</span>
                  </div>
                  {r.snippet && (
                    <p className="text-xs text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">
                      {r.snippet}
                    </p>
                  )}
                </div>
              ))}

              {m.query.trim() && !m.loading && m.results.length === 0 && (
                <div className="py-12 text-center text-xs text-slate-500 font-mono italic">
                  No results found for "{m.query}"
                </div>
              )}

              {!m.query.trim() && (
                <div className="py-8 text-center text-xs text-slate-500 font-mono">
                  Type to start searching knowledge base topics, issues, decisions, and sessions.
                </div>
              )}
            </div>
          </div>
        </Dialog>
      );
    },
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const SearchModal = toReact(useSearchModal);
