"""
================================================================
  第 4 课：单头注意力 —— Attention 的核心机制
================================================================

这是 Transformer 最重要的一课。

Attention 回答的核心问题：
  在预测下一个词时，前面的哪些词最重要？

比如："巴黎是法国的___"
  → "巴黎" 和 "法国" 很重要，"是" 和 "的" 不太重要
  → Attention 就是让模型自动学会做这种判断

本课你会学到：
  - Q, K, V 是什么，从哪来
  - 为什么要分 Q, K, V？一个不行吗？
  - Scaled Dot-Product 每一步的含义
  - Causal Mask 为什么必须存在

运行: uv run python 04_single_head_attention.py
================================================================
"""

import torch
import torch.nn.functional as F
import math


def separator(title: str):
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}\n")


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"设备: {device}")

# 我们用一个有意义的序列来演示
tokens = ["巴黎", "是", "法国", "的", "首都"]
seq_len = len(tokens)
d_model = 8  # 小维度便于观察

torch.manual_seed(42)

# 假设这是经过 Embedding + PE 之后的输入
x = torch.randn(1, seq_len, d_model).to(device)  # (batch=1, seq_len=5, d_model=8)

print(f"输入序列: {tokens}")
print(f"输入形状: {x.shape}")


# ──────────────────────────────────────────
# 1. Q, K, V 从哪来？
# ──────────────────────────────────────────
separator("1. Q, K, V 从哪来？")

print(
    """
  每个 token 的向量（来自上一步的 Embedding + PE）经过三个不同的
  线性变换（矩阵乘法），得到三个不同的向量：

    Q = x × W_Q    (Query，查询向量)
    K = x × W_K    (Key，键向量)
    V = x × W_V    (Value，值向量)

  W_Q, W_K, W_V 是三个独立的可训练权重矩阵。
"""
)

d_k = d_model  # 单头时 Q/K/V 维度通常等于 d_model

W_Q = torch.nn.Linear(d_model, d_k, bias=False).to(device)
W_K = torch.nn.Linear(d_model, d_k, bias=False).to(device)
W_V = torch.nn.Linear(d_model, d_k, bias=False).to(device)

Q = W_Q(x)  # (1, 5, 8)
K = W_K(x)  # (1, 5, 8)
V = W_V(x)  # (1, 5, 8)

print(f"  W_Q 形状: {W_Q.weight.shape}  (d_k × d_model 的权重矩阵)")
print(f"  W_K 形状: {W_K.weight.shape}")
print(f"  W_V 形状: {W_V.weight.shape}")
print(f"\n  Q 形状: {Q.shape}")
print(f"  K 形状: {K.shape}")
print(f"  V 形状: {V.shape}")

print(f"\n  每个 token 现在有 3 个不同的向量表示。")
print(f"  比如 token '{tokens[0]}':")
print(f"    Q = {Q[0, 0, :4].detach().cpu().tolist()} ...")
print(f"    K = {K[0, 0, :4].detach().cpu().tolist()} ...")
print(f"    V = {V[0, 0, :4].detach().cpu().tolist()} ...")


# ──────────────────────────────────────────
# 2. 为什么要分 Q, K, V？
# ──────────────────────────────────────────
separator("2. 为什么要分 Q, K, V？不能只用一个向量吗？")

print(
    """
  类比图书馆检索系统：

  你想找一本关于"法国历史"的书：

    Query (Q) = 你的搜索词："法国历史"
    Key (K)   = 每本书的标签/关键词
    Value (V) = 每本书的实际内容

  检索过程：
    1. 用你的 Query 和每本书的 Key 计算匹配度
    2. 匹配度高的书，它的 Value（内容）对你更有用
    3. 按匹配度加权，综合所有书的内容，得到你的答案

  为什么不能只用一个向量？

    如果 Q = K = V = x（同一个向量），那相似的词就只能关注相似的词
    "巴黎"最关注的永远是跟"巴黎"最像的词

    但实际上：
    - "首都" 这个词在预测时，需要关注的是 "巴黎" 和 "法国"
    - "首都" 和 "巴黎" 在语义上并不相似
    - 通过分开的 Q/K 映射，模型可以学到：
      "首都的 Q 向量" 和 "巴黎的 K 向量" 匹配度高
      即使原始 embedding 不太像

  简单说：分开 Q/K 让模型能学到 "谁应该关注谁" 这种非对称关系
"""
)


# ──────────────────────────────────────────
# 3. 第一步：计算注意力分数
# ──────────────────────────────────────────
separator("3. 第一步：Q × K^T → 原始注意力分数")

