const DEFAULT_SIDEBAR_PRESENTATION = Object.freeze({
  mode: 'expanded',
  showBrandCopy: true,
  showGroupLabels: true,
  showItemLabels: true,
});

export function getSidebarPresentation(_area) {
  return DEFAULT_SIDEBAR_PRESENTATION;
}
