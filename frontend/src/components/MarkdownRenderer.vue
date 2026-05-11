<template>
  <div class="markdown-body" v-html="renderedHtml" />
</template>

<script setup>
import { computed } from 'vue';
import { marked } from 'marked';
import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import markdown from 'highlight.js/lib/languages/markdown';
import plaintext from 'highlight.js/lib/languages/plaintext';
import python from 'highlight.js/lib/languages/python';
import sql from 'highlight.js/lib/languages/sql';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';
import DOMPurify from 'dompurify';

// 导入 GitHub Dark 主题
import 'highlight.js/styles/github-dark.css';

const props = defineProps({
  content: {
    type: String,
    default: '',
  },
  streaming: {
    type: Boolean,
    default: false,
  },
});

hljs.registerLanguage('bash', bash);
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('json', json);
hljs.registerLanguage('markdown', markdown);
hljs.registerLanguage('plaintext', plaintext);
hljs.registerLanguage('python', python);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('yaml', yaml);

const LANGUAGE_ALIASES = {
  sh: 'bash',
  shell: 'bash',
  js: 'javascript',
  ts: 'typescript',
  py: 'python',
  yml: 'yaml',
  html: 'xml',
  svg: 'xml',
  vue: 'xml',
  text: 'plaintext',
  plain: 'plaintext',
};

const escapeHtml = (value) => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const resolveLanguage = (lang) => {
  const normalized = String(lang || '').trim().toLowerCase();
  if (!normalized) {
    return '';
  }

  return LANGUAGE_ALIASES[normalized] || normalized;
};

const highlightCodeBlock = (text, lang) => {
  const language = resolveLanguage(lang);

  if (language && hljs.getLanguage(language)) {
    return {
      language,
      value: hljs.highlight(text, { language }).value,
    };
  }

  try {
    const detected = hljs.highlightAuto(text);
    return {
      language: detected.language || 'plaintext',
      value: detected.value,
    };
  } catch {
    return {
      language: language || 'plaintext',
      value: escapeHtml(text),
    };
  }
};

// 配置 marked
const renderer = new marked.Renderer();

// 自定义代码块渲染（带高亮）
renderer.code = function ({ text, lang }) {
  const highlightedBlock = highlightCodeBlock(text, lang);

  return `<pre class="hljs-code-block"><div class="hljs-code-header"><span class="hljs-code-lang">${highlightedBlock.language}</span><button class="hljs-copy-btn" onclick="navigator.clipboard.writeText(this.closest('.hljs-code-block').querySelector('code').textContent).then(()=>{this.textContent='已复制';setTimeout(()=>{this.textContent='复制'},1500)})">复制</button></div><code class="hljs language-${highlightedBlock.language}">${highlightedBlock.value}</code></pre>`;
};

// 自定义链接渲染（新标签页打开）
renderer.link = function ({ href, title, text }) {
  const titleAttr = title ? ` title="${title}"` : '';
  return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
};

// 自定义表格渲染
renderer.table = function ({ header, rows }) {
  return `<div class="table-wrapper"><table><thead>${header}</thead><tbody>${rows}</tbody></table></div>`;
};

marked.setOptions({
  renderer,
  breaks: true, // 支持 GFM 换行
  gfm: true,    // 启用 GitHub Flavored Markdown
});

// 渲染 Markdown 并清理 XSS
const renderedHtml = computed(() => {
  if (!props.content) return '';

  const rawHtml = marked.parse(props.content);
  return DOMPurify.sanitize(rawHtml, {
    ADD_TAGS: ['button'], // 允许复制按钮
    ADD_ATTR: ['onclick', 'class', 'target', 'rel'],
  });
});
</script>

<style>
/* GitHub-style Markdown 样式 */
.markdown-body {
  font-size: 14px;
  line-height: 1.7;
  word-wrap: break-word;
  color: #d8e5ff;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
  line-height: 1.4;
  color: #eef4ff;
}

