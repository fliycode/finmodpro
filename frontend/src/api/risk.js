import { createApiConfig, joinUrl } from './config.js';

const apiConfig = createApiConfig();

export const riskApi = {
  // Mock generating summary and risks
  async getAnalysis(documentId = null) {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve({
          summary: '该文档详细描述了2025年度的财务表现，主要亮点在于海外业务增长了25%，同时研发投入保持在营收的10%左右。整体经营活动现金流充沛。',
          risks: [
            { level: 'high', category: '市场风险', description: '原材料价格波动可能对下半年毛利率产生显著影响。' },
            { level: 'medium', category: '汇率风险', description: '海外业务占比提升，需关注汇率大幅波动的套期保值需求。' },
            { level: 'low', category: '合规风险', description: '新发布的行业监管政策可能增加合规成本。' }
          ]
        });
      }, 1000);
    });
  }
};
