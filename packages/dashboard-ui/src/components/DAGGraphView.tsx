import cytoscape from 'cytoscape';
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

export type GraphFilterMode = 'all' | 'dag' | 'kb' | 'decisions' | 'architecture';

export type GraphViewStruct = ComponentStruct<
  DashboardAppMsgStruct,
  {
    props: {
      graphData: {
        nodes: Array<{ id: string; label: string; type: string; [key: string]: any }>;
        edges: Array<{ source: string; target: string; type: string; label?: string }>;
      };
      filterMode?: GraphFilterMode;
    };
    msgScope: {
      publish: DashboardMsgChannels<'APP.ENTITY.SELECT'>;
    };
    actions: {
      resetLayout: () => void;
      fit: () => void;
      zoomIn: () => void;
      zoomOut: () => void;
      selectNode: (id: string) => void;
      setFilterMode: (mode: GraphFilterMode) => void;
    };
  }
>;

export const useGraphView = (
  params?: ComponentParams<GraphViewStruct>
): Component<GraphViewStruct> => {
  let c: Component<GraphViewStruct>;
  let m: ComponentModel<GraphViewStruct>;
  let cyInstance: cytoscape.Core | null = null;
  const containerRef = { current: null as HTMLDivElement | null };

  const initCytoscape = () => {
    if (!containerRef.current || !m.graphData) return;

    const currentFilter = m.filterMode || 'all';
    const allNodes = m.graphData.nodes || [];
    const allEdges = m.graphData.edges || [];

    const filteredNodes = allNodes.filter((n) => {
      if (currentFilter === 'all') return true;
      if (currentFilter === 'dag') return ['issue', 'milestone', 'risk'].includes(n.type);
      if (currentFilter === 'kb') return n.type === 'kb';
      if (currentFilter === 'decisions') return ['decision', 'spike'].includes(n.type);
      if (currentFilter === 'architecture') return n.type === 'architecture';
      return true;
    });

    const activeNodeIds = new Set(filteredNodes.map((n) => n.id));

    const filteredEdges = allEdges.filter(
      (e) => activeNodeIds.has(e.source) && activeNodeIds.has(e.target)
    );

    const elements: cytoscape.ElementDefinition[] = [];

    filteredNodes.forEach((n) => {
      let color = '#38bdf8';
      let shape: cytoscape.Css.NodeShape = 'round-rectangle';

      if (n.type === 'issue') {
        if (n.status === 'done') color = '#10b981';
        else if (n.status === 'in-progress') color = '#f59e0b';
        else if (n.status === 'blocked') color = '#ef4444';
        else color = '#64748b';
      } else if (n.type === 'milestone') {
        color = '#818cf8';
        shape = 'hexagon';
      } else if (n.type === 'risk') {
        color = '#f43f5e';
        shape = 'diamond';
      } else if (n.type === 'spike') {
        color = '#ec4899';
        shape = 'rhomboid';
      } else if (n.type === 'decision') {
        color = '#06b6d4';
        shape = 'round-rectangle';
      } else if (n.type === 'kb') {
        color = '#a855f7';
        shape = 'round-rectangle';
      } else if (n.type === 'architecture') {
        color = '#14b8a6';
        shape = 'round-rectangle';
      }

      elements.push({
        data: {
          id: n.id,
          label: n.label,
          color: color,
          shape: shape,
        },
      });
    });

    filteredEdges.forEach((e) => {
      let edgeColor = '#475569';
      let lineStyle: cytoscape.Css.LineStyle = 'solid';

      if (e.type === 'blocks') {
        edgeColor = '#ef4444';
      } else if (e.type === 'belongs_to') {
        edgeColor = '#38bdf8';
      } else if (e.type === 'parent_of') {
        edgeColor = '#818cf8';
      } else if (e.type === 'related') {
        edgeColor = '#64748b';
        lineStyle = 'dotted';
      } else if (e.type === 'supersedes') {
        edgeColor = '#f59e0b';
        lineStyle = 'dashed';
      } else if (e.type === 'links_to') {
        edgeColor = '#c084fc';
        lineStyle = 'dashed';
      } else if (e.type === 'calls') {
        edgeColor = '#2dd4bf';
        lineStyle = 'solid';
      }

      elements.push({
        data: {
          id: `${e.source}->${e.target}::${e.type}`,
          source: e.source,
          target: e.target,
          label: e.label || '',
          color: edgeColor,
          lineStyle: lineStyle,
        },
      });
    });

    if (cyInstance) {
      cyInstance.destroy();
    }

    cyInstance = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            label: 'data(label)',
            color: '#f8fafc',
            'font-size': '11px',
            'font-family': 'ui-monospace, monospace',
            'text-valign': 'center',
            'text-halign': 'center',
            shape: 'data(shape)' as any,
            width: 'label',
            height: '34px',
            padding: '10px',
            'border-width': 1,
            'border-color': 'rgba(255, 255, 255, 0.2)',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': 'data(color)',
            'target-arrow-color': 'data(color)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': '9px',
            'font-family': 'ui-monospace, monospace',
            color: '#94a3b8',
            'text-rotation': 'autorotate',
          },
        },
      ],
      layout: {
        name: 'cose',
        padding: 40,
        animate: false,
      } as any,
    });

    cyInstance.on('tap', 'node', (evt) => {
      m.selectNode(evt.target.id());
    });
  };

  const def: ComponentDef<GraphViewStruct> = {
    regType: 'GraphView',
    props: {
      graphData: { nodes: [], edges: [] },
      filterMode: 'all',
    },
    actions: {
      resetLayout: () => {
        if (cyInstance) {
          cyInstance.layout({ name: 'cose', padding: 40, animate: true } as any).run();
        }
      },
      fit: () => {
        if (cyInstance) {
          cyInstance.fit(undefined, 30);
        }
      },
      zoomIn: () => {
        if (cyInstance) {
          cyInstance.zoom(cyInstance.zoom() * 1.25);
        }
      },
      zoomOut: () => {
        if (cyInstance) {
          cyInstance.zoom(cyInstance.zoom() * 0.8);
        }
      },
      selectNode: (id: string) => {
        c.msgBus.send({
          channel: 'APP.ENTITY.SELECT',
          payload: { id },
        });
      },
      setFilterMode: (mode: GraphFilterMode) => {
        m.filterMode = mode;
        initCytoscape();
      },
    },
    events: {
      onLayoutReady: () => {
        initCytoscape();
      },
      onChangeGraphData: () => {
        initCytoscape();
      },
      onChangeFilterMode: () => {
        initCytoscape();
      },
      onDestroy: () => {
        if (cyInstance) {
          cyInstance.destroy();
          cyInstance = null;
        }
      },
    },
    view: () => (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-sm relative h-[720px] flex flex-col">
        {/* Controls Overlay Bar */}
        <div className="absolute top-4 left-4 z-10 flex flex-wrap items-center gap-2 bg-slate-950/90 backdrop-blur-md p-1.5 rounded-xl border border-slate-800 shadow-lg">
          {/* Mode Switcher */}
          <div className="flex items-center bg-slate-900 rounded-lg p-0.5 border border-slate-800 text-xs">
            {(
              [
                { id: 'all', label: 'All Entities' },
                { id: 'dag', label: 'Tasks & DAG' },
                { id: 'kb', label: 'Knowledge Base' },
                { id: 'decisions', label: 'Decisions (ADR)' },
                { id: 'architecture', label: 'Architecture' },
              ] as const
            ).map((filter) => (
              <button
                key={filter.id}
                onClick={() => m.setFilterMode(filter.id)}
                className={`px-2.5 py-1 rounded-md transition font-medium ${
                  (m.filterMode || 'all') === filter.id
                    ? 'bg-sky-500 text-slate-950 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <div className="w-px h-5 bg-slate-800 mx-1" />

          <button
            onClick={() => m.resetLayout()}
            className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-xs font-medium text-slate-200 rounded-lg transition flex items-center gap-1.5"
            title="Recalculate Layout"
          >
            <Icon icon="lucide:refresh-cw" className="w-3.5 h-3.5" /> Layout
          </button>
          <button
            onClick={() => m.fit()}
            className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-xs font-medium text-slate-200 rounded-lg transition"
            title="Fit to Screen"
          >
            <Icon icon="lucide:maximize-2" className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => m.zoomIn()}
            className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-lg transition"
            title="Zoom In"
          >
            <Icon icon="lucide:zoom-in" className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => m.zoomOut()}
            className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-lg transition"
            title="Zoom Out"
          >
            <Icon icon="lucide:zoom-out" className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Legend Overlay */}
        <div className="absolute bottom-4 left-4 z-10 bg-slate-950/90 backdrop-blur-md p-3 rounded-xl border border-slate-800 text-[10px] font-mono space-y-1.5 shadow-lg">
          <div className="text-slate-400 font-semibold uppercase text-[9px] mb-1">Legend</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-emerald-500" /> Done Issue
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-amber-500" /> In-Progress Issue
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-slate-500" /> Open Issue
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-indigo-400" /> Milestone (Hex)
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-rose-500" /> Risk (Diamond)
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-pink-500" /> Spike (Rhomboid)
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-cyan-500" /> Decision / ADR
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-purple-500" /> KB Article
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-teal-500" /> Architecture
            </div>
          </div>
        </div>

        {/* Canvas Container */}
        <div
          ref={(el) => {
            containerRef.current = el;
          }}
          className="w-full h-full cursor-grab active:cursor-grabbing"
        />
      </div>
    ),
  };

  c = useComponent(def, params ?? {});
  m = c.model;
  return c;
};

export const DAGGraphView = toReact(useGraphView);
