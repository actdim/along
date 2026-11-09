import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { tw } from '@actdim/ui-core/theme';
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
        { id: 'open', label: 'Open / Backlog', color: 'text-fg-default' },
        { id: 'in-progress', label: 'In Progress', color: 'text-warning-strong' },
        { id: 'blocked', label: 'Blocked', color: 'text-danger-strong' },
        { id: 'done', label: 'Done (Completed)', color: 'text-success-strong' },
      ];

      return (
        <div className={tw('space-y-normal')}>
          {/* Controls and Filters Bar */}
          <div className={tw('bg-surface-panel border border-line-default rounded-dialog p-normal flex flex-col md:flex-row gap-normal items-center justify-between')}>
            {/* Search input */}
            <div className={`md:w-72 ${tw('relative w-full')}`}>
              <span className={`iconify lucide--search ${tw('size-icon-sm text-fg-muted absolute left-snug top-snug')}`} />
              <input
                type="text"
                value={m.searchQuery}
                onChange={(e) => {
                  m.searchQuery = e.target.value;
                }}
                placeholder="Filter issues..."
                className={tw('w-full pl-spacious pr-normal py-tight bg-surface-inset border border-line-default rounded-control text-caption text-fg-default placeholder-fg-muted focus:outline-none focus:border-focus transition')}
              />
            </div>

            {/* Filter Dropdowns */}
            <div className={tw('flex flex-wrap items-center gap-snug w-full md:w-auto')}>
              <select
                value={m.statusFilter}
                onChange={(e) => {
                  m.statusFilter = e.target.value;
                }}
                className={tw('px-normal py-tight bg-surface-inset border border-line-default rounded-control text-caption text-fg-muted focus:outline-none focus:border-focus')}
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
                className={tw('px-normal py-tight bg-surface-inset border border-line-default rounded-control text-caption text-fg-muted focus:outline-none focus:border-focus')}
              >
                <option value="all">All Types</option>
                <option value="feat">Feature (feat)</option>
                <option value="bug">Bug (bug)</option>
                <option value="debt">Tech Debt (debt)</option>
                <option value="task">Task (task)</option>
                <option value="docs">Docs (docs)</option>
                <option value="spike">Spike (spike)</option>
              </select>

              <select
                value={m.priorityFilter}
                onChange={(e) => {
                  m.priorityFilter = e.target.value;
                }}
                className={tw('px-normal py-tight bg-surface-inset border border-line-default rounded-control text-caption text-fg-muted focus:outline-none focus:border-focus')}
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>

              {/* View Mode Toggle */}
              <div className={tw('flex items-center bg-surface-inset border border-line-default rounded-control p-micro ml-auto')}>
                <button
                  type="button"
                  onClick={() => {
                    m.viewMode = 'table';
                  }}
                  className={`${tw('p-tight rounded-control text-caption transition cursor-pointer')} ${
                    m.viewMode === 'table' ? tw('bg-primary text-primary-contrast') : tw('text-fg-muted hover:text-fg-default')
                  }`}
                  title="Table View"
                >
                  <span className="iconify lucide--table size-icon-sm" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    m.viewMode = 'kanban';
                  }}
                  className={`${tw('p-tight rounded-control text-caption transition cursor-pointer')} ${
                    m.viewMode === 'kanban' ? tw('bg-primary text-primary-contrast') : tw('text-fg-muted hover:text-fg-default')
                  }`}
                  title="Kanban Board"
                >
                  <span className="iconify lucide--columns size-icon-sm" />
                </button>
              </div>
            </div>
          </div>

          {/* View Output */}
          {m.viewMode === 'table' ? (
            <div className={tw('bg-surface-panel border border-line-default rounded-dialog overflow-hidden shadow-panel')}>
              <div className={tw('overflow-x-auto')}>
                <table className={tw('w-full text-left text-caption')}>
                  <thead className={tw('bg-surface-inset text-fg-muted border-b border-line-default font-code')}>
                    <tr>
                      <th className={tw('py-normal px-normal')}>Status</th>
                      <th className={tw('py-normal px-normal')}>Type</th>
                      <th className={tw('py-normal px-normal')}>Priority</th>
                      <th className={tw('py-normal px-normal')}>Title / ID</th>
                      <th className={tw('py-normal px-normal')}>Milestone</th>
                      <th className={tw('py-normal px-normal')}>Tags</th>
                      <th className={tw('py-normal px-normal text-right')}>Updated</th>
                    </tr>
                  </thead>
                  <tbody className={tw('divide-y divide-line-muted text-fg-default')}>
                    {m.filteredIssues.map((iss) => (
                      <tr
                        key={iss.id}
                        onClick={() => {
                          m.selectIssue(iss.id, iss.type);
                        }}
                        className={tw('hover:bg-surface-hover cursor-pointer transition')}
                      >
                        <td className={tw('py-normal px-normal')}>
                          <span
                            className={`${tw('font-code text-micro uppercase font-emphasis px-snug py-micro rounded-control')} ${
                              iss.status === 'done'
                                ? tw('bg-success-soft text-success-strong border border-success-line')
                                : iss.status === 'in-progress'
                                ? tw('bg-warning-soft text-warning-strong border border-warning-line')
                                : iss.status === 'blocked'
                                ? tw('bg-danger-soft text-danger-strong border border-danger-line')
                                : tw('bg-surface-inset text-fg-muted border border-line-default')
                            }`}
                          >
                            {iss.status}
                          </span>
                        </td>
                        <td className={tw('py-normal px-normal font-code')}>{iss.type}</td>
                        <td className={tw('py-normal px-normal font-code')}>
                          <span
                            className={
                              iss.priority === 'critical'
                                ? tw('text-danger-strong font-emphasis')
                                : iss.priority === 'high'
                                ? tw('text-warning-strong')
                                : tw('text-fg-muted')
                            }
                          >
                            {iss.priority}
                          </span>
                        </td>
                        <td className={tw('py-normal px-normal')}>
                          <div className={tw('font-emphasis text-fg-default')}>{iss.title || iss.slug}</div>
                          <div className={tw('text-micro text-fg-muted font-code mt-micro')}>{iss.id}</div>
                        </td>
                        <td className={tw('py-normal px-normal font-code text-fg-muted')}>
                          {iss.milestone ? `@${iss.milestone}` : '-'}
                        </td>
                        <td className={tw('py-normal px-normal')}>
                          <div className={tw('flex flex-wrap gap-tight')}>
                            {iss.tags.slice(0, 3).map((t) => (
                              <span
                                key={t}
                                className={tw('text-micro font-code px-tight py-micro bg-surface-inset text-fg-muted border border-line-default rounded-control')}
                              >
                                #{t}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className={tw('py-normal px-normal text-right font-code text-fg-muted')}>
                          {iss.updated || iss.created || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className={tw('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-normal')}>
              {columns.map((col) => {
                const colIssues = m.filteredIssues.filter((i) => i.status === col.id);
                return (
                  <div key={col.id} className={tw('bg-surface-panel border border-line-default rounded-dialog p-normal flex flex-col')}>
                    <div className={tw('flex items-center justify-between pb-normal border-b border-line-default mb-normal')}>
                      <h3 className={`${tw('text-caption font-emphasis uppercase tracking-wider')} ${col.color}`}>{col.label}</h3>
                      <span className={tw('text-caption font-code px-snug py-micro rounded-full bg-surface-inset text-fg-muted')}>
                        {colIssues.length}
                      </span>
                    </div>
                    <div className={`max-h-[680px] ${tw('space-y-normal flex-1 overflow-y-auto pr-tight')}`}>
                      {colIssues.map((iss) => (
                        <div
                          key={iss.id}
                          onClick={() => {
                            m.selectIssue(iss.id, iss.type);
                          }}
                          className={tw('bg-surface-inset border border-line-default hover:border-line-strong rounded-panel p-normal cursor-pointer transition hover:shadow-panel space-y-snug')}
                        >
                          <div className={tw('flex items-center justify-between text-micro font-code')}>
                            <span className={tw('text-fg-muted uppercase')}>{iss.type}</span>
                            <span
                              className={
                                iss.priority === 'critical'
                                  ? tw('text-danger-strong font-emphasis')
                                  : iss.priority === 'high'
                                  ? tw('text-warning-strong')
                                  : tw('text-fg-muted')
                              }
                            >
                              {iss.priority}
                            </span>
                          </div>
                          <h4 className={tw('text-caption font-emphasis text-fg-default line-clamp-2')}>{iss.title || iss.slug}</h4>
                          {iss.tags.length > 0 && (
                            <div className={tw('flex flex-wrap gap-tight')}>
                              {iss.tags.slice(0, 2).map((t) => (
                                <span key={t} className={tw('text-micro font-code px-tight py-micro bg-surface-panel text-fg-muted rounded-control')}>
                                  #{t}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                      {colIssues.length === 0 && (
                        <div className={tw('text-center text-caption text-fg-faint py-loose italic font-code')}>No issues in column</div>
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
