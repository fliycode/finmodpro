const DEFAULT_SIDEBAR_PRESENTATION = {
  mode: 'expanded',
  showBrandCopy: true,
  showGroupLabels: true,
  showItemLabels: true,
};

export function getSidebarPresentation(area) {
  if (area === 'workspace' || area === 'admin') {
    return DEFAULT_SIDEBAR_PRESENTATION;
  }

  return DEFAULT_SIDEBAR_PRESENTATION;
}
