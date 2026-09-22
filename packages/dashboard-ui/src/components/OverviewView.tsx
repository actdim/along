import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { Icon } from '@iconify/react';
import { FullDashboardData } from '../types';
import { DashboardAppMsgStruct, DashboardMsgChannels } from '../bus';

export type OverviewViewStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      data: FullDashboardData | null;
    };
    msgScope: {
      publish: DashboardMsgChannels<'APP.ENTITY.SELECT' | 'APP.TAB.SET'>;
    };
    actions: {
      selectEntity: (id: string, type?: string) => void;
      switchTab: (tab: string) => void;
    };
  }
>;

export const useOverviewView = (
  params?: ComponentParams<OverviewViewStruct>
): Component<OverviewViewStruct> => {
  let c: Component<OverviewViewStruct>;
  let m: ComponentModel<OverviewViewStruct>;

  const def: ComponentDef<OverviewViewStruct> = {
    regType: 'OverviewView',
    props: {
      data: null,
    },
    actions: {
      selectEntity: (id: string, type?: string) => {
        c.msgBus.send({
          channel: 'APP.ENTITY.SELECT',
          payload: { id, type },
        });
      },
      switchTab: (tab: string) => {
        c.msgBus.send({
          channel: 'APP.TAB.SET',
          payload: tab,
        });
      },
    },
    view: () => {
      if (!m.data) return null;
      const { metrics, issues, risks, sessions, kb_articles } = m.data;
      const activeIssues = issues.filter(
        (i) => i.status === 'in-progress' || i.status === 'open' || i.status === 'blocked'
      );

      return (
        <div className="space-y-6">
          {/* Top Metric KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Completion */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium">Issue Completion</span>
                <Icon icon="lucide:check-circle-2" className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-slate-100">{metrics.completion_pct}%</span>
                <span className="text-xs text-slate-400 font-mono">
                  ({metrics.done_issues}/{metrics.total_issues})
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 mt-3 overflow-hidden">
                <div
                  className="bg-emerald-400 h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${metrics.completion_pct}%` }}
                />
              </div>
            </div>

            {/* In-Progress & Active Pipeline */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium">Active Pipeline</span>
                <Icon icon="lucide:flame" className="w-5 h-5 text-amber-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-amber-400">
                  {metrics.open_issues + metrics.in_progress_issues}
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  {metrics.in_progress_issues} in progress, {metrics.open_issues} open
                </span>
              </div>
              <div className="mt-3 flex gap-2 text-xs font-mono text-slate-400">
                <span className="text-amber-400">{metrics.by_type.feat} feats</span>
                <span>&bull;</span>
                <span className="text-rose-400">{metrics.by_type.bug} bugs</span>
                <span>&bull;</span>
                <span className="text-purple-400">{metrics.by_type.debt} debt</span>
              </div>
            </div>

            {/* Knowledge Base */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium">Knowledge Base (KB)</span>
                <Icon icon="lucide:book-marked" className="w-5 h-5 text-sky-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-sky-400">{metrics.total_kb_articles}</span>
                <span className="text-xs text-slate-400 font-mono">topics & guides</span>
              </div>
              <div className="mt-3 text-xs text-slate-400 flex items-center gap-1 font-mono">
                <span>{metrics.total_decisions} ADRs</span>
                <span>&bull;</span>
                <span>{kb_articles.reduce((acc, k) => acc + k.tags.length, 0)} cross-tags</span>
              </div>
            </div>

            {/* Milestones & Risks */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 relative overflow-hidden shadow-sm">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-xs font-medium">Milestones & Risks</span>
                <Icon icon="lucide:shield-alert" className="w-5 h-5 text-indigo-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-indigo-400">{metrics.active_milestones}</span>
                <span className="text-xs text-slate-400 font-mono">
                  milestones, {metrics.active_risks} active risks
                </span>
              </div>
              <div className="mt-3 text-xs text-slate-400 font-mono">
                {risks.length === 0 ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <Icon icon="lucide:check" className="w-3.5 h-3.5" /> No active blockers
                  </span>
                ) : (
                  <span className="text-rose-400">{risks.length} logged risk items</span>
                )}
              </div>
            </div>
          </div>

          {/* Main Grid: Active Sprint & Recent Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Active Issues */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Icon icon="lucide:list-todo" className="w-4 h-4 text-sky-400" />
                  Active Sprint Items ({activeIssues.length})
                </h2>
                <button
                  onClick={() => m.switchTab('issues')}
                  className="text-xs text-sky-400 hover:text-sky-300 font-medium hover:underline flex items-center gap-1"
                >
                  View all issues &rarr;
                </button>
              </div>

              <div className="space-y-2.5">
                {activeIssues.slice(0, 7).map((iss) => (
                  <div
                    key={iss.id}
                    onClick={() => m.selectEntity(iss.id, iss.type)}
                    className="group bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 cursor-pointer transition-all hover:shadow-md flex items-start justify-between gap-4"
                  >
                    <div className="space-y-1.5 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded uppercase ${
                            iss.status === 'in-progress'
                              ? 'bg-amber-950 text-amber-300 border border-amber-800'
                              : iss.status === 'blocked'
                              ? 'bg-rose-950 text-rose-300 border border-rose-800'
                              : 'bg-sky-950 text-sky-300 border border-sky-800'
                          }`}
                        >
                          {iss.status}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                          {iss.type}
                        </span>
                        {iss.priority === 'critical' && (
                          <span className="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded bg-rose-900/60 text-rose-300 border border-rose-700">
                            CRITICAL
                          </span>
                        )}
                        {iss.priority === 'high' && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-300">
                            high
                          </span>
                        )}
                        {iss.milestone && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                            @{iss.milestone}
                          </span>
                        )}
                      </div>
                      <h3 className="text-sm font-semibold text-slate-200 group-hover:text-sky-300 transition truncate">
                        {iss.title || iss.slug}
                      </h3>
                      <div className="text-xs text-slate-400 font-mono flex items-center gap-3">
                        <span>{iss.id}</span>
                        {iss.agent && <span>Agent: {iss.agent}</span>}
                      </div>
                    </div>
                    <Icon icon="lucide:chevron-right" className="w-5 h-5 text-slate-600 group-hover:text-slate-400 shrink-0 mt-1 transition" />
                  </div>
                ))}
              </div>
            </div>

            {/* Right Col: Recent Sessions & Topics */}
            <div className="space-y-6">
              {/* Sessions */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                    <Icon icon="lucide:history" className="w-4 h-4 text-emerald-400" />
                    Recent Sessions
                  </h2>
                  <button
                    onClick={() => m.switchTab('sessions')}
                    className="text-xs text-emerald-400 hover:underline"
                  >
                    All &rarr;
                  </button>
                </div>

                <div className="space-y-2">
                  {sessions.slice(0, 3).map((sess) => (
                    <div
                      key={sess.id}
                      onClick={() => m.selectEntity(sess.id, 'session')}
                      className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3.5 cursor-pointer transition"
                    >
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span className="font-bold text-sky-400">{sess.date}</span>
                        <span className="text-slate-400">{sess.agent}</span>
                      </div>
                      <p className="text-xs text-slate-300 mt-1.5 line-clamp-2 font-medium">
                        {sess.summary || 'Session work log'}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Topics */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                    <Icon icon="lucide:book-open" className="w-4 h-4 text-sky-400" />
                    Knowledge Base Topics
                  </h2>
                  <button
                    onClick={() => m.switchTab('kb')}
                    className="text-xs text-sky-400 hover:underline"
                  >
                    Explorer &rarr;
                  </button>
                </div>

                <div className="space-y-2">
                  {kb_articles.slice(0, 4).map((kb) => (
                    <div
                      key={kb.id}
                      onClick={() => m.selectEntity(kb.id, 'kb')}
                      className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-3 cursor-pointer transition flex items-center justify-between"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="text-xs font-bold text-slate-200 truncate">{kb.title}</div>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">{kb.slug}.md</div>
                      </div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono shrink-0">
                        {kb.type}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    },
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const OverviewView = toReact(useOverviewView);
