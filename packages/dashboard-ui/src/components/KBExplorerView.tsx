import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { Icon } from '@iconify/react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { KBArticle } from '../types';
import { DashboardAppMsgStruct, DashboardMsgChannels } from '../bus';

export type KBViewStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      articles: KBArticle[];
      selectedSlug: string;
      searchQuery: string;
      categoryFilter: string;
      readonly filteredArticles: KBArticle[];
      readonly activeArticle: KBArticle | null;
      readonly renderedHtml: string;
    };
    msgScope: {
      publish: DashboardMsgChannels<'APP.ENTITY.SELECT'>;
    };
    actions: {
      selectArticle: (slug: string) => void;
      inspectInDrawer: (id: string) => void;
      selectEntity: (id: string) => void;
    };
  }
>;

export const useKBView = (params?: ComponentParams<KBViewStruct>): Component<KBViewStruct> => {
  let c: Component<KBViewStruct>;
  let m: ComponentModel<KBViewStruct>;

  const def: ComponentDef<KBViewStruct> = {
    regType: 'KBView',
    props: {
      articles: [],
      selectedSlug: '',
      searchQuery: '',
      categoryFilter: 'all',
      get filteredArticles() {
        const q = m.searchQuery.toLowerCase();
        return m.articles.filter((a) => {
          const matchQ =
            !q ||
            a.title.toLowerCase().includes(q) ||
            a.slug.toLowerCase().includes(q) ||
            (a.body || '').toLowerCase().includes(q) ||
            a.tags.some((t) => t.toLowerCase().includes(q));

          const matchCat = m.categoryFilter === 'all' || a.type === m.categoryFilter;
          return matchQ && matchCat;
        });
      },
      get activeArticle() {
        if (!m.articles || m.articles.length === 0) return null;
        if (!m.selectedSlug) return m.articles[0];
        return m.articles.find((a) => a.slug === m.selectedSlug) || m.articles[0] || null;
      },
      get renderedHtml() {
        const art = m.activeArticle;
        if (!art || !art.body) return '';
        try {
          const parsed = marked.parse(art.body);
          return DOMPurify.sanitize(typeof parsed === 'string' ? parsed : String(parsed));
        } catch {
          return DOMPurify.sanitize(art.body);
        }
      },
    },
    actions: {
      selectArticle: (slug: string) => {
        m.selectedSlug = slug;
      },
      inspectInDrawer: (id: string) => {
        c.msgBus.send({
          channel: 'APP.ENTITY.SELECT',
          payload: { id, type: 'kb' },
        });
      },
      selectEntity: (id: string) => {
        c.msgBus.send({
          channel: 'APP.ENTITY.SELECT',
          payload: { id },
        });
      },
    },
    view: () => {
      const categories = [
        { id: 'all', label: 'All Articles' },
        { id: 'architecture', label: 'Architecture' },
        { id: 'domain-model', label: 'Domain Model' },
        { id: 'setup-workflow', label: 'Setup & Workflow' },
        { id: 'topic', label: 'Topics' },
        { id: 'index', label: 'Indexes' },
      ];

      return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Articles Navigation (4 cols) */}
          <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-4 shadow-sm">
            {/* Search */}
            <div className="relative">
              <Icon icon="lucide:search" className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={m.searchQuery}
                onChange={(e) => {
                  m.searchQuery = e.target.value;
                }}
                placeholder="Search KB articles & docs..."
                className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
              />
            </div>

            {/* Category Pills */}
            <div className="flex flex-wrap gap-1.5">
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => {
                    m.categoryFilter = cat.id;
                  }}
                  className={`px-2.5 py-1 rounded-lg text-[10px] font-mono transition ${
                    m.categoryFilter === cat.id
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-bold'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {/* Article List */}
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {m.filteredArticles.map((a) => {
                const isSelected = m.activeArticle?.slug === a.slug;
                return (
                  <div
                    key={a.id}
                    onClick={() => m.selectArticle(a.slug)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition ${
                      isSelected
                        ? 'bg-sky-950/40 border-sky-500/50 shadow-sm'
                        : 'bg-slate-950 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-900 text-slate-400 border border-slate-800">
                        {a.type}
                      </span>
                      {a.updated && <span className="text-[10px] font-mono text-slate-500">{a.updated}</span>}
                    </div>
                    <h4 className="text-xs font-bold text-slate-200 mt-2">{a.title}</h4>
                    <div className="text-[10px] text-slate-500 font-mono mt-1">{a.file_path}</div>
                    {a.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {a.tags.slice(0, 3).map((t) => (
                          <span
                            key={t}
                            className="text-[9px] font-mono px-1 py-0.2 bg-slate-900 text-slate-400 rounded"
                          >
                            #{t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
              {m.filteredArticles.length === 0 && (
                <div className="text-center text-xs text-slate-500 py-8 italic font-mono">
                  No KB articles match filter
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Article Reader (8 cols) */}
          <div className="lg:col-span-8 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm min-h-[680px]">
            {m.activeArticle ? (
              <div className="space-y-6">
                {/* Header */}
                <div className="border-b border-slate-800 pb-5 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800">
                        {m.activeArticle.type}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">{m.activeArticle.file_path}</span>
                    </div>
                    <button
                      onClick={() => m.inspectInDrawer(m.activeArticle!.id)}
                      className="text-xs text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition"
                      title="Inspect Metadata in Drawer"
                    >
                      <Icon icon="lucide:maximize" className="w-4 h-4" />
                    </button>
                  </div>

                  <h2 className="text-2xl font-bold text-slate-100 tracking-tight">
                    {m.activeArticle.title}
                  </h2>

                  {m.activeArticle.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {m.activeArticle.tags.map((t) => (
                        <span
                          key={t}
                          className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-slate-950 text-slate-400 border border-slate-800"
                        >
                          #{t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Outgoing & Wiki Links */}
                {m.activeArticle.outgoing_links.length > 0 && (
                  <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-2">
                      <Icon icon="lucide:link-2" className="w-3.5 h-3.5 text-sky-400" />
                      Referenced Topics & Entities
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {m.activeArticle.outgoing_links.map((link) => (
                        <button
                          key={link}
                          onClick={() => {
                            const target = m.articles.find((a) => a.slug === link || a.title === link);
                            if (target) m.selectArticle(target.slug);
                            else m.selectEntity(link);
                          }}
                          className="text-xs font-mono px-2 py-0.5 bg-slate-900 hover:bg-sky-950 hover:text-sky-300 text-slate-300 border border-slate-800 hover:border-sky-700 rounded transition flex items-center gap-1"
                        >
                          [[{link}]]
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Rendered Markdown Body */}
                <div
                  className="markdown-body prose prose-invert max-w-none text-slate-300 text-sm leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: m.renderedHtml }}
                />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-slate-500 space-y-3">
                <Icon icon="lucide:book-open" className="w-12 h-12 text-slate-600" />
                <p className="text-sm font-medium">Select an article from the left column to read.</p>
              </div>
            )}
          </div>
        </div>
      );
    },
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const KBExplorerView = toReact(useKBView);
