import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildLightragGraphNeighbors,
  buildLightragGraphFacets,
  filterLightragGraphLabels,
  filterLightragGraph,
  findLightragGraphMatches,
  getLightragStatusTone,
  searchLightragGraphNodes,
} from '../lightrag-workspace.js';

test('buildLightragGraphFacets groups node and relation counts', () => {
  const facets = buildLightragGraphFacets(
    [
      { id: 'n1', type: '公司' },
      { id: 'n2', type: '公司' },
      { id: 'n3', type: '人物' },
    ],
    [
      { id: 'e1', label: '投资' },
      { id: 'e2', label: '投资' },
      { id: 'e3', label: '任职' },
    ],
  );

  assert.deepEqual(facets.nodeTypes, [
    { label: '公司', count: 2 },
    { label: '人物', count: 1 },
  ]);
  assert.deepEqual(facets.relationLabels, [
    { label: '投资', count: 2 },
    { label: '任职', count: 1 },
  ]);
});

test('filterLightragGraph removes hidden nodes and disconnected edges', () => {
  const graph = filterLightragGraph(
    {
      nodes: [
        { id: 'a', type: '公司' },
        { id: 'b', type: '人物' },
        { id: 'c', type: '事件' },
      ],
      edges: [
        { id: 'ab', source: 'a', target: 'b', label: '任职' },
        { id: 'ac', source: 'a', target: 'c', label: '投资' },
      ],
    },
    {
      activeNodeTypes: ['公司', '人物'],
      activeRelationLabels: ['任职'],
    },
  );

  assert.deepEqual(graph.nodes.map((node) => node.id), ['a', 'b']);
  assert.deepEqual(graph.edges.map((edge) => edge.id), ['ab']);
});

test('searchLightragGraphNodes matches across label, type, and description', () => {
  const ids = searchLightragGraphNodes(
    [
      { id: 'bank', label: '招商银行', type: '公司', description: '流动性风险关注对象' },
      { id: 'bond', label: '债券违约', type: '事件', description: '' },
    ],
    '流动性',
  );

  assert.deepEqual(ids, ['bank']);
});

test('findLightragGraphMatches ranks label matches ahead of description matches', () => {
  const matches = findLightragGraphMatches(
    [
      { id: 'bank', label: '流动性风险', type: '主题', description: '监管口径' },
      { id: 'memo', label: '季度纪要', type: '文档', description: '包含流动性风险相关描述' },
    ],
    '流动性风险',
  );

  assert.deepEqual(matches.map((item) => item.id), ['bank', 'memo']);
});

test('filterLightragGraphLabels narrows the visible label list without changing order', () => {
  const labels = filterLightragGraphLabels(
    ['流动性风险', '资本结构', '风险抽取'],
    '风险',
  );

  assert.deepEqual(labels, ['流动性风险', '风险抽取']);
});

test('buildLightragGraphNeighbors returns connected node summaries for an active node', () => {
  const neighbors = buildLightragGraphNeighbors(
    {
      nodes: [
        { id: 'company', label: '招商银行', type: '公司' },
        { id: 'event', label: '流动性风险', type: '事件' },
      ],
      edges: [
        { id: 'edge-1', source: 'company', target: 'event', label: '涉及' },
      ],
    },
    'company',
  );

  assert.deepEqual(neighbors, [
    {
      id: 'event',
      label: '流动性风险',
      type: '事件',
      description: '',
      edgeId: 'edge-1',
      edgeLabel: '涉及',
      direction: 'outgoing',
    },
  ]);
});

test('getLightragStatusTone maps known statuses into semantic tones', () => {
  assert.equal(getLightragStatusTone('processed'), 'success');
  assert.equal(getLightragStatusTone('processing'), 'brand');
  assert.equal(getLightragStatusTone('failed'), 'risk');
  assert.equal(getLightragStatusTone('unknown'), 'muted');
});
