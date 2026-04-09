const ACTIVE_CODES = new Set(['queued', 'parsing', 'chunking', 'indexing']);
const ACTIVE_TASK_STATUSES = new Set(['queued', 'running']);

export const isIngestionInFlight = (document) => {
  const processCode = String(document?.processStep?.code || '').toLowerCase();
  const taskStatus = String(document?.latestTask?.status || '').toLowerCase();

  return ACTIVE_CODES.has(processCode) || ACTIVE_TASK_STATUSES.has(taskStatus);
};

export const getIngestionAction = (document) => {
  if (!document || isIngestionInFlight(document)) {
    return null;
  }

  const processCode = String(document.processStep?.code || document.status || '').toLowerCase();
  if (document.isSearchReady || processCode === 'indexed') {
    return {
      label: '重新入库',
      emphasis: 'secondary',
    };
  }

  if (processCode === 'failed') {
    return {
      label: '重新入库',
      emphasis: 'primary',
    };
  }

  return {
    label: '启动入库',
    emphasis: 'primary',
  };
};
