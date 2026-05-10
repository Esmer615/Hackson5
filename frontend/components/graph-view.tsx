'use client';

import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { GraphChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { ComposeOption, ECharts } from 'echarts/core';
import type { GraphSeriesOption } from 'echarts/charts';
import type {
  GridComponentOption,
  LegendComponentOption,
  TitleComponentOption,
  TooltipComponentOption,
} from 'echarts/components';
import type { CallbackDataParams } from 'echarts/types/dist/shared';

import type { GraphData, GraphNode } from '@/lib/types';

echarts.use([
  GraphChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
]);

type GraphViewOption = ComposeOption<
  | GraphSeriesOption
  | GridComponentOption
  | LegendComponentOption
  | TitleComponentOption
  | TooltipComponentOption
>;

type GraphViewProps = {
  graph: GraphData;
  selectedNodeId?: string;
  onSelectNode: (node: GraphNode) => void;
};

const categoryPalette = [
  '#0f766e',
  '#d97706',
  '#be123c',
  '#2563eb',
  '#4d7c0f',
  '#7c3aed',
];

function isCallbackDataParams(
  params: CallbackDataParams | CallbackDataParams[],
): params is CallbackDataParams {
  return !Array.isArray(params);
}

function isGraphEdgeData(
  data: CallbackDataParams['data'],
): data is { source: string; target: string } {
  return (
    typeof data === 'object' &&
    data !== null &&
    'source' in data &&
    'target' in data
  );
}

export function GraphView({
  graph,
  selectedNodeId,
  onSelectNode,
}: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const chart = echarts.init(containerRef.current, undefined, {
      renderer: 'canvas',
    });
    chartRef.current = chart;

    const resize = () => chart.resize();
    window.addEventListener('resize', resize);

    chart.on('click', (params) => {
      if (params.dataType !== 'node') {
        return;
      }

      const node = graph.nodes.find((item) => item.node_id === params.name);
      if (node) {
        onSelectNode(node);
      }
    });

    return () => {
      window.removeEventListener('resize', resize);
      chart.dispose();
      chartRef.current = null;
    };
  }, [graph.nodes, onSelectNode]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) {
      return;
    }

    const categories = Array.from(
      new Set(graph.nodes.map((node) => node.category || '未分类')),
    ).map((name, index) => ({
      name,
      itemStyle: { color: categoryPalette[index % categoryPalette.length] },
    }));

    const option: GraphViewOption = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          if (!isCallbackDataParams(params)) {
            return '';
          }

          if (params.dataType === 'edge' && isGraphEdgeData(params.data)) {
            const edgeData = params.data;
            const edge = graph.edges.find(
              (item) =>
                item.source === edgeData.source &&
                item.target === edgeData.target,
            );
            return edge
              ? `${edge.relation_type}<br/>${edge.description || ''}`
              : '';
          }

          const node = graph.nodes.find((item) => item.node_id === params.name);
          return node
            ? `${node.name}<br/>${node.definition || '暂无定义'}`
            : '';
        },
      },
      legend: {
        bottom: 6,
        left: 12,
        textStyle: { color: '#475569' },
        data: categories.map((category) => category.name),
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          categories,
          force: {
            repulsion: 180,
            edgeLength: [70, 150],
            gravity: 0.08,
          },
          label: {
            show: true,
            color: '#0f172a',
            fontSize: 12,
            formatter: '{b}',
          },
          lineStyle: {
            color: '#64748b',
            opacity: 0.55,
            curveness: 0.18,
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 3 },
          },
          data: graph.nodes.map((node) => ({
            id: node.node_id,
            name: node.node_id,
            value: node.frequency,
            category: categories.findIndex(
              (category) => category.name === (node.category || '未分类'),
            ),
            symbolSize: Math.min(58, Math.max(24, 22 + node.frequency * 3)),
            itemStyle: {
              borderColor:
                node.node_id === selectedNodeId ? '#020617' : '#ffffff',
              borderWidth: node.node_id === selectedNodeId ? 5 : 2,
              shadowBlur: node.node_id === selectedNodeId ? 24 : 10,
              shadowColor: 'rgba(15, 23, 42, 0.22)',
            },
            label: {
              formatter: node.name,
              fontWeight: node.node_id === selectedNodeId ? 800 : 600,
            },
          })),
          links: graph.edges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            lineStyle: {
              width: edge.relation_type === 'prerequisite' ? 2.6 : 1.5,
            },
          })),
        },
      ],
    };

    chart.setOption(option, true);
  }, [graph, selectedNodeId]);

  if (graph.nodes.length === 0) {
    return (
      <div className="flex min-h-[420px] items-center justify-center rounded-[2rem] border border-dashed border-slate-300 bg-white/50 p-8 text-center text-sm text-slate-500">
        上传教材并运行流水线后，知识图谱会在这里展开。
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="min-h-[480px] w-full rounded-[2rem] bg-white/60"
    />
  );
}
