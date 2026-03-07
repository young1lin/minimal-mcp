"""
================================================================
  第 1 课：Tokenizer —— 文本如何变成数字
================================================================

核心问题：神经网络只能处理数字，那文本怎么输入？

答案分两步：
  1. Tokenizer：文本 → 整数 ID（本课内容）
  2. Embedding：整数 ID → 向量（下一课）

本课你会学到：
  - 什么是 Token
  - 为什么不直接按字符或按词切分
  - BPE (Byte Pair Encoding) 算法的核心思路
  - 同样的文本，不同 Tokenizer 结果完全不同

运行: uv run python 01_tokenizer.py
================================================================
"""

import tiktoken


def separator(title: str):
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}\n")


# ──────────────────────────────────────────
# 1. 最朴素的想法：按字符切分
# ──────────────────────────────────────────
separator("1. 最朴素的想法：按字符切分")

text = "Hello world"
chars = list(text)
char_ids = [ord(c) for c in text]  # ASCII / Unicode 编码

print(f"原文: '{text}'")
print(f"按字符切: {chars}")
print(f"字符编码: {char_ids}")
print(f"Token 数: {len(chars)}")

print(
    """
问题：
  - "Hello" 要 5 个 token，太碎了，模型要处理很长的序列
  - 模型很难学到 "H-e-l-l-o" 这 5 个字符合起来是一个词
  - 效率极低：一句话可能要几百个 token
"""
)


# ──────────────────────────────────────────
# 2. 另一个极端：按词切分
# ──────────────────────────────────────────
separator("2. 另一个极端：按词切分（空格分割）")

text = "I love transformers"
words = text.split(" ")
# 假设我们有一个词表
vocab = {"I": 0, "love": 1, "transformers": 2, "hate": 3, "neural": 4, "networks": 5}

word_ids = [vocab[w] for w in words]
print(f"原文: '{text}'")
print(f"按词切:  {words}")
print(f"词 ID:   {word_ids}")

print(
    """
问题：
  - 遇到没见过的词怎么办？比如 "transformerish"，词表里没有，直接崩了
  - 英文还好，中文呢？"我喜欢自然语言处理" 怎么切？分词本身就是难题
  - 词表会极其庞大（英文几十万词），embedding 矩阵太大
"""
)

# ──────────────────────────────────────────
# 3. BPE：两个极端之间的平衡
# ──────────────────────────────────────────
separator("3. BPE (Byte Pair Encoding)：聪明的折中方案")

print(
    """
BPE 的核心思路（简化版）：

  第 0 步：从最小单位（字节/字符）开始
  第 1 步：统计训练语料中，哪两个相邻的 token 一起出现最多
  第 2 步：把这对 token 合并成一个新 token
  第 3 步：重复第 1-2 步，直到词表达到预设大小

举例：假设语料是 "low lower lowest"

  初始词表: ['l', 'o', 'w', 'e', 'r', 's', 't', ' ']

  统计发现 'l' 和 'o' 经常相邻 → 合并成 'lo'
  词表变成: ['l', 'o', 'w', 'e', 'r', 's', 't', ' ', 'lo']

  统计发现 'lo' 和 'w' 经常相邻 → 合并成 'low'
  词表变成: [..., 'lo', 'low']

  统计发现 'low' 和 'e' 经常相邻 → 合并成 'lowe'
  ...以此类推

结果：
  - 常见的词（如 "the"）会被当作一个 token
  - 罕见的词会被拆成几个子词（subword）
  - 永远不会遇到"没见过的词"，因为最坏情况下可以退回到字节级别
"""
)


# ──────────────────────────────────────────
# 4. 实际操作：用 tiktoken 看真实 Tokenizer
# ──────────────────────────────────────────
separator("4. 实际操作：GPT 系列使用的 BPE Tokenizer")

# cl100k_base 是 GPT-4 / ChatGPT 使用的编码方案
enc = tiktoken.get_encoding("cl100k_base")

print(f"词表大小: {enc.n_vocab:,} 个 token")
print(f"（这意味着 Embedding 矩阵有 {enc.n_vocab:,} 行）\n")


