const MODELS = Object.freeze({
  qa: Object.freeze({
    mobileMode: 'chapter-tabs',
    regions: Object.freeze([
      Object.freeze({ id: 'conversation', label: '会话' }),
      Object.freeze({ id: 'dossier', label: '结论' }),
      Object.freeze({ id: 'evidence', label: '证据' }),
    ]),
  }),
  knowledge: Object.freeze({
    mobileMode: 'stacked-drawers',
    regions: Object.freeze([
      Object.freeze({ id: 'filters', label: '筛选' }),
      Object.freeze({ id: 'ledger', label: '文档' }),
      Object.freeze({ id: 'inspector', label: '详情' }),
    ]),
  }),
  risk: Object.freeze({
    mobileMode: 'chapter-tabs',
    regions: Object.freeze([
      Object.freeze({ id: 'upload', label: '上传' }),
      Object.freeze({ id: 'results', label: '结果' }),
    ]),
  }),
  history: Object.freeze({
    mobileMode: 'single-column',
    regions: Object.freeze([
      Object.freeze({ id: 'filters', label: '检索' }),
      Object.freeze({ id: 'records', label: '记录' }),
    ]),
  }),
  profile: Object.freeze({
    mobileMode: 'single-column',
    regions: Object.freeze([
      Object.freeze({ id: 'identity', label: '身份' }),
      Object.freeze({ id: 'access', label: '权限' }),
    ]),
  }),
});

export function getWorkspacePageModel(page) {
  return MODELS[page];
}
