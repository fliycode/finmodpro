import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const currentDir = dirname(fileURLToPath(import.meta.url));
const stylePath = resolve(currentDir, '../../style.css');

const readStyles = () => readFileSync(stylePath, 'utf8');

test('light console theme neutralizes known dark-only card surfaces', () => {
  const styles = readStyles();
  const lightThemeStart = styles.indexOf(":root[data-theme='light'] .app-shell");

  assert.notEqual(lightThemeStart, -1);

  const lightThemeStyles = styles.slice(lightThemeStart);
  [
    '.board-panel',
    '.event-table th',
    '.history-session-summary',
    '.profile-panel__actions a',
    '.qa-msg__bubble--ai',
    '.qa-input__row',
    '.qa-question-btn',
    '.qa-history-drawer .el-drawer__body',
    '.board-tabs',
    '.risk-doc',
    '.risk-extract__item',
    '.risk-kpi',
    '.risk-step__n',
    '.risk-err',
    '.ops-section-frame__header',
    '.ops-inspector-drawer',
    '.ops-status-band__item',
    '.governance-review-queue__item',
  ].forEach((selector) => {
    assert.match(lightThemeStyles, new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  });
});
