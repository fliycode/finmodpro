import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ALERT_RULE_TEMPLATES,
  formatAlertTime,
  getMetricLabel,
  getNotificationChannelLabel,
  sortAlertEventsByPriority,
  summarizeAlertEvents,
  summarizeAlertSeverities,
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

test('alert severity summary counts critical warning and info events', () => {
  const summary = summarizeAlertSeverities([
    { severity: 'critical' },
    { severity: 'warning' },
    { severity: 'critical' },
    { severity: 'info' },
  ]);

  assert.deepEqual(summary, {
    critical: 2,
    warning: 1,
    info: 1,
  });
});

test('alert events sort by status priority then severity then recency', () => {
  const sorted = sortAlertEventsByPriority([
    { id: 1, status: 'resolved', severity: 'critical', triggeredAt: '2026-05-12T10:30:00+08:00' },
    { id: 2, status: 'firing', severity: 'warning', triggeredAt: '2026-05-12T10:20:00+08:00' },
    { id: 3, status: 'acknowledged', severity: 'critical', triggeredAt: '2026-05-12T10:40:00+08:00' },
    { id: 4, status: 'firing', severity: 'critical', triggeredAt: '2026-05-12T10:10:00+08:00' },
  ]);

  assert.deepEqual(sorted.map((item) => item.id), [4, 2, 3, 1]);
});

test('alert time formatter outputs month-day hour-minute strings', () => {
  assert.equal(formatAlertTime('2026-05-12T10:23:00+08:00'), '5/12 10:23');
  assert.equal(formatAlertTime(''), '-');
});
