import test from 'node:test';
import assert from 'node:assert/strict';

import { createLightragApi, normalizeGraphEdge, normalizeGraphNode, normalizeLightragDocument } from '../lightrag.js';

test('normalizeLightragDocument maps mixed document payloads into stable rows', () => {
  const row = normalizeLightragDocument({
    doc_id: 'doc-1',
    file_name: 'bank-risk.pdf',
    status: 'processed',
    track_id: 'track-1',
  });

  assert.equal(row.docId, 'doc-1');
  assert.equal(row.title, 'bank-risk.pdf');
  assert.equal(row.status, 'processed');
});

test('normalizeGraphNode preserves human-readable node labels', () => {
  const node = normalizeGraphNode({
    entity_name: '流动性风险',
    entity_type: 'risk',
  });

  assert.equal(node.label, '流动性风险');
  assert.equal(node.type, 'risk');
});

test('normalizeGraphNode reads nested LightRAG graph properties', () => {
  const node = normalizeGraphNode({
    id: 'Baseline Probe Observations',
    labels: ['Baseline Probe Observations'],
    properties: {
      entity_type: 'data',
      description: 'A record of agent behavior before the skill is installed.',
      entity_id: 'Baseline Probe Observations',
      file_path: 'baseline-observations.txt',
    },
  });

  assert.equal(node.label, 'Baseline Probe Observations');
  assert.equal(node.type, 'data');
  assert.equal(node.description, 'A record of agent behavior before the skill is installed.');
  assert.equal(node.properties.file_path, 'baseline-observations.txt');
});

test('normalizeGraphEdge reads nested LightRAG edge properties', () => {
  const edge = normalizeGraphEdge({
    id: '0',
    type: 'DIRECTED',
    source: 'A',
    target: 'B',
    properties: {
      description: 'A points to B.',
      keywords: 'document date',
    },
  });

  assert.equal(edge.label, '关联');
  assert.equal(edge.description, 'A points to B.');
  assert.equal(edge.properties.keywords, 'document date');
});

test('createLightragApi targets the bridge endpoints', async () => {
  const calls = [];
  const api = createLightragApi({
    fetchJson: async (path, options) => {
      calls.push({ path, options });
      return { code: 0, data: { status_counts: { all: 2 }, documents: [], pagination: {} } };
    },
  });

  await api.getOverview();
  await api.listDocuments({ page: 2, pageSize: 15 });
  await api.deleteDocument(['doc-1'], { deleteFile: true });

  assert.deepEqual(
    calls.map((call) => ({ path: call.path, method: call.options.method })),
    [
      { path: '/api/ops/lightrag/', method: 'GET' },
      { path: '/api/ops/lightrag/documents/paginated/', method: 'POST' },
      { path: '/api/ops/lightrag/documents/delete_document/', method: 'DELETE' },
    ],
  );
});
