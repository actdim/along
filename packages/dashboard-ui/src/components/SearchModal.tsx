import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { useDialog, type DialogStruct } from '@actdim/dynstruct-mui/Dialog';
import { bindProp } from '@actdim/dynstruct/componentModel/core';
import { tw } from '@actdim/ui-core/theme';
import { SearchResultItem, FullDashboardData } from '../types';
import { DashboardAppMsgStruct, DashboardMsgChannels } from '../bus';

export type SearchModalStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      isOpen: boolean;
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
    children: {
      dialog: DialogStruct;
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
            group: 'in',
            payload: [queryText, undefined, typeParam],
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
    children: {
      dialog: useDialog({
        open: bindProp(() => m, 'isOpen'),
        onClose: () => {
          m.close();
        },
        maxWidth: 'md',
        fullWidth: true,
        sx: {
          zIndex: 1400,
          '& .MuiDialog-paper': {
            backgroundColor: 'var(--color-surface-panel)',
            color: 'var(--color-fg-default)',
            backgroundImage: 'none',
            borderRadius: '16px',
            border: '1px solid var(--color-line-default)',
            overflow: 'hidden',
            margin: '16px',
          },
          '& .MuiBackdrop-root': {
            backgroundColor: 'var(--color-surface-scrim)',
            backdropFilter: 'blur(4px)',
          },
        },
        content: () => (
          <div className={tw('bg-surface-panel text-fg-default p-0 flex flex-col max-h-[80vh]')}>
            {/* Search Bar Input */}
            <div className={tw('flex items-center px-relaxed py-normal border-b border-line-default gap-normal')}>
              <span className={`iconify lucide--search ${tw('size-icon-md shrink-0')}`} />
              <input
                type="text"
                autoFocus
                value={m.query}
                onChange={(e) => {
                  m.performSearch(e.target.value);
                }}
                placeholder="Search across Knowledge Base, Issues, ADR decisions..."
                className={tw('w-full bg-transparent text-fg-default placeholder-fg-muted text-body focus:outline-none')}
              />
              {m.loading && (
                <span className={`iconify lucide--loader-2 ${tw('size-icon-sm animate-spin shrink-0')}`} />
              )}
              <button
                type="button"
                onClick={() => {
                  m.close();
                }}
                className={tw('text-fg-muted hover:text-fg-default p-tight rounded-control cursor-pointer transition')}
                title="Close modal (Esc)"
              >
                <span className="iconify lucide--x size-icon-sm" />
              </button>
            </div>

            {/* Filter Pills */}
            <div className={tw('flex items-center gap-tight px-relaxed py-snug bg-surface-inset border-b border-line-default text-micro font-code')}>
              <span className={tw('text-fg-muted mr-tight')}>Filter:</span>
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
                  className={`${tw('px-snug py-micro rounded-control uppercase cursor-pointer transition')} ${
                    m.activeTypeFilter === t
                      ? tw('bg-primary text-primary-contrast font-emphasis')
                      : tw('bg-surface-panel text-fg-muted hover:text-fg-default')
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>

            {/* Results List */}
            <div className={tw('overflow-y-auto p-normal space-y-snug flex-1 max-h-[55vh]')}>
              {m.results.map((r) => (
                <div
                  key={r.id}
                  onClick={() => {
                    m.selectResult(r);
                  }}
                  className={tw('p-normal bg-surface-inset border border-line-default hover:border-line-strong rounded-panel cursor-pointer transition group')}
                >
                  <div className={tw('flex items-center justify-between')}>
                    <div className={tw('flex items-center gap-snug')}>
                      <span className={tw('text-micro font-code uppercase px-tight py-micro rounded-control bg-surface-panel text-primary border border-line-default')}>
                        {r.type}
                      </span>
                      <h4 className={tw('text-caption font-emphasis text-fg-default group-hover:text-primary transition')}>
                        {r.title}
                      </h4>
                    </div>
                    <span className={tw('text-micro text-fg-muted font-code')}>{r.file_path}</span>
                  </div>
                  {r.snippet && (
                    <p className={tw('text-caption text-fg-muted mt-snug line-clamp-2 leading-relaxed')}>
                      {r.snippet}
                    </p>
                  )}
                </div>
              ))}

              {m.query.trim() && !m.loading && m.results.length === 0 && (
                <div className={tw('py-spacious text-center text-caption text-fg-muted font-code italic')}>
                  No results found for "{m.query}"
                </div>
              )}

              {!m.query.trim() && (
                <div className={tw('py-loose text-center text-caption text-fg-muted font-code')}>
                  Type to start searching knowledge base topics, issues, decisions, and sessions.
                </div>
              )}
            </div>
          </div>
        ),
      }),
    },
    view: () => <c.children.Dialog />,
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const SearchModal = toReact(useSearchModal);
