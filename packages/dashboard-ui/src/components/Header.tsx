import {
  type ComponentStruct,
  type ComponentDef,
  type ComponentParams,
  type Component,
  type ComponentModel,
} from '@actdim/dynstruct/componentModel/contracts';
import { useComponent, toReact } from '@actdim/dynstruct/componentModel/react/hooks';
import { Icon } from '@iconify/react';
import { DashboardAppMsgStruct, DashboardMsgChannels } from '../bus';

export type HeaderStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      repoName: string;
      scanTimestamp: string;
      sseConnected: boolean;
      protocolVersion?: string;
      onSearchClick?: () => void;
    };
    msgScope: {
      publish: DashboardMsgChannels<'APP.SEARCH.OPEN'>;
    };
  }
>;

export const useHeader = (params: ComponentParams<HeaderStruct>): Component<HeaderStruct> => {
  let c: Component<HeaderStruct>;
  let m: ComponentModel<HeaderStruct>;

  const def: ComponentDef<HeaderStruct> = {
    regType: 'Header',
    props: {
      repoName: 'Along',
      scanTimestamp: '',
      sseConnected: false,
      protocolVersion: '3.9.4',
      onSearchClick: () => {},
    },
    view: () => (
      <header className="sticky top-0 z-30 bg-slate-950/80 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo and Repo Title */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-sky-500/20">
                <Icon icon="lucide:cpu" className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-bold text-slate-100 tracking-tight">{m.repoName}</h1>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60 font-semibold">
                    {m.protocolVersion ? (m.protocolVersion.startsWith('v') ? m.protocolVersion : `v${m.protocolVersion}`) : 'v3.9.4'}
                  </span>
                  <div
                    className={`w-2 h-2 rounded-full ${
                      m.sseConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
                    }`}
                    title={m.sseConnected ? 'Live SSE Connected' : 'Disconnected'}
                  />
                </div>
                <p className="text-xs text-slate-400 font-mono">
                  {m.scanTimestamp ? `Synced: ${m.scanTimestamp}` : 'Connecting...'}
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  m.onSearchClick?.();
                  c.msgBus.send({ channel: 'APP.SEARCH.OPEN' });
                }}
                className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs text-slate-400 hover:text-slate-200 transition cursor-pointer"
                title="Search Knowledge Base and Entities (Ctrl+K or /)"
              >
                <Icon icon="lucide:search" className="w-4 h-4 text-slate-400" />
                <span className="hidden sm:inline">Search KB...</span>
                <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono bg-slate-950 border border-slate-700 rounded text-slate-400">
                  /
                </kbd>
              </button>

              <a
                href="/docs"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs font-medium text-sky-400 hover:text-sky-300 transition"
                title="OpenAPI Swagger Documentation"
              >
                <Icon icon="lucide:file-code-2" className="w-4 h-4" />
                <span className="hidden lg:inline">Swagger API</span>
              </a>
            </div>
          </div>
        </div>
      </header>
    ),
  };

  c = useComponent(def, params);
  m = c.model;
  return c;
};

export const Header = toReact(useHeader);
