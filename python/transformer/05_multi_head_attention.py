"""
================================================================
  第 5 课：多头注意力 —— 同时从多个角度看世界
================================================================

上一课我们实现了单头注意力。
它能工作，但有一个根本问题：只能学一种关注模式。

本课你会学到：
  - 为什么一个 head 不够
  - 多个 head 怎么分工
  - 怎么拆分和拼接
  - 不同 head 真的会学到不同东西吗？

运行: uv run python 05_multi_head_attention.py
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
torch.manual_seed(42)

tokens = ["小明", "把", "妈妈", "买的", "苹果", "吃了"]
seq_len = len(tokens)
d_model = 12  # 选 12 是因为能被 2, 3, 4, 6 整除
batch_size = 1

x = torch.randn(batch_size, seq_len, d_model).to(device)


# ──────────────────────────────────────────
# 1. 为什么一个 head 不够？
# ──────────────────────────────────────────
separator("1. 为什么一个 head 不够？")

print(
    f"""
  想想句子 "小明把妈妈买的苹果吃了"

  当模型处理 "吃了" 这个 token 时，它需要同时知道：

    关系 1 - 语法主语："谁"吃了？ → "小明"
    关系 2 - 宾语：    吃了"什么"？ → "苹果"
    关系 3 - 句式框架："把...吃了" → "把"
    关系 4 - 修饰链：  苹果从哪来？ → "妈妈买的"

  一个 attention head 只有一组 Q/K 权重
  → 只能学一种 "什么该关注什么" 的模式
  → 如果学了"关注主语"，就没法同时"关注宾语"

  解决方案：用多个 head，每个 head 学不同的关注模式

  这就像一个团队：
    head 0：我负责盯语法关系
    head 1：我负责盯语义角色
    head 2：我负责盯距离较近的上下文
    head 3：我负责盯长距离依赖
    ...
  最后把所有人的信息汇总
"""
)


# ──────────────────────────────────────────
# 2. 多头的关键操作：拆分
# ──────────────────────────────────────────
separator("2. 关键操作：把 d_model 维切成 n_heads 份")

n_heads = 3
d_k = d_model // n_heads  # 每个 head 的维度

print(f"  d_model = {d_model}")
print(f"  n_heads = {n_heads}")
print(f"  d_k = d_model / n_heads = {d_model} / {n_heads} = {d_k}")

print(
    f"""
  不是每个 head 都做 {d_model} 维的注意力！
  而是每个 head 只在 {d_k} 维的子空间里工作。

  总计算量：{n_heads} 个 head × {d_k} 维 = {n_heads * d_k} 维 = d_model
  → 跟一个大 head 的计算量几乎一样！
"""
)

# 演示拆分过程
print("具体怎么拆：\n")

# Step 1: 计算完整的 Q (所有 head 一起算，更高效)
W_Q = torch.nn.Linear(d_model, d_model, bias=False).to(device)
Q_full = W_Q(x)  # (1, 6, 12)
print(
    f"  完整 Q: {Q_full.shape}  (batch={batch_size}, seq_len={seq_len}, d_model={d_model})"
)

# Step 2: reshape 拆成多个 head
Q_reshaped = Q_full.view(batch_size, seq_len, n_heads, d_k)
print(f"  reshape: {Q_reshaped.shape}  (batch, seq_len, n_heads={n_heads}, d_k={d_k})")

# Step 3: transpose 让 head 维度在前面（方便并行计算）
Q_multi = Q_reshaped.transpose(1, 2)
print(
    f"  transpose: {Q_multi.shape}  (batch, n_heads={n_heads}, seq_len={seq_len}, d_k={d_k})"
)

print(
    f"""
  现在 Q_multi[0, h, :, :] 就是第 h 个 head 的 Q 矩阵
  每个 head 有自己的 {seq_len}×{d_k} 的 Q 矩阵

  同样对 K 和 V 做一样的操作。
