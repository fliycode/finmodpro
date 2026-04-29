import { getAuthenticatedShellSpec } from './authenticated-shell.js';

const SIDEBAR_PRESENTATIONS = Object.freeze({
  dossier: Object.freeze({
    mode: 'editorial',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  }),
  'war-room': Object.freeze({
    mode: 'dense',
    showBrandCopy: true,
    showGroupLabels: true,
    showItemLabels: true,
  }),
});

export function getSidebarPresentation(area) {
  const spec = getAuthenticatedShellSpec(area);

  return SIDEBAR_PRESENTATIONS[spec.persona] ?? SIDEBAR_PRESENTATIONS.dossier;
}
