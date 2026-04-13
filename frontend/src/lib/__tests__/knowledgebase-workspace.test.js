import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildChunkExpansionState,
  buildEmptyDetailState,
  buildKnowledgebaseQuery,
  buildNextSelection,
  buildPreviewState,
  buildSelectionAfterBatchDelete,
  summarizeBatchResult,
} from '../knowledgebase-workspace.js';

test('buildKnowledgebaseQuery removes empty filters and keeps pagination', () => {
  assert.deepEqual(
    buildKnowledgebaseQuery({
      searchKeyword: 'liquidity',
      statusFilter: 'indexed',
      timeRange: '7d',
      page: 2,
      pageSize: 10,
    }),
    { q: 'liquidity', status: 'indexed', time_range: '7d', page: 2, page_size: 10 },
  );
});

test('buildPreviewState prefers extracted text and falls back to preview text', () => {
  assert.deepEqual(
    buildPreviewState({ extractedText: '', parsedTextPreview: 'short preview' }),
    { hasContent: true, body: 'short preview' },
  );
});

test('summarizeBatchResult reports partial failure details', () => {
  assert.match(
    summarizeBatchResult(
      { accepted_count: 2, skipped_count: 1, results: [{ document_id: 3, reason: '已有进行中的摄取任务。' }] },
      '重新入库',
    ),
    /成功 2 项，跳过\/失败 1 项/,
  );
});

test('buildNextSelection keeps row selection separate from checkbox selection', () => {
  assert.deepEqual(
    buildNextSelection({
      selectedIds: [2],
      toggledId: 3,
    }),
    [2, 3],
  );
});

test('buildSelectionAfterBatchDelete removes deleted ids and preserves survivors', () => {
  assert.deepEqual(
    buildSelectionAfterBatchDelete([1, 2, 3], [2, 4]),
    [1, 3],
  );
});

test('buildEmptyDetailState returns the expected workspace prompt', () => {
  assert.deepEqual(buildEmptyDetailState(), {
    title: '请选择一个文档查看详情',
    detail: '左侧选择文档后，可查看处理进度、切块和错误信息。',
  });
});

test('buildChunkExpansionState toggles a chunk key idempotently', () => {
  assert.deepEqual(buildChunkExpansionState(['chunk-1'], 'chunk-2'), ['chunk-1', 'chunk-2']);
  assert.deepEqual(buildChunkExpansionState(['chunk-1'], 'chunk-1'), []);
});
