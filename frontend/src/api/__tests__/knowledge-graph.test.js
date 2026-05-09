import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createKnowledgeGraphApi,
  normalizeKnowledgeGraphDocument,
  normalizeKnowledgeGraphEdge,
  normalizeKnowledgeGraphNode,
} from '../knowledge-graph.js';

test('normalizeKnowledgeGraphDocument maps mixed document payloads into stable rows', () => {
  const row = normalizeKnowledgeGraphDocument({
    doc_id: 'doc-1',
    file_name: 'bank-risk.pdf',
    status: 'processed',
    track_id: 'track-1',
  });

  assert.equal(row.docId, 'doc-1');
  assert.equal(row.title, 'bank-risk.pdf');
  assert.equal(row.status, 'processed');
});

test('normalizeKnowledgeGraphNode preserves human-readable node labels', () => {
  const node = normalizeKnowledgeGraphNode({
    entity_name: '流动性风险',
    entity_type: 'risk',
  });

  assert.equal(node.label, '流动性风险');
  assert.equal(node.type, 'risk');
});

test('normalizeKnowledgeGraphNode reads nested graph properties', () => {
  const node = normalizeKnowledgeGraphNode({
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

test('normalizeKnowledgeGraphEdge reads nested graph properties', () => {
  const edge = normalizeKnowledgeGraphEdge({
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

test('createKnowledgeGraphApi targets the compatibility endpoints', async () => {
  const calls = [];
  const api = createKnowledgeGraphApi({
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