.markdown-body h1 {
  font-size: 1.5em;
  padding-bottom: 0.3em;
  border-bottom: 1px solid rgba(72, 108, 255, 0.2);
}

.markdown-body h2 {
  font-size: 1.3em;
  padding-bottom: 0.3em;
  border-bottom: 1px solid rgba(72, 108, 255, 0.15);
}

.markdown-body h3 {
  font-size: 1.15em;
}

.markdown-body h4 {
  font-size: 1em;
}

.markdown-body p {
  margin-top: 0;
  margin-bottom: 10px;
}

.markdown-body a {
  color: #7b9fff;
  text-decoration: none;
}

.markdown-body a:hover {
  text-decoration: underline;
}

.markdown-body strong {
  font-weight: 600;
  color: #eef4ff;
}

.markdown-body em {
  font-style: italic;
}

/* 行内代码 */
.markdown-body code {
  padding: 0.2em 0.4em;
  margin: 0;
  font-size: 85%;
  background: rgba(72, 108, 255, 0.15);
  border-radius: 4px;
  font-family: 'SF Mono', 'Fira Code', 'Fira Mono', Menlo, Consolas, monospace;
  color: #b8ccff;
}

/* 代码块 */
.markdown-body .hljs-code-block {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(72, 108, 255, 0.2);
  background: rgba(10, 19, 38, 0.8);
}

.markdown-body .hljs-code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: rgba(20, 35, 65, 0.9);
  border-bottom: 1px solid rgba(72, 108, 255, 0.15);
}

.markdown-body .hljs-code-lang {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #8597bb;
}

.markdown-body .hljs-copy-btn {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(72, 108, 255, 0.25);
  background: rgba(36, 87, 197, 0.15);
  color: #8597bb;
  cursor: pointer;
  transition: all 0.2s ease;
}

.markdown-body .hljs-copy-btn:hover {
  background: rgba(36, 87, 197, 0.3);
  color: #b8ccff;
}

.markdown-body pre code {
  display: block;
  padding: 12px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.6;
  background: transparent;
  border-radius: 0;
  color: inherit;
}

/* 列表 */
.markdown-body ul,
.markdown-body ol {
  padding-left: 2em;
  margin-top: 0;
  margin-bottom: 10px;
}

.markdown-body li {
  margin-bottom: 4px;
}

.markdown-body li > p {
  margin-top: 0;
  margin-bottom: 0;
}

/* 引用块 */
.markdown-body blockquote {
  margin: 10px 0;
  padding: 0.5em 1em;
  border-left: 3px solid rgba(36, 87, 197, 0.5);
  background: rgba(36, 87, 197, 0.08);
  border-radius: 0 6px 6px 0;
  color: #b8ccff;
}

.markdown-body blockquote p:last-child {
  margin-bottom: 0;
}

/* 表格 */
.markdown-body .table-wrapper {
  overflow-x: auto;
  margin: 12px 0;
  border-radius: 8px;
  border: 1px solid rgba(72, 108, 255, 0.2);
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.markdown-body thead {
  background: rgba(20, 35, 65, 0.6);
}

.markdown-body th {
  padding: 8px 12px;
  font-weight: 600;
  text-align: left;
  border-bottom: 2px solid rgba(72, 108, 255, 0.25);
  color: #eef4ff;
}

.markdown-body td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(72, 108, 255, 0.1);
}

.markdown-body tbody tr:hover {
  background: rgba(36, 87, 197, 0.08);
}

/* 水平线 */
.markdown-body hr {
  height: 2px;
  margin: 16px 0;
  background: rgba(72, 108, 255, 0.2);
  border: none;
  border-radius: 1px;
}

/* 图片 */
.markdown-body img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 8px 0;
}

/* 复选框列表（GFM 任务列表） */
.markdown-body .task-list-item {
  list-style: none;
  margin-left: -1.5em;
}

.markdown-body .task-list-item input[type="checkbox"] {
  margin-right: 0.5em;
  accent-color: #2457c5;
}
</style>
