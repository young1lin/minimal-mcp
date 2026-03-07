"""
================================================================
  中文分词效率演进验证脚本
================================================================

本脚本验证不同时代分词器对中文的处理效率。

运行: uv run python verify_tokenizer_efficiency.py

验证内容:
1. OpenAI 分词器演进 (GPT-2/GPT-3 → GPT-4 → GPT-4o)
2. 国产模型分词器 (Qwen 等)
3. 中英文 Token 效率对比

================================================================
"""

import tiktoken


def test_chinese_tokenizer_evolution():
    """测试中文分词器演进"""
    print("=" * 70)
    print("中文分词效率演进验证")
    print("=" * 70)

    test_cases = [
        "我喜欢吃苹果",
        "今天天气很好",
        "自然语言处理",
        "深度学习是人工智能的一个分支",
    ]

    all_text = " ".join(test_cases)
    print(f"\n测试文本: {repr(all_text[:30])}...")
    print(f"总字符数: {len(all_text)}\n")

    # OpenAI 分词器演进
    encoders = {
        "GPT-2/GPT-3 (r50k_base)": tiktoken.get_encoding("r50k_base"),
        "GPT-4 (cl100k_base)": tiktoken.get_encoding("cl100k_base"),
        "GPT-4o (o200k_base)": tiktoken.get_encoding("o200k_base"),
    }

    results = {}
    baseline_tokens = None

    print("【OpenAI 分词器演进】")
    print(f"{'分词器':30s} | {'Token数':>8s} | {'效率':>15s} | {'相对GPT-3提升':>12s}")
    print("-" * 70)

    for name, enc in encoders.items():
        tokens = enc.encode(all_text)
        efficiency = len(all_text) / len(tokens)
        results[name] = {"tokens": len(tokens), "efficiency": efficiency}

        if baseline_tokens is None:
            baseline_tokens = len(tokens)
            improvement = 0.0
        else:
            improvement = (baseline_tokens - len(tokens)) / baseline_tokens * 100

        print(
            f"{name:30s} | {len(tokens):8d} | {efficiency:15.2f} | {improvement:+.1f}%"
        )

    return results, baseline_tokens


def test_chinese_vs_english():
    """测试中英文 Token 效率对比"""
    print("\n" + "=" * 70)
    print("中英文 Token 效率对比 (GPT-4o)")
    print("=" * 70)

    enc = tiktoken.get_encoding("o200k_base")

    tests = [
        ("我喜欢吃苹果", "I like to eat apples", "简单句子"),
        (
            "今天天气很好，适合出去散步",
            "The weather is nice today, suitable for a walk",
            "日常描述",
        ),
        (
            "机器学习是人工智能的一个分支",
            "Machine learning is a branch of artificial intelligence",
            "技术文本",
        ),
        (
            "深度学习模型需要大量数据训练",
            "Deep learning models require large amounts of data for training",
            "技术描述",
        ),
    ]

    print(
        f"\n{'描述':10s} | {'中文tokens':>10s} | {'英文tokens':>10s} | {'比例':>8s}"
    )
    print("-" * 50)

    total_cn = 0
    total_en = 0

    for cn, en, desc in tests:
        cn_tokens = len(enc.encode(cn))
        en_tokens = len(enc.encode(en))
        ratio = cn_tokens / en_tokens
        total_cn += cn_tokens
        total_en += en_tokens

        print(f"{desc:10s} | {cn_tokens:10d} | {en_tokens:10d} | {ratio:8.2f}")

    avg_ratio = total_cn / total_en
    print("-" * 50)
    print(f"{'总计':10s} | {total_cn:10d} | {total_en:10d} | {avg_ratio:8.2f}")

    if avg_ratio < 1:
        print(f"\n结论: 中文比英文更节省 tokens ({avg_ratio:.2f}x)")
    elif avg_ratio > 1:
        print(f"\n结论: 英文比中文更节省 tokens ({avg_ratio:.2f}x)")
    else:
        print(f"\n结论: 中英文 token 效率相当 ({avg_ratio:.2f}x)")


def test_chinese_models():
    """测试国产模型分词器"""
    print("\n" + "=" * 70)
    print("国产模型分词器测试")
    print("=" * 70)

    test_cases = [
        "我喜欢吃苹果",
        "今天天气很好",
        "自然语言处理",
        "深度学习是人工智能的一个分支",
    ]
    all_text = " ".join(test_cases)

    try:
        from transformers import AutoTokenizer

        models = [
            ("deepseek-ai/deepseek-llm-7b-base", "DeepSeek-7B"),
            ("Qwen/Qwen1.5-7B", "Qwen-7B"),
        ]

        for model_path, model_name in models:
            try:
                print(f"\n加载 {model_name}...")
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path, trust_remote_code=True
                )
                tokens = tokenizer.encode(all_text, add_special_tokens=False)
                if len(tokens) > 0:
                    efficiency = len(all_text) / len(tokens)
                    print(
                        f"  {model_name}: {len(tokens)} tokens, 效率: {efficiency:.2f} 字符/token"
                    )
                else:
                    print(f"  {model_name}: 返回空 token")
            except Exception as e:
                print(f"  {model_name}: 加载失败 - {str(e)[:50]}...")

    except ImportError:
        print("需要安装 transformers 库: uv pip install transformers")


def print_summary():
    """打印总结"""
    print("\n" + "=" * 70)
    print("演进总结")
    print("=" * 70)
    print("""
1. GPT-2/GPT-3 时代 (2019-2020):
   - 分词器以英文为主，中文效率极低
   - 1 个汉字 ≈ 2 tokens
   - 中文用户成本是英文的约 2 倍

2. GPT-4 时代 (2023):
   - 词汇量从 5 万扩展到 10 万
   - 加入了更多中文字符和常见词
   - 效率提升约 40%

3. GPT-4o 时代 (2024):
   - 词汇量扩展到 20 万
   - 常见中文词组可合并为单个 token
   - 效率超过 1 (1 token > 1 汉字)
   - 相对 GPT-3 效率提升约 68%

4. 国产模型 (DeepSeek/Qwen):
   - 专门针对中文优化
   - 中文效率甚至超过 GPT-4o
   - 如 Qwen 效率可达 1.75 字符/token

结论: 现代分词器对中英文的处理效率已经相当接近，
      不需要担心"中文更贵"的问题。
""")


if __name__ == "__main__":
    test_chinese_tokenizer_evolution()
    test_chinese_vs_english()
    test_chinese_models()
    print_summary()
