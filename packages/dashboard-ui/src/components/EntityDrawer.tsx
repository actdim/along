import React from 'react';
import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { type BaseAppMsgStruct } from '@actdim/dynstruct/appDomain/appContracts';
import { useDrawer, type DrawerStruct } from '@actdim/dynstruct-mui/Drawer';
import { bind } from '@actdim/dynstruct/componentModel/core';
import { Icon } from '@iconify/react';
import { marked } from 'marked';
import {
  type Issue,
  type Milestone,
  type Risk,
  type Spike,
  type Session,
  type Decision,
  type KBArticle,
  type FullDashboardData,
} from '../types';

export type DrawerEntity =
  | (Issue & { entityType: 'issue' })
  | (Milestone & { entityType: 'milestone' })
  | (Risk & { entityType: 'risk' })
  | (Spike & { entityType: 'spike' })
  | (Session & { entityType: 'session' })
  | (KBArticle & { entityType: 'kb' })
  | (Decision & { entityType: 'decision'; body?: string });

interface WindowWithMermaid {
  mermaid?: {
    run: (options: { nodes: NodeListOf<Element> }) => void;
  };
}

export type MarkdownContentStruct = ComponentStruct<
  BaseAppMsgStruct,
  {
    props: {
      html: string;
    };
    actions: {
      renderMermaid: () => void;
    };
  }
>;