print(
    """
  对每一对 (token_i, token_j)，计算：
    score(i, j) = Q_i · K_j  （向量点积）

  点积衡量的是两个向量的"方向相似度"：
    - 方向相同 → 点积大（正值）
    - 方向相反 → 点积小（负值）
    - 正交 → 点积接近 0

  矩阵化：一次性算完所有 pair
    Scores = Q × K^T  （矩阵乘法）
"""
)

# Q: (1, 5, 8)  K^T: (1, 8, 5)  → Scores: (1, 5, 5)
scores = torch.matmul(Q, K.transpose(-2, -1))

print(f"  Q 形状:   {Q.shape}")
print(f"  K^T 形状: {K.transpose(-2, -1).shape}")
print(f"  分数矩阵: {scores.shape}  (5×5，每对 token 一个分数)\n")

# 打印分数矩阵
scores_cpu = scores[0].detach().cpu()
header = "           " + "  ".join(f"{t:>6s}" for t in tokens)
print(header)
print("  " + "-" * (len(header) - 2))
for i in range(seq_len):
    row = [f"{scores_cpu[i][j]:+6.2f}" for j in range(seq_len)]
    print(f"  {tokens[i]:>4s}  |  {'  '.join(row)}")

print(
    f"""
  解读 score(i, j)：
    "当模型在位置 i 时，它对位置 j 的原始关注度"

  注意：这些分数还没有归一化，数值范围不固定。
  而且还没有阻止"偷看未来"。
"""
)


# ──────────────────────────────────────────
# 4. 第二步：缩放（除以 sqrt(d_k)）
# ──────────────────────────────────────────
separator("4. 第二步：为什么要除以 sqrt(d_k)？")

print(
    f"""
  公式：Scaled_Scores = Scores / sqrt(d_k)

  我们的 d_k = {d_k}，所以除以 sqrt({d_k}) = {math.sqrt(d_k):.4f}

  为什么要缩放？论文给出的解释：

  假设 Q 和 K 的每个维度都是均值 0、方差 1 的随机变量。
  那么 Q · K = Σ(q_i × k_i)，这个求和有 d_k 项。

  每一项 q_i × k_i 的方差 = 1
  d_k 项求和后，方差 = d_k

  所以 d_k 越大，点积的绝对值越大。
"""
)

# 实际验证
print("  实验验证：\n")
for test_dk in [8, 64, 512, 4096]:
    q_test = torch.randn(1000, test_dk)
    k_test = torch.randn(1000, test_dk)
    dots = (q_test * k_test).sum(dim=1)
    print(
        f"    d_k = {test_dk:>4d} → 点积的标准差 = {dots.std():.2f}"
        f"  (理论值 sqrt({test_dk}) = {math.sqrt(test_dk):.2f})"
    )

print(
    f"""
  如果不缩放：
    d_k = 4096 时，点积值可能达到 ±100 甚至更大
    →  softmax 的输入值太大
    →  softmax 输出接近 one-hot（某个位置≈1，其他≈0）
    →  梯度几乎为 0（梯度消失）
    →  训练不动！

  除以 sqrt(d_k) 后，点积值的方差 ≈ 1，softmax 表现正常。
"""
)

scaled_scores = scores / math.sqrt(d_k)
print(f"  缩放后的分数矩阵：")
ss_cpu = scaled_scores[0].detach().cpu()
header = "           " + "  ".join(f"{t:>6s}" for t in tokens)
print(header)
for i in range(seq_len):
    row = [f"{ss_cpu[i][j]:+6.3f}" for j in range(seq_len)]
    print(f"  {tokens[i]:>4s}  |  {'  '.join(row)}")


# ──────────────────────────────────────────
# 5. 第三步：Causal Mask
# ──────────────────────────────────────────
separator("5. 第三步：因果掩码 —— 不能偷看未来")

print(
    """
  核心问题：在自回归生成时，预测第 3 个 token 时
  不应该看到第 4、5 个 token（那些还没生成呢！）

  做法：把"未来位置"的分数设为 -∞
  → softmax(-∞) = 0
  → 对应位置的注意力权重为 0，等于完全看不到
"""
)

# 创建上三角掩码
mask = torch.triu(torch.ones(seq_len, seq_len, device=device), diagonal=1).bool()

print(f"  掩码矩阵 (True = 被遮挡的未来位置):\n")
header = "           " + "  ".join(f"{t:>6s}" for t in tokens)
print(header)
for i in range(seq_len):
    row = []
    for j in range(seq_len):
        if mask[i][j]:
            row.append("   -∞ ")
        else:
            row.append(f"{ss_cpu[i][j]:+6.3f}")
    print(f"  {tokens[i]:>4s}  |  {'  '.join(row)}")

print(
    f"""
  对角线以上全是 -∞：
    "巴黎" 只能看自己（还没有其他 token）
    "是"   能看 "巴黎" 和自己
    "法国" 能看 "巴黎"、"是"、自己
    ...
    "首都" 能看所有 token
"""
)

