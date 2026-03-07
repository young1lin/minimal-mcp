"""
================================================================
  第 3 课：Positional Encoding —— 让模型知道顺序
================================================================

上一课的遗留问题：
  Embedding 只是给每个 token 一个向量，但不知道它在第几个位置。
  "猫吃鱼" 和 "鱼吃猫" 对模型来说一模一样！

本课你会学到：
  - 为什么 Transformer 天生不知道顺序
  - Positional Encoding 的 sin/cos 公式怎么来的
  - 为什么 sin/cos 而不是直接用 [1, 2, 3, ...]
  - 论文中的 sqrt(d_model) 缩放

运行: uv run python 03_positional_encoding.py
================================================================
"""

import torch
import math
import tiktoken


def separator(title: str):
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}\n")


# ──────────────────────────────────────────
# 1. 为什么 Transformer 不知道顺序？
# ──────────────────────────────────────────
separator("1. 为什么需要位置编码？")

print(
    """
  RNN 天生知道顺序：它一个一个处理 token，第 3 个 token 的计算
  依赖第 2 个的结果，第 2 个依赖第 1 个。顺序写死在计算图里了。

  Transformer 不同：Attention 机制看的是"所有 token 和所有 token"
  的关系，是通过矩阵乘法一次性并行算的。

  打个比方：
  - RNN 像排队进门，你知道前面是谁，后面是谁
  - Transformer 像把所有人扔进一个房间，谁和谁都能交流
    → 但你不知道大家原来站的什么位置！

  解决方案：在每个人身上贴一个"我是第几号"的标签
  这个标签就是 Positional Encoding (PE)
"""
)


# ──────────────────────────────────────────
# 2. 最朴素的想法：直接用位置数字
# ──────────────────────────────────────────
separator("2. 最朴素的想法行不行？")

print(
    """
  方案 A：直接把位置编号加到向量里？

    位置 0 → 加 0
    位置 1 → 加 1
    位置 2 → 加 2
    ...
    位置 4096 → 加 4096

  问题：
    ① 数值范围太大，位置靠后的 token 加的值远大于 embedding 本身
    ② 模型没见过长度 5000 的序列，遇到位置 5000 会崩溃
    ③ 相对关系不明显：位置 1000 和 1001 的差，跟 1 和 2 的差一样吗？

  方案 B：归一化到 [0, 1]？

    位置 0 → 加 0.0
    位置 1 → 加 0.001
    ...
    位置 999 → 加 1.0

  问题：
    ① 不同长度的序列，同一个位置编码不同（100 个 token 时位置 50 = 0.5,
       200 个 token 时位置 50 = 0.25）
    ② 精度问题：序列越长，相邻位置的差异越小
"""
)


# ──────────────────────────────────────────
# 3. 论文的方案：sin/cos 编码
# ──────────────────────────────────────────
separator("3. Transformer 论文的方案：sin/cos 编码")

print(
    """
  论文公式 (Section 3.5)：

    PE(pos, 2i)   = sin(pos / 10000^(2i / d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i / d_model))

  其中：
    pos  = token 在序列中的位置（0, 1, 2, ...）
    i    = 向量的维度索引（0, 1, 2, ..., d_model/2 - 1）
    2i   = 偶数维度用 sin
    2i+1 = 奇数维度用 cos

  直觉：想象一堆不同频率的"钟表"

    维度 0,1：秒针（变化很快，每个位置都不同）
    维度 2,3：分针（变化较慢）
    维度 4,5：时针（变化更慢）
    ...
    维度 d-2,d-1：年历（变化极慢）

  不同位置组合起来，就像不同时间的钟表读数，独一无二！
"""
)


# ──────────────────────────────────────────
# 4. 手动计算几个值
# ──────────────────────────────────────────
separator("4. 手动算几个值，建立直觉")

d_model = 8  # 用小维度演示
max_len = 6  # 6 个位置

print(f"参数：d_model = {d_model}, 序列长度 = {max_len}\n")

# 手动计算
pe = torch.zeros(max_len, d_model)

