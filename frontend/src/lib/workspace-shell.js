export function getSidebarPresentation(area) {
  if (area === 'workspace') {
    return {
      mode: 'expanded',
      showBrandCopy: true,
      showGroupLabels: true,
      showItemLabels: true,
    };
  }

  return {
    mode: 'expanded',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  };
}