masked_scores = scaled_scores.masked_fill(mask.unsqueeze(0), float("-inf"))


# ──────────────────────────────────────────
# 6. 第四步：Softmax
# ──────────────────────────────────────────
separator("6. 第四步：Softmax → 注意力权重")

print(
    """
  Softmax 做两件事：
    1. 把任意实数值变成正数
    2. 让每一行的值加起来 = 1（变成概率分布）

  公式：softmax(x_i) = exp(x_i) / Σ exp(x_j)

  -∞ 经过 softmax 后变成 0（因为 exp(-∞) = 0）
"""
)

attn_weights = F.softmax(masked_scores, dim=-1)

aw_cpu = attn_weights[0].detach().cpu()
print(f"  注意力权重（每行加起来 = 1.0）:\n")
header = "           " + "  ".join(f"{t:>6s}" for t in tokens)
print(header)
print("  " + "-" * (len(header) - 2))
for i in range(seq_len):
    row_vals = [aw_cpu[i][j].item() for j in range(seq_len)]
    row = [f"{v:6.3f}" for v in row_vals]
    row_sum = sum(row_vals)
    print(f"  {tokens[i]:>4s}  |  {'  '.join(row)}  | Σ = {row_sum:.3f}")

print(
    f"""
  解读：
  - "巴黎" 行：100% 关注自己（因为没有其他可见 token）
  - "首都" 行：可以看到所有 token，注意力按学到的 Q/K 分配
  - 未来位置的权重 = 0.000（被 mask 掉了）

  这个矩阵就是 "谁在关注谁" 的完整描述！
"""
)


# ──────────────────────────────────────────
# 7. 第五步：加权求和
# ──────────────────────────────────────────
separator("7. 第五步：用注意力权重加权 Value 向量")

print(
    """
  最后一步：Output = Attention_Weights × V

  对于每个 token i：
    output_i = Σ_j (attn_weight[i][j] × V[j])

  直觉：
    "首都" 的输出 = 0.15 × V("巴黎") + 0.20 × V("是") + ...
    它是前面所有 token 的 Value 的加权组合
    权重由 Q/K 的匹配度决定
"""
)

output = torch.matmul(attn_weights, V)
print(f"  注意力权重: {attn_weights.shape}")
print(f"  V:          {V.shape}")
print(f"  输出:       {output.shape}")

print(f"\n  输出形状和输入完全一样！")
print(f"  输入:  (batch=1, seq_len=5, d_model=8)")
print(f"  输出:  (batch=1, seq_len=5, d_model=8)")

# 手动验证最后一个 token 的输出
print(f"\n  手动验证 '{tokens[-1]}' 的输出：")
manual_output = torch.zeros(d_k).to(device)
for j in range(seq_len):
    weight = aw_cpu[-1][j].item()
    if weight > 0.001:
        manual_output += weight * V[0, j]
        print(f"    + {weight:.3f} × V('{tokens[j]}')")

diff = (manual_output - output[0, -1]).abs().max().item()
print(f"\n  手动计算 vs 矩阵乘法的最大误差: {diff:.8f}")
print(f"  → 完全一致！矩阵乘法只是并行化的加权求和。")


# ──────────────────────────────────────────
# 8. 完整公式总结
# ──────────────────────────────────────────
separator("8. 完整公式一览")

print(
    """
  Attention(Q, K, V) = softmax( Q × K^T / sqrt(d_k) + Mask ) × V

  分解为 5 步：

  ┌─────────────────────────────────────────────────────────────┐
  │  1. Q = x × W_Q,  K = x × W_K,  V = x × W_V              │
  │     → 线性变换，把输入映射到 Q/K/V 空间                      │
  │                                                             │
  │  2. Scores = Q × K^T                                        │
  │     → 计算所有 token 对之间的原始匹配分数                     │
  │                                                             │
  │  3. Scaled = Scores / sqrt(d_k)                             │
  │     → 缩放，防止点积值太大导致梯度消失                        │
  │                                                             │
  │  4. Masked = Scaled + CausalMask (未来位置设为 -∞)           │
  │     → 确保自回归生成时不能看到未来                            │
  │                                                             │
  │  5. Output = softmax(Masked) × V                            │
  │     → 归一化为概率分布，然后加权求和 Value 向量               │
  └─────────────────────────────────────────────────────────────┘

  整个过程没有循环，全是矩阵运算，所以可以在 GPU 上高度并行！

  但这只是"单头"注意力，只能学一种关注模式。
  → 下一课：Multi-Head Attention，让模型同时从多个角度关注
  → 运行 05_multi_head_attention.py
"""
)