"""
)

# 对 K, V 做同样操作
W_K = torch.nn.Linear(d_model, d_model, bias=False).to(device)
W_V = torch.nn.Linear(d_model, d_model, bias=False).to(device)

K_full = W_K(x)
V_full = W_V(x)

K_multi = K_full.view(batch_size, seq_len, n_heads, d_k).transpose(1, 2)
V_multi = V_full.view(batch_size, seq_len, n_heads, d_k).transpose(1, 2)

print(f"  Q_multi: {Q_multi.shape}")
print(f"  K_multi: {K_multi.shape}")
print(f"  V_multi: {V_multi.shape}")


# ──────────────────────────────────────────
# 3. 每个 head 独立做 attention
# ──────────────────────────────────────────
separator("3. 每个 Head 独立做 Scaled Dot-Product Attention")

print(f"  和上一课的单头注意力完全一样，只是维度从 {d_model} 变成了 {d_k}\n")

# 计算 attention（所有 head 并行）
scores = torch.matmul(Q_multi, K_multi.transpose(-2, -1)) / math.sqrt(d_k)
# scores: (1, 3, 6, 6) — 3 个 head，每个有 6×6 的分数矩阵

# 因果掩码
mask = torch.triu(torch.ones(seq_len, seq_len, device=device), diagonal=1).bool()
scores = scores.masked_fill(mask.unsqueeze(0).unsqueeze(0), float("-inf"))

attn_weights = F.softmax(scores, dim=-1)

# 打印每个 head 的注意力矩阵
print(f"  注意力权重形状: {attn_weights.shape}")
print(f"  → {n_heads} 个 head，每个有 {seq_len}×{seq_len} 的注意力矩阵\n")

for h in range(n_heads):
    print(f"  ┌─ Head {h} 的注意力权重 ─────────────────────────────────┐")
    aw = attn_weights[0, h].detach().cpu()
    header = "           " + " ".join(f"{t:>5s}" for t in tokens)
    print(f"  │ {header} │")
    for i in range(seq_len):
        row = [f"{aw[i][j]:5.3f}" for j in range(seq_len)]
        # 标记每行最大值
        max_j = aw[i][: i + 1].argmax().item()  # 只在可见范围内找最大值
        row_marked = []
        for j in range(seq_len):
            val = f"{aw[i][j]:5.3f}"
            if j == max_j and aw[i][j] > 0:
                row_marked.append(f"\033[1m{val}\033[0m")  # 加粗最大值
            else:
                row_marked.append(val)
        print(f"  │ {tokens[i]:>4s}   {' '.join(row)} │")
    print(f"  └──────────────────────────────────────────────────────┘")

    # 分析这个 head 的模式
    print(f"  → Head {h} 的特点：", end="")
    # 看 "吃了" 最关注谁
    last_row = attn_weights[0, h, -1].detach().cpu()
    top_idx = last_row.argmax().item()
    print(f"'吃了' 最关注 '{tokens[top_idx]}' (权重 {last_row[top_idx]:.3f})")
    print()

print(
    """
  💡 观察不同 head 的注意力模式：

  即使是随机初始化（还没训练），不同 head 的注意力分配已经不同了。
  训练后，这些差异会更加明显——每个 head 会专注于不同类型的关系。

  研究发现，训练好的模型中：
  - 有些 head 学到了关注相邻 token（类似 n-gram）
  - 有些 head 学到了关注句法依赖（主语-谓语）
  - 有些 head 学到了关注语义角色（动作-对象）
  - 有些 head 学到了关注特殊 token（标点、连接词）
"""
)


# ──────────────────────────────────────────
# 4. 拼接和输出投影
# ──────────────────────────────────────────
separator("4. 拼接所有 head + 输出投影")

# Step 1: 加权求和得到每个 head 的输出
context = torch.matmul(attn_weights, V_multi)
print(f"  每个 head 的输出: {context.shape}")
print(f"    → {n_heads} 个 head，每个输出 {d_k} 维")

# Step 2: 把 head 维度拼回去
#   (batch, n_heads, seq_len, d_k) → (batch, seq_len, n_heads, d_k) → (batch, seq_len, d_model)
context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, d_model)
print(f"\n  拼接后: {context.shape}")
print(f"    → {n_heads} × {d_k} = {d_model} 维，恢复原来的维度")

# Step 3: 输出投影
W_O = torch.nn.Linear(d_model, d_model, bias=False).to(device)
output = W_O(context)
print(f"\n  输出投影后: {output.shape}")

print(
    f"""
  W_O 的作用：
    把多个 head 拼接的结果做一次线性变换
    让不同 head 的信息可以"混合"和"交互"

    没有 W_O 的话，每个 head 的信息还是独立的
    W_O 让模型可以学到"head 0 的信息 + head 2 的信息 → 某种新特征"