for pos in range(max_len):
    for i in range(0, d_model, 2):
        denominator = 10000 ** (i / d_model)
        pe[pos, i] = math.sin(pos / denominator)
        pe[pos, i + 1] = math.cos(pos / denominator)

# 打印完整 PE 矩阵
dims = [f"d{j}" for j in range(d_model)]
header = "pos  " + "  ".join(f"{d:>7s}" for d in dims)
print(header)
print("-" * len(header))
for pos in range(max_len):
    row = [f"{pe[pos, j]:+.4f}" for j in range(d_model)]
    print(f" {pos}   {'  '.join(row)}")

print(
    f"""
观察：
  - 每一行（每个位置）的值都不同 → 唯一标识
  - 左边列（低维度, d0/d1）变化快 → "秒针"
  - 右边列（高维度, d6/d7）变化慢 → "时针"
  - 所有值都在 [-1, +1] 范围内 → 数值稳定
"""
)


# ──────────────────────────────────────────
# 5. 验证 sin/cos 的一个优美性质
# ──────────────────────────────────────────
separator("5. 关键性质：相对位置可以通过线性变换得到")

print(
    """
  sin/cos 编码有一个关键数学性质：

  PE(pos + k) 可以表示为 PE(pos) 的线性变换！

  因为三角函数的和角公式：
    sin(a + b) = sin(a)cos(b) + cos(a)sin(b)
    cos(a + b) = cos(a)cos(b) - sin(a)sin(b)

  这意味着：
    从位置 3 "跳到" 位置 5（偏移 k=2）
    和从位置 100 "跳到" 位置 102（同样偏移 k=2）
    用的是同一个线性变换矩阵！

  → 模型可以很容易学到"往前看 k 个位置"这种相对关系
"""
)

# 验证：PE(pos=3) 和 PE(pos=5) 的关系
pos_3 = pe[3]
pos_5 = pe[5]
k = 2  # 偏移量

# 对每对 sin/cos 维度验证
print("验证：PE(3+2) 是否等于 PE(3) 的线性变换？\n")
for i in range(0, d_model, 2):
    freq = 1.0 / (10000 ** (i / d_model))
    # 变换矩阵
    cos_k = math.cos(k * freq)
    sin_k = math.sin(k * freq)

    # PE(pos+k) = M @ PE(pos)
    # [sin(pos+k)]   [cos(k)  sin(k)] [sin(pos)]
    # [cos(pos+k)] = [-sin(k) cos(k)] [cos(pos)]
    predicted_sin = cos_k * pe[3, i] + sin_k * pe[3, i + 1]
    predicted_cos = -sin_k * pe[3, i] + cos_k * pe[3, i + 1]
    actual_sin = pe[5, i]
    actual_cos = pe[5, i + 1]

    match_sin = "✓" if abs(predicted_sin - actual_sin) < 1e-6 else "✗"
    match_cos = "✓" if abs(predicted_cos - actual_cos) < 1e-6 else "✗"
    print(
        f"  维度 {i},{i+1}: 预测 ({predicted_sin:+.4f}, {predicted_cos:+.4f})"
        f"  实际 ({actual_sin:+.4f}, {actual_cos:+.4f})  {match_sin}{match_cos}"
    )

print("\n→ 完美匹配！这证明了相对位置关系确实可以通过线性变换捕获。")


# ──────────────────────────────────────────
# 6. sqrt(d_model) 缩放
# ──────────────────────────────────────────
separator("6. 为什么 Embedding 要乘以 sqrt(d_model)？")

print(
    """
  论文 Section 3.4 写道：
    "we multiply those weights by sqrt(d_model)"

  也就是说，最终输入 = Embedding × sqrt(d_model) + PE

  为什么？

  Embedding 向量在初始化时，每个维度的值大约在 [-1, +1] 之间（标准正态）
  Positional Encoding 的值也在 [-1, +1] 之间（sin/cos 的范围）

  但 Embedding 向量的 "能量"（L2范数）大约是 sqrt(d_model)
  而 PE 的能量也大约是 sqrt(d_model)

  如果不缩放，当 d_model 很大时：
    Embedding 的范数 ≈ sqrt(d_model)
    PE 的范数        ≈ sqrt(d_model/2)

  它们差不多，但论文选择乘以 sqrt(d_model) 让 embedding 的信号更强：
"""
)

