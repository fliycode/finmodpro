export const AUTH_BRAND_STATEMENT = '一站式风控平台，连接文档、问答与模型，快速完成从风险识别到报告生成。';

const EMPHASIS_WORDS = ['文档', '问答', '模型'];

export function buildBrandStatementSegments(statement = AUTH_BRAND_STATEMENT) {
  const segments = [];
  let cursor = 0;

  EMPHASIS_WORDS.forEach((word) => {
    const nextIndex = statement.indexOf(word, cursor);
    if (nextIndex === -1) {
      return;
    }

    if (nextIndex > cursor) {
      segments.push({ text: statement.slice(cursor, nextIndex), emphasis: false });
    }

    segments.push({ text: word, emphasis: true });
    cursor = nextIndex + word.length;
  });

  if (cursor < statement.length) {
    segments.push({ text: statement.slice(cursor), emphasis: false });
  }

  return segments;
}

export function getPasswordToggleLabel(showPassword) {
  return showPassword ? '隐藏密码' : '显示密码';
}
