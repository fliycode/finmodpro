const SHELL_SPECS = Object.freeze({
  workspace: Object.freeze({
    persona: 'dossier',
    layout: Object.freeze({
      desktop: 'split-dossier',
      tablet: 'folding-rail',
      mobile: 'chapter-tabs',
    }),
  }),
  admin: Object.freeze({
    persona: 'war-room',
    layout: Object.freeze({
      desktop: 'status-band',
      tablet: 'slice-grid',
      mobile: 'triage-stack',
    }),
  }),
});

const DESTRUCTIVE_AUDIT_ROWS = Object.freeze([
  Object.freeze({
    dimension: 'Layout system',
    before: 'Shared shell',
    after: 'Dossier vs war room',
  }),
  Object.freeze({
    dimension: 'Color system',
    before: 'Blue-gray shared palette',
    after: 'Warm dossier and dark ops split',
  }),
  Object.freeze({
    dimension: 'Typography',
    before: 'Uniform product sans',
    after: 'Editorial vs command hierarchy',
  }),
  Object.freeze({
    dimension: 'Component shape',
    before: 'Rounded product cards',
    after: 'Folders, drawers, monitor slices',
  }),
  Object.freeze({
    dimension: 'Information order',
    before: 'Tool-first',
    after: 'Conclusion and status first',
  }),
  Object.freeze({
    dimension: 'Responsive strategy',
    before: 'Collapse and stack',
    after: 'Chapter tabs and triage modes',
  }),
]);

export function getAuthenticatedShellSpec(area) {
  return SHELL_SPECS[area] ?? SHELL_SPECS.workspace;
}

export function getDestructiveAuditRows() {
  return [...DESTRUCTIVE_AUDIT_ROWS];
}
