import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { Icon } from '@iconify/react';
import { Session, Decision } from '../types';
import { DashboardAppMsgStruct, DashboardMsgChannels } from '../bus';

export type SessionsViewStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      sessions: Session[];
      decisions: Decision[];
      section: 'sessions' | 'decisions';
    };
    msgScope: {
      publish: DashboardMsgChannels<'APP.ENTITY.SELECT'>;
    };
    actions: {
      setSection: (section: 'sessions' | 'decisions') => void;
      selectEntity: (id: string, type: string) => void;
    };
  }
>;

export const useSessionsView = (
  params?: ComponentParams<SessionsViewStruct>
): Component<SessionsViewStruct> => {
  let c: Component<SessionsViewStruct>;
  let m: ComponentModel<SessionsViewStruct>;

  const def: ComponentDef<SessionsViewStruct> = {
    regType: 'SessionsView',
    props: {
      sessions: [],
      decisions: [],
      section: 'sessions',
    },
    actions: {
      setSection: (section: 'sessions' | 'decisions') => {
        m.section = section;
      },
      selectEntity: (id: string, type: string) => {
        c.msgBus.send({
          channel: 'APP.ENTITY.SELECT',
          payload: { id, type },
        });
      },
    },
    view: () => (
      <div className="space-y-6">
        {/* Section Switcher */}
        <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 p-1.5 rounded-2xl w-fit">
          <button
            onClick={() => m.setSection('sessions')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
              m.section === 'sessions'
                ? 'bg-sky-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Icon icon="lucide:history" className="w-4 h-4" />
            Work Sessions ({m.sessions.length})
          </button>
          <button
            onClick={() => m.setSection('decisions')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
              m.section === 'decisions'
                ? 'bg-sky-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Icon icon="lucide:scale" className="w-4 h-4" />
            Architectural Decisions (ADR) ({m.decisions.length})
          </button>
        </div>

        {m.section === 'sessions' ? (
          <div className="space-y-4">
            {m.sessions.map((sess) => (
              <div
                key={sess.id}
                onClick={() => m.selectEntity(sess.id, 'session')}
                className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 cursor-pointer transition shadow-sm space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold font-mono text-sky-400">{sess.date}</span>
                    {sess.branch && (
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                        branch: {sess.branch}
                      </span>
                    )}
                    {sess.commit && (
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                        commit: {sess.commit}
                      </span>
                    )}
                  </div>
                  <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
                    {sess.agent || 'agent'}
                  </span>
                </div>

                <p className="text-sm text-slate-200 font-medium leading-relaxed">
                  {sess.summary || 'Session work log summary'}
                </p>

                <div className="flex flex-wrap items-center gap-2 pt-1 text-xs font-mono">
                  {sess.issues_completed.length > 0 && (
                    <span className="text-emerald-400 flex items-center gap-1 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/60">
                      <Icon icon="lucide:check-circle" className="w-3.5 h-3.5" />
                      Completed: {sess.issues_completed.join(', ')}
                    </span>
                  )}
                  {sess.issues_advanced.length > 0 && (
                    <span className="text-sky-400 flex items-center gap-1 bg-sky-950/40 px-2 py-0.5 rounded border border-sky-800/60">
                      <Icon icon="lucide:arrow-right" className="w-3.5 h-3.5" />
                      Advanced: {sess.issues_advanced.join(', ')}
                    </span>
                  )}
                  {sess.decisions.length > 0 && (
                    <span className="text-amber-400 flex items-center gap-1 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/60">
                      <Icon icon="lucide:bookmark" className="w-3.5 h-3.5" />
                      ADR: {sess.decisions.join(', ')}
                    </span>
                  )}
                </div>
              </div>
            ))}
            {m.sessions.length === 0 && (
              <div className="text-center text-xs text-slate-500 py-12 italic font-mono bg-slate-900 border border-slate-800 rounded-2xl">
                No session logs recorded in .along/SESSIONS/
              </div>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {m.decisions.map((dec) => (
              <div
                key={dec.id}
                onClick={() => m.selectEntity(dec.id, 'decision')}
                className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 cursor-pointer transition shadow-sm space-y-3 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-amber-400">{dec.id}</span>
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase border ${
                        dec.status === 'Accepted'
                          ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {dec.status}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-slate-100 mt-2">{dec.title}</h3>
                  {dec.date && (
                    <div className="text-xs text-slate-400 font-mono mt-1">Recorded: {dec.date}</div>
                  )}
                </div>
                <div className="text-xs text-sky-400 font-medium flex items-center gap-1 hover:underline">
                  View Decision Details &rarr;
                </div>
              </div>
            ))}
            {m.decisions.length === 0 && (
              <div className="col-span-2 text-center text-xs text-slate-500 py-12 italic font-mono bg-slate-900 border border-slate-800 rounded-2xl">
                No ADR decisions found in .along/DECISIONS.md
              </div>
            )}
          </div>
        )}
      </div>
    ),
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const SessionsDecisionsView = toReact(useSessionsView);