export const useMarkdownContent = (
  params?: ComponentParams<MarkdownContentStruct>
): Component<MarkdownContentStruct> => {
  let c: Component<MarkdownContentStruct>;
  let m: ComponentModel<MarkdownContentStruct>;

  const def: ComponentDef<MarkdownContentStruct> = {
    regType: 'MarkdownContent',
    props: {
      html: '',
    },
    actions: {
      renderMermaid: () => {
        const container = document.getElementById(c.id);
        if (!container) return;

        const w = window as unknown as WindowWithMermaid;
        if (!w.mermaid) return;

        const codeBlocks = container.querySelectorAll('pre code.language-mermaid');
        if (codeBlocks.length === 0) return;

        codeBlocks.forEach((codeEl) => {
          const preEl = codeEl.parentElement;
          if (!preEl) return;
          const div = document.createElement('div');
          div.className =
            'mermaid my-4 p-4 bg-slate-950 rounded-xl border border-slate-800 flex justify-center overflow-x-auto text-slate-200';
          div.textContent = codeEl.textContent;
          preEl.replaceWith(div);
        });

        try {
          const mermaidNodes = container.querySelectorAll('.mermaid');
          if (mermaidNodes.length > 0) {
            w.mermaid.run({ nodes: mermaidNodes });
          }
        } catch (err) {
          console.warn('Mermaid rendering error:', err);
        }
      },
    },
    events: {
      onLayoutReady: () => {
        m.renderMermaid();
      },
      onChangeHtml: () => {
        m.renderMermaid();
      },
    },
    view: () => (
      <div
        id={c.id}
        className="markdown-body prose prose-invert max-w-none text-slate-300 text-xs leading-relaxed"
        dangerouslySetInnerHTML={{
          __html: m.html || '<p class="italic text-slate-500">No content provided.</p>',
        }}
      />
    ),
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const MarkdownContent = toReact(useMarkdownContent);

export type EntityDrawerStruct = ComponentStruct<
  BaseAppMsgStruct,
  {
    props: {
      data: FullDashboardData | null;
      selectedEntityId: string | null;
      onClose: () => void;
      readonly entity: DrawerEntity | null;
      readonly renderedBody: string;
    };
    children: {
      drawer: DrawerStruct;
      markdownContent: MarkdownContentStruct;
    };
  }
>;

export const useEntityDrawer = (
  params?: ComponentParams<EntityDrawerStruct>
): Component<EntityDrawerStruct> => {
  let c: Component<EntityDrawerStruct>;
  let m: ComponentModel<EntityDrawerStruct>;

  const def: ComponentDef<EntityDrawerStruct> = {
    regType: 'EntityDrawer',
    props: {
      data: null,
      selectedEntityId: null,
      onClose: () => {},
      get entity(): DrawerEntity | null {
        if (!m.data || !m.selectedEntityId) return null;
        const id = m.selectedEntityId;

        const iss = m.data.issues.find((i) => i.id === id || i.slug === id);
        if (iss) return { ...iss, entityType: 'issue' as const };

        const mil = m.data.milestones.find((ml) => ml.id === id || ml.slug === id);
        if (mil) return { ...mil, entityType: 'milestone' as const };

        const r = m.data.risks.find((rk) => rk.id === id || rk.slug === id);
        if (r) return { ...r, entityType: 'risk' as const };

        const sp = m.data.spikes.find((s) => s.id === id || s.slug === id);
        if (sp) return { ...sp, entityType: 'spike' as const };

        const sess = m.data.sessions.find((s) => s.id === id || s.slug === id);
        if (sess) return { ...sess, entityType: 'session' as const };

        const kb = m.data.kb_articles.find((k) => k.id === id || k.slug === id);
        if (kb) return { ...kb, entityType: 'kb' as const };

        const dec = m.data.decisions.find((d) => d.id === id);
        if (dec) return { ...dec, entityType: 'decision' as const, body: dec.raw_markdown };

        return null;
      },
      get renderedBody() {
        const ent = m.entity;
        if (!ent || !ent.body) return '';
        try {
          return marked.parse(ent.body) as string;
        } catch {
          return ent.body;
        }
      },
    },
    children: {
      drawer: useDrawer({
        anchor: 'right',
        open: bind(() => Boolean(m.selectedEntityId)),
        onClose: bind(() => m.onClose),
        sx: {
          '& .MuiDrawer-paper': {
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            backgroundImage: 'none',
            borderLeft: '1px solid #1e293b',
          },
        },
        children: () => {
          const ent = m.entity;
          if (!ent) return null;

          const title =
            ('title' in ent && ent.title) ||
            ('summary' in ent && ent.summary) ||
            ent.slug ||
            ent.id;

          return (
            <div className="w-full sm:w-[600px] bg-slate-900 text-slate-100 p-6 min-h-full flex flex-col justify-between">
              <div className="space-y-6">
                {/* Header */}
                <div className="flex items-start justify-between border-b border-slate-800 pb-4">
                  <div>
                    <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-sky-400 border border-slate-700">
                      {ent.entityType}
                    </span>
                    <h2 className="text-xl font-bold text-slate-100 mt-2 tracking-tight">
                      {title}
                    </h2>
                  </div>
                  <button
                    onClick={m.onClose}
                    className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
                  >
                    <Icon icon="lucide:x" className="w-5 h-5" />
                  </button>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-3 text-xs text-slate-400 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                  {'status' in ent && ent.status && (
                    <div>
                      Status: <span className="text-slate-200 font-bold">{ent.status}</span>
                    </div>
                  )}
                  {'priority' in ent && ent.priority && (
                    <div>
                      Priority: <span className="text-slate-200 font-bold">{ent.priority}</span>
                    </div>
                  )}
                  {'type' in ent && ent.type && (
                    <div>
                      Type: <span className="text-slate-200 font-mono">{ent.type}</span>
                    </div>
                  )}
                  {'agent' in ent && ent.agent && (
                    <div>
                      Agent: <span className="text-slate-200">{ent.agent}</span>
                    </div>
                  )}
                  {'created' in ent && ent.created && (
                    <div>
                      Created: <span className="text-slate-200">{ent.created}</span>
                    </div>
                  )}
                  {'completed' in ent && ent.completed && (
                    <div>
                      Completed: <span className="text-emerald-400 font-bold">{ent.completed}</span>
                    </div>
                  )}
                  {'file_path' in ent && ent.file_path && (
                    <div className="col-span-2">
                      File: <span className="text-sky-400">{ent.file_path}</span>
                    </div>
                  )}
                </div>

                {/* Tags */}
                {'tags' in ent && Array.isArray(ent.tags) && ent.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {ent.tags.map((t: string) => (
                      <span
                        key={t}
                        className="text-xs font-mono px-2 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                )}

                {/* Content */}
                <div className="border-t border-slate-800 pt-4">
                  <h3 className="text-xs font-bold font-mono uppercase text-slate-400 mb-3">
                    Description & Content
                  </h3>
                  <c.children.MarkdownContent />
                </div>
              </div>

              <div className="border-t border-slate-800 pt-4 mt-6 flex justify-end">
                <button
                  onClick={m.onClose}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium transition"
                >
                  Close
                </button>
              </div>
            </div>
          );
        },
      }),
      markdownContent: useMarkdownContent({
        html: bind(() => m.renderedBody),
      }),
    },
    view: () => <c.children.Drawer />,
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const EntityDrawer = toReact(useEntityDrawer);
