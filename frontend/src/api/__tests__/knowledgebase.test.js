import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeDocument,
  normalizeDocumentVersion,
} from '../knowledgebase.js';

test('normalizeDocument keeps dataset and provenance/version metadata', () => {
  const normalized = normalizeDocument({
    id: 18,
    title: 'Q1 风险纪要修订版',
    filename: 'q1-report-v2.txt',
    status: 'indexed',
    dataset: {
      id: 4,
      name: '2025 年报数据集',
      description: '用于问答与风险提取',
      document_count: 2,
    },
    root_document_id: 11,
    version_number: 2,
    current_version: 2,
    is_current_version: true,
    provenance: {
      source_type: 'upload',
      source_label: 'Q1 风险纪要修订版',
      source_metadata: {
        channel: 'email',
      },
      processing_notes: '补充了董事会风险说明。',
    },
    created_at: '2026-04-13T10:00:00+08:00',
    updated_at: '2026-04-13T10:10:00+08:00',
  });

  assert.equal(normalized.dataset.id, 4);
  assert.equal(normalized.dataset.name, '2025 年报数据集');
  assert.equal(normalized.datasetName, '2025 年报数据集');
  assert.equal(normalized.rootDocumentId, 11);
  assert.equal(normalized.versionNumber, 2);
  assert.equal(normalized.currentVersion, 2);
  assert.equal(normalized.provenance.sourceType, 'upload');
  assert.equal(normalized.provenance.sourceLabel, 'Q1 风险纪要修订版');
  assert.deepEqual(normalized.provenance.sourceMetadata, { channel: 'email' });
  assert.equal(normalized.provenance.processingNotes, '补充了董事会风险说明。');
});

test('normalizeDocumentVersion formats version metadata for the detail panel', () => {
  const normalized = normalizeDocumentVersion({
    document_id: 18,
    version_number: 2,
    is_current: true,
    source_type: 'upload',
    source_label: 'Q1 风险纪要修订版',
    source_metadata: { checksum: 'abc123' },
    processing_notes: '补充了董事会风险说明。',
    created_at: '2026-04-13T10:00:00+08:00',
  });

  assert.equal(normalized.documentId, 18);
  assert.equal(normalized.versionNumber, 2);
  assert.equal(normalized.isCurrent, true);
  assert.equal(normalized.sourceType, 'upload');
  assert.equal(normalized.sourceLabel, 'Q1 风险纪要修订版');
  assert.deepEqual(normalized.sourceMetadata, { checksum: 'abc123' });
  assert.equal(normalized.processingNotes, '补充了董事会风险说明。');
  assert.match(normalized.createdAtText, /2026-04-13/);
});
