import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ALERT_RULE_TEMPLATES,
  formatAlertTime,
  getMetricLabel,
  getNotificationChannelLabel,
  summarizeAlertEvents,
} from '../admin-monitoring.js';

test('alert templates default to in-app notifications for admin bell delivery', () => {
  assert.ok(ALERT_RULE_TEMPLATES.length >= 4);
  assert.ok(ALERT_RULE_TEMPLATES.every((template) => template.notification_channels.includes('in_app')));
});

test('monitoring helpers expose readable metric and channel labels', () => {
  assert.equal(getMetricLabel('cpu_percent'), 'CPU 使用率');
  assert.equal(getNotificationChannelLabel('in_app'), '站内通知（管理员铃铛）');
});

test('alert summaries count each status bucket from recent events', () => {
  const summary = summarizeAlertEvents([
    { status: 'firing' },
    { status: 'firing' },
    { status: 'acknowledged' },
    { status: 'resolved' },
  ]);

  assert.deepEqual(summary, {
    all: 4,
    firing: 2,
    acknowledged: 1,
    resolved: 1,
  });
});

test('alert time formatter outputs month-day hour-minute strings', () => {
  assert.equal(formatAlertTime('2026-05-12T10:23:00+08:00'), '5/12 10:23');
  assert.equal(formatAlertTime(''), '-');
});
