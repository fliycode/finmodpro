"""
策略对比评测脚本: 直接控制检索路径，对比4种策略。
运行方式: docker exec finmodpro-backend-1 python manage.py shell < this_script
或作为 management command 运行。
"""

import json
import time
import os
import sys
from unittest.mock import patch

# Add backend to path if needed
os.chdir('/app')

import django
django.setup()

from django.conf import settings
from django.test.utils import override_settings


def load_dataset(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_strategy_comparison(dataset_path, limit=None):
    """运行4种策略的完整对比评测。"""
    dataset = load_dataset(dataset_path)
    items = dataset['items'][:limit] if limit else dataset['items']

    strategies = {
        'keyword': '仅BM25+全文检索',
        'vector': '仅向量检索',
        'hybrid': '向量+BM25+全文检索+RRF',
        'hybrid_rerank': '向量+BM25+全文检索+RRF+rerank',
    }

    all_results = {}

    for strategy_key, strategy_name in strategies.items():
        print(f"\n{'='*60}")
        print(f"策略: {strategy_name} ({strategy_key})")
        print(f"{'='*60}")

        results = run_questions_with_strategy(items, strategy_key)
        all_results[strategy_key] = {
            'name': strategy_name,
            'results': results,
            'metrics': compute_metrics(results),
        }

        m = all_results[strategy_key]['metrics']
        print(f"  回答准确率: {m['accuracy']:.1%}")
        print(f"  引用召回率: {m['citation_recall']:.1%}")
        print(f"  引用一致率: {m['citation_consistency']:.1%}")
        print(f"  平均首token时间: {m['avg_first_token_ms']:.0f}ms")

    return all_results


def run_questions_with_strategy(items, strategy):
    """对指定策略运行所有问题。"""
    from chat.services.ask_service import ask_question
    from llm.services.llm_judge_service import judge_rag_answer

    results = []

    for idx, item in enumerate(items):
        question = item['question']
        qid = item['id']
        category = item.get('category', 'unknown')
        expected_type = item.get('expected_answer_type', 'cited')
        expected_keywords = item.get('expected_answer_keywords', [])

        print(f"  [{idx+1}/{len(items)}] {qid}: {question[:50]}...")

        try:
            start = time.time()

            # 根据策略调用 ask_question
            if strategy == 'keyword':
                # 禁用向量检索，仅用 BM25 + 全文检索
                with patch('rag.services.llamaindex_store_service.search',
                          return_value=[], create=True):
                    result = ask_question(question=question, top_k=5)
            elif strategy == 'vector':
                # 禁用 BM25 和全文检索
                with override_settings(RAG_BM25_ENABLED=False, RAG_MYSQL_FULLTEXT_ENABLED=False):
                    result = ask_question(question=question, top_k=5)
            elif strategy == 'hybrid':
                # 向量 + BM25 + 全文，但跳过 rerank
                with patch('rag.services.rerank_service.rerank_results',
                          side_effect=lambda results, **kwargs: results):
                    result = ask_question(question=question, top_k=5)
            else:  # hybrid_rerank - 完整链路
                result = ask_question(question=question, top_k=5)

            elapsed_ms = int((time.time() - start) * 1000)

            answer = result.get('answer', '')
            citations = result.get('citations', [])
            answer_mode = result.get('answer_mode', 'unknown')

            # 构建引用上下文
            ctx = ""
            if citations:
                for i, c in enumerate(citations[:5]):
                    ctx += f"[{i+1}] {c.get('source','?')}: {c.get('content','')[:150]}\n"

            # LLM Judge评分
            judge = judge_rag_answer(
                question=question,
                citations_context=ctx,
                answer=answer,
                expected_answer_type=expected_type,
                expected_keywords=expected_keywords,
                expected_sources=item.get('expected_document_sources', []),
            )

            if judge:
                accuracy = judge['accuracy'] / 10.0
                cit_recall = judge['citation_recall'] / 10.0
                cit_consistency = judge['citation_consistency'] / 10.0
                is_correct = judge['accuracy'] >= 5
            else:
                accuracy = 0.0
                cit_recall = 0.0
                cit_consistency = 0.0
                is_correct = False

            results.append({
                'id': qid,
                'category': category,
                'question': question,
                'answer': answer[:300],
                'answer_mode': answer_mode,
                'accuracy': accuracy,
                'citation_recall': cit_recall,
                'citation_consistency': cit_consistency,
                'is_correct': is_correct,
                'first_token_ms': elapsed_ms,
                'judge_scores': judge,
            })

            status = '✓' if is_correct else '✗'
            print(f"    {status} acc={accuracy:.1f} recall={cit_recall:.1f} consist={cit_consistency:.1f} time={elapsed_ms}ms")

        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({
                'id': qid,
                'category': category,
                'question': question,
                'error': str(e),
                'is_correct': False,
            })

    return results


def compute_metrics(results):
    """计算聚合指标。"""
    valid = [r for r in results if 'error' not in r]
    correct = [r for r in valid if r.get('is_correct')]

    accuracies = [r['accuracy'] for r in valid if 'accuracy' in r]
    recalls = [r['citation_recall'] for r in valid if 'citation_recall' in r]
    consistencies = [r['citation_consistency'] for r in valid if 'citation_consistency' in r]
    times = [r['first_token_ms'] for r in valid if 'first_token_ms' in r]

    def mean_std(vals):
        if not vals:
            return (0, 0)
        m = sum(vals) / len(vals)
        if len(vals) < 2:
            return (m, 0)
        var = sum((v-m)**2 for v in vals) / (len(vals)-1)
        return (m, var**0.5)

    acc_m, acc_s = mean_std(accuracies)
    rec_m, rec_s = mean_std(recalls)
    con_m, con_s = mean_std(consistencies)
    time_m, time_s = mean_std(times)

    return {
        'accuracy': len(correct) / len(valid) if valid else 0,
        'accuracy_mean': acc_m,
        'citation_recall': rec_m,
        'citation_consistency': con_m,
        'avg_first_token_ms': time_m,
        'total': len(results),
        'completed': len(valid),
        'errors': len(results) - len(valid),
    }


def print_comparison_table(all_results):
    """打印对比表。"""
    print("\n")
    print("=" * 90)
    print("表6.3  RAG 问答质量评估结果")
    print("=" * 90)
    header = f"{'检索策略':<30} {'问题数':<8} {'回答准确率':<12} {'引用召回率':<12} {'引用一致率':<12} {'平均首token':<12}"
    print(header)
    print("-" * 90)

    order = ['keyword', 'vector', 'hybrid', 'hybrid_rerank']
    for key in order:
        if key not in all_results:
            continue
        m = all_results[key]['metrics']
        name = all_results[key]['name']
        print(f"{name:<30} {m['total']:<8} {m['accuracy']:.1%}        {m['citation_recall']:.1%}        {m['citation_consistency']:.1%}        {m['avg_first_token_ms']:.0f}ms")


if __name__ == '__main__':
    dataset_path = '/app/eval_datasets/rag_qa/qa_30_questions.json'
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]

    print("RAG QA 策略对比评测")
    print(f"数据集: {dataset_path}")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    results = run_strategy_comparison(dataset_path, limit=None)
    print_comparison_table(results)

    # 保存结果
    output_path = '/app/eval_results/strategy_comparison.json'
    os.makedirs('/app/eval_results', exist_ok=True)

    # 清理不可序列化的对象
    clean_results = {}
    for key, val in results.items():
        clean_results[key] = {
            'name': val['name'],
            'metrics': val['metrics'],
            'results': [{
                k: v for k, v in r.items()
                if k not in ('judge_scores',)
            } for r in val['results']],
        }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(clean_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存至: {output_path}")