# ──── 英文示例 ────
separator("4a. 英文 Tokenization")

examples_en = [
    "Hello",
    "Hello world",
    "I love natural language processing",
    "Transformerish",  # 一个虚构的词
    "antidisestablishmentarianism",  # 一个超长的真实英文词
]

for text in examples_en:
    ids = enc.encode(text)
    # 逐个解码，看每个 token 对应什么
    parts = [enc.decode([tid]) for tid in ids]
    print(f"  '{text}'")
    print(f"    Token 数: {len(ids)}")
    print(f"    切分结果: {parts}")
    print(f"    Token ID: {ids}")
    print()


# ──── 中文示例 ────
separator("4b. 中文 Tokenization")

examples_zh = [
    "你好",
    "我喜欢自然语言处理",
    "Transformer 注意力机制",  # 中英混合
]

for text in examples_zh:
    ids = enc.encode(text)
    parts = [enc.decode([tid]) for tid in ids]

    print(f"  '{text}'")
    print(f"    Token 数: {len(ids)}")
    print(f"    切分结果: {parts}")
    print(f"    Token ID: {ids}")
    print()

print(
    """
💡 观察：
  - 常见英文词 "Hello" 是 1 个 token，不常见的词会被拆开
  - 中文每个字通常是 1-3 个 token（因为 BPE 训练语料以英文为主）
  - 这就是为什么中文 prompt 消耗的 token 数量更多
"""
)


# ──── 代码示例 ────
separator("4c. 代码也是文本！")

code = "def hello():\n    print('world')"
ids = enc.encode(code)
parts = [enc.decode([tid]) for tid in ids]

print(f"  代码: {repr(code)}")
print(f"  Token 数: {len(ids)}")
print(f"  切分结果: {parts}")
print(f"\n  注意：空格、换行、缩进都是 token 的一部分")


# ──────────────────────────────────────────
# 5. Token ID 的本质：只是一个查表索引
# ──────────────────────────────────────────
separator("5. Token ID 的本质")

text = "AI"
ids = enc.encode(text)
print(f"  '{text}' 的 Token ID: {ids}")
print(
    f"""
  这个数字本身没有任何数学含义！
  它不代表"AI"和其他词的相似度，不代表任何语义信息。
  它只是词表里第 {ids[0]} 行的索引号，就像数组下标一样。

  真正的语义信息在下一步 —— Embedding 层 —— 才会出现。

  类比：
    Token ID 就像你的身份证号码
    身份证号 440106... 并不代表你是什么样的人
    它只是一个唯一标识符，用来在数据库里找到你的完整信息

  同理：
    Token ID 只是一个索引，用来在 Embedding 矩阵里找到对应的向量
"""
)


# ──────────────────────────────────────────
# 6. 特殊 Token
# ──────────────────────────────────────────
separator("6. 特殊 Token")

print(
    """
  除了普通文本 token，还有一些特殊 token：

  - BOS (Beginning of Sequence): 序列开始标记
  - EOS (End of Sequence): 序列结束标记
    → 模型生成到这个 token 时就停止输出
  - PAD (Padding): 填充标记，用于对齐不同长度的序列

  不同模型的特殊 token 不同，但概念是一样的。

  这也回答了你之前的问题"直到停止输出"具体是怎么停的：
  → 模型预测出了 EOS token 的概率最高（或被采样到）
"""
)


# ──────────────────────────────────────────
# 总结
# ──────────────────────────────────────────
separator("本课总结")

print(
    """
  文本 ──[Tokenizer]──→ Token ID 序列

  "I love AI"  →  [40, 3021, 15592]

  关键理解：
  ✓ Token 不等于字符，不等于词，而是介于两者之间的 "子词" (subword)
  ✓ BPE 根据训练语料中的频率决定怎么切分
  ✓ Token ID 只是索引号，没有语义信息
  ✓ 同一段文本，用不同 Tokenizer 会得到完全不同的 ID

  下一课：这些整数 ID 如何变成神经网络能处理的向量？
  → 运行 02_embedding.py
"""
)