d_model_real = 512
embedding_demo = torch.nn.Embedding(1000, d_model_real)

# 随机取一个 embedding 向量
vec = embedding_demo.weight[42].detach()
norm_before = vec.norm().item()
norm_after = (vec * math.sqrt(d_model_real)).norm().item()

# 计算 PE 的范数
pe_demo = torch.zeros(d_model_real)
for i in range(0, d_model_real, 2):
    denominator = 10000 ** (i / d_model_real)
    pe_demo[i] = math.sin(1.0 / denominator)
    pe_demo[i + 1] = math.cos(1.0 / denominator)
pe_norm = pe_demo.norm().item()

print(f"  d_model = {d_model_real}")
print(f"  Embedding 向量范数（缩放前）: {norm_before:.2f}")
print(f"  Embedding 向量范数（× sqrt(d_model) 后）: {norm_after:.2f}")
print(f"  PE 向量范数:                  {pe_norm:.2f}")
print(f"\n  缩放后，Embedding 的信号远强于 PE")
print(f"  → 语义信息为主，位置信息为辅")


# ──────────────────────────────────────────
# 7. 完整流程
# ──────────────────────────────────────────
separator("7. 把三课连起来：文本 → Token ID → Embedding → + PE")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
enc = tiktoken.get_encoding("cl100k_base")

text = "Attention is all you need"
token_ids = enc.encode(text)
parts = [enc.decode([tid]) for tid in token_ids]
seq_len = len(token_ids)
d_model = 64

# Embedding
embedding = torch.nn.Embedding(enc.n_vocab, d_model).to(device)
input_tensor = torch.tensor([token_ids], dtype=torch.long).to(device)
embedded = embedding(input_tensor)  # (1, seq_len, d_model)

# 缩放
scaled = embedded * math.sqrt(d_model)

# Positional Encoding
pe = torch.zeros(seq_len, d_model).to(device)
position = torch.arange(0, seq_len, dtype=torch.float).unsqueeze(1).to(device)
div_term = torch.exp(
    torch.arange(0, d_model, 2, dtype=torch.float).to(device)
    * (-math.log(10000.0) / d_model)
)
pe[:, 0::2] = torch.sin(position * div_term)
pe[:, 1::2] = torch.cos(position * div_term)

# 最终输入
final_input = scaled + pe.unsqueeze(0)  # 广播: (1, seq_len, d_model)

print(f"  文本: '{text}'")
print(f"   ↓ Tokenizer")
print(f"  Tokens: {parts}")
print(f"   ↓ Embedding 查表")
print(f"  形状: {embedded.shape}")
print(f"   ↓ × sqrt({d_model}) = × {math.sqrt(d_model):.2f}")
print(f"  形状: {scaled.shape}")
print(f"   ↓ + Positional Encoding")
print(f"  形状: {final_input.shape}")

print(f"\n  每个 token 现在是一个 {d_model} 维向量，同时包含了：")
print(f"    ① 语义信息（来自 Embedding）")
print(f"    ② 位置信息（来自 PE）")


# ──────────────────────────────────────────
# 总结
# ──────────────────────────────────────────
separator("本课总结")

print(
    f"""
  Embedding 向量 ──[× sqrt(d_model)]──→ ──[+ PE]──→ Transformer 输入

  关键理解：
  ✓ Transformer 的 Attention 本身没有位置概念
  ✓ sin/cos 编码用不同频率的波叠加，给每个位置唯一标识
  ✓ 关键数学性质：相对位置可以通过线性变换得到
  ✓ Embedding × sqrt(d_model) 是为了让语义信号强于位置信号
  ✓ PE 是固定的（不参与训练），Embedding 是训练出来的

  注意：现代模型（GPT、LLaMA）大多改用 RoPE (Rotary Position Embedding)
  原理相似但更优雅，效果更好。但 sin/cos PE 是理解一切的基础。

  现在我们有了完整的输入向量，下一课进入核心：
  → Attention 机制到底怎么计算？
  → 运行 04_single_head_attention.py
"""
)
