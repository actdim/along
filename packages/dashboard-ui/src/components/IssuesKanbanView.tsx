import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { Icon } from '@iconify/react';
import { Issue } from '../types';
import { DashboardAppMsgStruct, DashboardMsgChannels } from '../bus';

export type IssuesViewStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      issues: Issue[];
      searchQuery: string;
      statusFilter: string;
      typeFilter: string;
      priorityFilter: string;
      viewMode: 'table' | 'kanban';
      readonly filteredIssues: Issue[];
    };
    msgScope: {
      publish: DashboardMsgChannels<'APP.ENTITY.SELECT'>;
    };
    actions: {
      selectIssue: (id: string, type: string) => void;
    };
  }
>;

export const useIssuesView = (
  params?: ComponentParams<IssuesViewStruct>
): Component<IssuesViewStruct> => {
  let c: Component<IssuesViewStruct>;
  let m: ComponentModel<IssuesViewStruct>;

  const def: ComponentDef<IssuesViewStruct> = {
    regType: 'IssuesView',
    props: {
      issues: [],
      searchQuery: '',
      statusFilter: 'all',
      typeFilter: 'all',
      priorityFilter: 'all',
      viewMode: 'table',
      get filteredIssues() {
        const q = m.searchQuery.toLowerCase();
        return m.issues.filter((iss) => {
          const matchQuery =
            !q ||
            (iss.title && iss.title.toLowerCase().includes(q)) ||
            iss.slug.toLowerCase().includes(q) ||
            iss.id.toLowerCase().includes(q) ||
            iss.tags.some((t) => t.toLowerCase().includes(q));

          const matchStatus = m.statusFilter === 'all' || iss.status === m.statusFilter;
          const matchType = m.typeFilter === 'all' || iss.type === m.typeFilter;
          const matchPrio = m.priorityFilter === 'all' || iss.priority === m.priorityFilter;

          return matchQuery && matchStatus && matchType && matchPrio;
        });
      },
    },
    actions: {
      selectIssue: (id: string, type: string) => {
        c.msgBus.send({
          channel: 'APP.ENTITY.SELECT',
          payload: { id, type },
        });
      },
    },
    view: () => {
      const columns: Array<{ id: 'open' | 'in-progress' | 'blocked' | 'done'; label: string; color: string }> = [
        { id: 'open', label: 'Open / Backlog', color: 'border-slate-700 text-slate-300' },
        { id: 'in-progress', label: 'In Progress', color: 'border-amber-700/60 text-amber-300' },
        { id: 'blocked', label: 'Blocked', color: 'border-rose-700/60 text-rose-300' },
        { id: 'done', label: 'Done (Completed)', color: 'border-emerald-700/60 text-emerald-300' },
      ];

      return (
        <div className="space-y-4">
          {/* Controls and Filters Bar */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
            {/* Search input */}
            <div className="relative w-full md:w-72">
              <Icon icon="lucide:search" className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={m.searchQuery}
                onChange={(e) => {
                  m.searchQuery = e.target.value;
                }}
                placeholder="Filter issues..."
                className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
              />
            </div>

            {/* Filter Dropdowns */}
            <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
              <select
                value={m.statusFilter}
                onChange={(e) => {
                  m.statusFilter = e.target.value;
                }}
                className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-sky-500"
              >
                <option value="all">All Statuses</option>
                <option value="open">Open</option>
                <option value="in-progress">In Progress</option>
                <option value="blocked">Blocked</option>
                <option value="done">Done</option>
              </select>

              <select
                value={m.typeFilter}
                onChange={(e) => {
                  m.typeFilter = e.target.value;
                }}
                className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-sky-500"
              >
                <option value="all">All Types</option>
                <option value="feat">Feature (feat)</option>
                <option value="bug">Bug (bug)</option>
                <option value="debt">Tech Debt (debt)</option>
                <option value="task">Task (task)</option>
                <option value="docs">Docs (docs)</option>
              </select>

              <select
                value={m.priorityFilter}
                onChange={(e) => {
                  m.priorityFilter = e.target.value;
                }}
                className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-sky-500"
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>

              {/* View Mode Toggle */}
              <div className="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-0.5 ml-auto">
                <button
                  onClick={() => {
                    m.viewMode = 'table';
                  }}
                  className={`p-1.5 rounded-lg text-xs transition ${
                    m.viewMode === 'table' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Table View"
                >
                  <Icon icon="lucide:table" className="w-4 h-4" />
                </button>
                <button
                  onClick={() => {
                    m.viewMode = 'kanban';
                  }}
                  className={`p-1.5 rounded-lg text-xs transition ${
                    m.viewMode === 'kanban' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Kanban Board"
                >
                  <Icon icon="lucide:columns" className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* View Output */}
          {m.viewMode === 'table' ? (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
                    <tr>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Type</th>
                      <th className="py-3 px-4">Priority</th>
                      <th className="py-3 px-4">Title / ID</th>
                      <th className="py-3 px-4">Milestone</th>
                      <th className="py-3 px-4">Tags</th>
                      <th className="py-3 px-4 text-right">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-slate-300">
                    {m.filteredIssues.map((iss) => (
                      <tr
                        key={iss.id}
                        onClick={() => m.selectIssue(iss.id, iss.type)}
                        className="hover:bg-slate-800/60 cursor-pointer transition"
                      >
                        <td className="py-3 px-4">
                          <span
                            className={`font-mono text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${
                              iss.status === 'done'
                                ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                                : iss.status === 'in-progress'
                                ? 'bg-amber-950 text-amber-300 border-amber-800'
                                : iss.status === 'blocked'
                                ? 'bg-rose-950 text-rose-300 border-rose-800'
                                : 'bg-slate-800 text-slate-300 border-slate-700'
                            }`}
                          >
                            {iss.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono">{iss.type}</td>
                        <td className="py-3 px-4 font-mono">
                          <span
                            className={`${
                              iss.priority === 'critical'
                                ? 'text-rose-400 font-bold'
                                : iss.priority === 'high'
                                ? 'text-amber-400'
                                : 'text-slate-400'
                            }`}
                          >
                            {iss.priority}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-100">{iss.title || iss.slug}</div>
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{iss.id}</div>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-400">
                          {iss.milestone ? `@${iss.milestone}` : '-'}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-1">
                            {iss.tags.slice(0, 3).map((t) => (
                              <span
                                key={t}
                                className="text-[10px] font-mono px-1.5 py-0.2 bg-slate-950 text-slate-400 border border-slate-800 rounded"
                              >
                                #{t}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right font-mono text-slate-400">
                          {iss.updated || iss.created || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {columns.map((col) => {
                const colIssues = m.filteredIssues.filter((i) => i.status === col.id);
                return (
                  <div key={col.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col">
                    <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                      <h3 className={`text-xs font-bold uppercase tracking-wider ${col.color}`}>{col.label}</h3>
                      <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
                        {colIssues.length}
                      </span>
                    </div>
                    <div className="space-y-3 flex-1 overflow-y-auto max-h-[680px] pr-1">
                      {colIssues.map((iss) => (
                        <div
                          key={iss.id}
                          onClick={() => m.selectIssue(iss.id, iss.type)}
                          className="bg-slate-950 border border-slate-800/80 hover:border-slate-700 rounded-xl p-3.5 cursor-pointer transition hover:shadow-md space-y-2"
                        >
                          <div className="flex items-center justify-between text-[10px] font-mono">
                            <span className="text-slate-400 uppercase">{iss.type}</span>
                            <span
                              className={`font-semibold ${
                                iss.priority === 'critical'
                                  ? 'text-rose-400'
                                  : iss.priority === 'high'
                                  ? 'text-amber-400'
                                  : 'text-slate-400'
                              }`}
                            >
                              {iss.priority}
                            </span>
                          </div>
                          <h4 className="text-xs font-bold text-slate-200 line-clamp-2">{iss.title || iss.slug}</h4>
                          {iss.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {iss.tags.slice(0, 2).map((t) => (
                                <span key={t} className="text-[9px] font-mono px-1 py-0.2 bg-slate-900 text-slate-400 rounded">
                                  #{t}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                      {colIssues.length === 0 && (
                        <div className="text-center text-xs text-slate-600 py-8 italic font-mono">No issues in column</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      );
    },
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const IssuesKanbanView = toReact(useIssuesView);
