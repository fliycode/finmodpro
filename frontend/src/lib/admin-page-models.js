const MODELS = Object.freeze({
  overview: {
    mobileMode: 'triage-stack',
    regions: [
      { id: 'status-band', label: '态势' },
      { id: 'command-deck', label: '指挥' },
      { id: 'inspector', label: '巡检' },
    ],
  },
  'llm-overview': {
    mobileMode: 'triage-stack',
    regions: [
      { id: 'status-band', label: '态势' },
      { id: 'command-deck', label: '路由' },
      { id: 'inspector', label: '异常' },
    ],
  },
  operations: {
    mobileMode: 'triage-stack',
    regions: [
      { id: 'status-band', label: '态势' },
      { id: 'command-deck', label: '控制' },
      { id: 'inspector', label: '巡检' },
    ],
  },
  governance: {
    mobileMode: 'review-stack',
    regions: [
      { id: 'queue', label: '队列' },
      { id: 'comparison', label: '对照' },
      { id: 'decision', label: '决策' },
    ],
  },
});

export const getAdminPageModel = (key) => MODELS[key] || MODELS.operations;
