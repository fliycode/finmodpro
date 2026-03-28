import { createApiConfig, joinUrl } from './config.js';

export const opsApi = {
  // Mock fetch stats
  async getStats() {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve({
          kbCount: 156,
          activeModels: 12,
          health: '98%',
          requestCount: 4520,
          errorRate: '0.05%'
        });
      }, 400);
    });
  },
  
  // Mock fetch logs
  async getLogs() {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve([
          { timestamp: '2026-03-26 10:15:22', level: 'INFO', module: 'QA-Engine', message: 'Query processed successfully for user: admin' },
          { timestamp: '2026-03-26 10:14:05', level: 'WARN', module: 'Auth', message: 'Failed login attempt from IP: 192.168.1.105' },
          { timestamp: '2026-03-26 10:12:45', level: 'INFO', module: 'KB-Manager', message: 'Document [Q1_Report.pdf] indexed successfully' },
          { timestamp: '2026-03-26 10:10:01', level: 'ERROR', module: 'Database', message: 'Connection timeout on read replica 2' }
        ]);
      }, 600);
    });
  }
};