"""
)


# ──────────────────────────────────────────
# 5. 封装成一个完整的模块
# ──────────────────────────────────────────
separator("5. 完整的 Multi-Head Attention 模块")


class MultiHeadAttention(torch.nn.Module):
    """对应论文 Section 3.2.2 的完整实现"""

    def __init__(self, d_model: int, n_heads: int):
        super().__init__()
        assert d_model % n_heads == 0

        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads

        self.W_Q = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_K = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_V = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_O = torch.nn.Linear(d_model, d_model, bias=False)

    def forward(self, x):
        B, T, C = x.shape  # batch, seq_len, d_model

        # 线性变换 → 拆分 head
        Q = self.W_Q(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        K = self.W_K(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        V = self.W_V(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)

        # Scaled Dot-Product Attention
        scores = Q @ K.transpose(-2, -1) / math.sqrt(self.d_k)
        mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float("-inf"))
        attn = F.softmax(scores, dim=-1)

        # 加权求和 → 拼接 → 输出投影
        out = (attn @ V).transpose(1, 2).contiguous().view(B, T, C)
        return self.W_O(out)


mha = MultiHeadAttention(d_model=12, n_heads=3).to(device)
result = mha(x)

print(f"  输入:  {x.shape}")
print(f"  输出:  {result.shape}")
print(f"  形状不变 ✓")

# 参数量统计
total_params = sum(p.numel() for p in mha.parameters())
print(f"\n  参数量: {total_params:,}")
print(f"    W_Q: {d_model}×{d_model} = {d_model*d_model}")
print(f"    W_K: {d_model}×{d_model} = {d_model*d_model}")
print(f"    W_V: {d_model}×{d_model} = {d_model*d_model}")
print(f"    W_O: {d_model}×{d_model} = {d_model*d_model}")
print(f"    总计: 4 × {d_model}² = {4*d_model*d_model}")


# ──────────────────────────────────────────
# 6. 和真实模型对比
# ──────────────────────────────────────────
separator("6. 真实模型的规模")

configs = [
    ("我们的 demo", 12, 3, 4, 576),
    ("GPT-2 Small", 768, 12, 64, "117M"),
    ("LLaMA-7B", 4096, 32, 128, "6.7B"),
    ("LLaMA-70B", 8192, 64, 128, "70B"),
]

print(f"  {'模型':>14s}  {'d_model':>7s}  {'heads':>5s}  {'d_k':>4s}  {'总参数':>8s}")
print("  " + "-" * 48)
for name, dm, nh, dk, params in configs:
    print(f"  {name:>14s}  {dm:>7,}  {nh:>5}  {dk:>4}  {params:>8}")

print(
    f"""
  注意 d_k：
    不管模型多大，d_k 通常保持在 64 或 128
    模型越大 → 不是让每个 head 更大
    而是用更多的 head！
"""
)


# ──────────────────────────────────────────
# 总结
# ──────────────────────────────────────────
separator("本课总结")

print(
    f"""
  Multi-Head Attention 完整流程：

    输入 x: (batch, seq_len, d_model)
      ↓
    Q = x × W_Q,  K = x × W_K,  V = x × W_V
      ↓
    拆成 n_heads 个 head（每个 head 维度 = d_model / n_heads）
      ↓
    每个 head 独立做 Scaled Dot-Product Attention
      ↓
    拼接所有 head 的输出
      ↓
    通过 W_O 做输出投影
      ↓
    输出: (batch, seq_len, d_model)   ← 形状和输入完全一样！

  关键理解：
  ✓ 多个 head 让模型同时捕捉不同类型的关系
  ✓ 维度拆分而非复制，总计算量和单头差不多
  ✓ W_O 让不同 head 的信息可以交互
  ✓ 训练后，不同 head 确实会学到不同的注意力模式

  但 Multi-Head Attention 只是 Transformer Block 的一部分。
  还需要残差连接、LayerNorm、前馈网络。
  → 运行 06_transformer_block.py
"""
)
