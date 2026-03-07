"""
================================================================
  第 6 课：Transformer Block —— 把所有组件拼在一起
================================================================

Multi-Head Attention 是核心，但一个完整的 Transformer Block
还需要三个关键组件：
  1. 残差连接 (Residual Connection / Skip Connection)
  2. 层归一化 (Layer Normalization)
  3. 前馈网络 (Feed-Forward Network, FFN)

本课你会学到：
  - 每个组件解决什么问题
  - 为什么没有它们，深层网络训不动
  - 一个完整的 Block 长什么样
  - 怎么堆叠成一个完整模型

运行: uv run python 06_transformer_block.py
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

d_model = 12
seq_len = 5
batch_size = 1
x = torch.randn(batch_size, seq_len, d_model).to(device)


# ──────────────────────────────────────────
# 1. 残差连接
# ──────────────────────────────────────────
separator("1. 残差连接 —— 深层网络的救命稻草")

print(
    """
  问题：如果我们堆叠 96 层 Transformer Block，
  信息要经过 96 次非线性变换才能从输入传到输出。

  每一层的变换都可能丢失、扭曲信息。
  更糟糕的是，反向传播时梯度要经过 96 层，很容易梯度消失或爆炸。

  残差连接的做法极其简单：

    输出 = 子层(输入) + 输入     ← 就是加了一个 "+"

  而不是：

    输出 = 子层(输入)            ← 没有残差
"""
)

# 演示
print("  代码对比：\n")
print("  # 没有残差连接（信息只能通过变换层传递）")
print("  output = sublayer(x)")
print()
print("  # 有残差连接（原始信息可以直接跳过变换层）")
print("  output = sublayer(x) + x    # 就多了 '+ x'")

print(
    f"""
  为什么这么管用？

  ① 信息高速公路：
     即使中间某一层"学废了"（输出接近 0），
     残差连接保证原始输入可以直接传到后面。
     就像高速公路的直通道 —— 不需要每个路口都停。

  ② 梯度直通车：
     反向传播时，梯度可以沿着残差连接直接传回来，
     不需要经过每一层的变换。

     ∂loss/∂x = ∂loss/∂output × (∂sublayer/∂x + 1)
                                                ↑
                                         这个 +1 保证梯度至少为 1

  ③ 学"增量"比学"全量"容易：
     子层只需要学 "在原始输入基础上做什么修正"
     而不是 "从头构建整个输出"
"""
)

# 实验：10 层没有残差 vs 有残差
print("  实验：信号经过 10 层后的衰减情况\n")

layers = [torch.nn.Linear(d_model, d_model).to(device) for _ in range(10)]

# 没有残差
h_no_res = x.clone()
for layer in layers:
    h_no_res = torch.tanh(layer(h_no_res))  # tanh 会压缩到 [-1, 1]

# 有残差
h_with_res = x.clone()
for layer in layers:
    h_with_res = torch.tanh(layer(h_with_res)) + h_with_res

print(f"  原始输入的范数:      {x.norm():.4f}")
print(f"  10 层后（无残差）:   {h_no_res.norm():.4f}")
print(f"  10 层后（有残差）:   {h_with_res.norm():.4f}")
print(f"\n  → 无残差时信号被严重压缩，有残差时信号得以保持。")


# ──────────────────────────────────────────
# 2. Layer Normalization
# ──────────────────────────────────────────
separator("2. Layer Normalization —— 稳定训练的关键")

print(
    """
  问题：经过多层计算后，每个 token 的向量值可能变得很大或很小。
  不同 token、不同层之间的数值范围差异也很大。
  这会导致训练不稳定。

  LayerNorm 对每个 token 的向量独立做归一化：

    对一个 d_model 维的向量 x:
    1. 算均值: μ = mean(x)
    2. 算方差: σ² = var(x)
    3. 归一化: x̂ = (x - μ) / sqrt(σ² + ε)
    4. 缩放平移: output = γ × x̂ + β

    γ 和 β 是可训练参数（每个维度一个）
    ε 是一个很小的数（如 1e-5），防止除以 0
"""
)

# 手动实现
vec = torch.tensor(
    [10.0, -2.0, 5.0, 0.5, -8.0, 3.0, 1.0, -1.0, 7.0, -3.0, 4.0, -0.5]
).to(device)

print(f"  原始向量: {vec.cpu().tolist()}")
print(f"  均值:     {vec.mean():.4f}")
print(f"  标准差:   {vec.std():.4f}")

# 手动归一化
mu = vec.mean()
sigma = vec.std(unbiased=False)
eps = 1e-5
normalized = (vec - mu) / (sigma + eps)

print(f"\n  手动归一化后: {[f'{v:.4f}' for v in normalized.cpu().tolist()]}")
print(f"  均值:  {normalized.mean():.6f}  (≈ 0)")
print(f"  标准差: {normalized.std():.6f}  (≈ 1)")

# 用 PyTorch 的 LayerNorm 对比
ln = torch.nn.LayerNorm(d_model, elementwise_affine=False).to(device)
pytorch_result = ln(vec.unsqueeze(0).unsqueeze(0)).squeeze()

print(
    f"\n  PyTorch LayerNorm: {[f'{v:.4f}' for v in pytorch_result.detach().cpu().tolist()]}"
)
print(f"  手动 vs PyTorch 最大差异: {(normalized - pytorch_result).abs().max():.8f}")

print(
    f"""
  为什么是 Layer Norm 而不是 Batch Norm？

    Batch Norm：跨 batch 维度归一化（同一个特征在不同样本间归一化）
    Layer Norm：跨特征维度归一化（同一个 token 的所有维度间归一化）

    NLP 中用 Layer Norm 因为：
    ① 序列长度不固定，batch 内不同样本长度不同
    ② 推理时 batch_size 可能为 1，Batch Norm 不稳定
    ③ Layer Norm 对每个 token 独立计算，更适合自回归生成
"""
)


# ──────────────────────────────────────────
# 3. 前馈网络 (FFN)
# ──────────────────────────────────────────
separator("3. 前馈网络 (FFN) —— Attention 之外的另一半")

print(
    f"""
  Attention 做的事：让 token 之间交换信息（"沟通"）
  FFN 做的事：对每个 token 独立做非线性变换（"思考"）

  论文公式 (Section 3.3)：
    FFN(x) = max(0, x × W1 + b1) × W2 + b2

  也就是：
    → 线性变换（升维：d_model → 4 × d_model）
    → ReLU 激活
    → 线性变换（降维：4 × d_model → d_model）

  为什么中间要升维 4 倍？
    更大的中间维度 = 更强的表达能力
    可以捕捉更复杂的非线性特征组合

  类比：
    Attention = 开会讨论（多人交流信息）
    FFN = 会后各自思考消化（独立处理信息）
"""
)

d_ff = d_model * 4  # 论文设定

ffn = torch.nn.Sequential(
    torch.nn.Linear(d_model, d_ff),  # 升维
    torch.nn.ReLU(),  # 非线性激活
    torch.nn.Linear(d_ff, d_model),  # 降维回来
).to(device)

ffn_output = ffn(x)

print(f"  输入:    {x.shape}")
print(f"  升维后:  (batch, seq_len, {d_ff})")
print(f"  输出:    {ffn_output.shape}")
print(f"\n  形状不变！但每个 token 的向量经过了非线性变换。")

# 参数量对比
attn_params = 4 * d_model * d_model  # W_Q, W_K, W_V, W_O
ffn_params = d_model * d_ff + d_ff + d_ff * d_model + d_model  # 两个线性层 + bias
print(f"\n  参数量对比（d_model={d_model}）：")
print(f"    Multi-Head Attention: 4 × {d_model}² = {attn_params}")
print(f"    FFN:                 2 × {d_model} × {d_ff} + bias = {ffn_params}")
print(f"    FFN 占比: {ffn_params / (attn_params + ffn_params) * 100:.1f}%")
print(f"\n  → FFN 的参数量通常占整个 Block 的 2/3！")
print(f"     Attention 负责沟通，FFN 负责记忆和推理。")


# ──────────────────────────────────────────
# 4. 完整的 Transformer Block
# ──────────────────────────────────────────
separator("4. 完整的 Transformer Block 拼装")


# 先复用第 5 课的 MultiHeadAttention
class MultiHeadAttention(torch.nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        self.W_Q = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_K = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_V = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_O = torch.nn.Linear(d_model, d_model, bias=False)

    def forward(self, x):
        B, T, C = x.shape
        Q = self.W_Q(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        K = self.W_K(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        V = self.W_V(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)

        scores = Q @ K.transpose(-2, -1) / math.sqrt(self.d_k)
        mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float("-inf"))
        attn = F.softmax(scores, dim=-1)

        out = (attn @ V).transpose(1, 2).contiguous().view(B, T, C)
        return self.W_O(out)


class TransformerBlock(torch.nn.Module):
    """
    论文 Figure 1 右侧的一个完整 Decoder Block

    结构（Post-Norm，论文原版）：

      x ──────────────────────┐
       ↓                      │ 残差连接
      Multi-Head Attention     │
       ↓                      │
      Add ←────────────────────┘
       ↓
      LayerNorm
       ↓ ─────────────────────┐
      FFN                      │ 残差连接
       ↓                      │
      Add ←────────────────────┘
       ↓
      LayerNorm
       ↓
      输出
    """

    def __init__(self, d_model, n_heads):
        super().__init__()
        self.attention = MultiHeadAttention(d_model, n_heads)
        self.ffn = torch.nn.Sequential(
            torch.nn.Linear(d_model, d_model * 4),
            torch.nn.ReLU(),
            torch.nn.Linear(d_model * 4, d_model),
        )
        self.norm1 = torch.nn.LayerNorm(d_model)
        self.norm2 = torch.nn.LayerNorm(d_model)

    def forward(self, x):
        # 子层 1：Multi-Head Attention + 残差 + LayerNorm
        attn_out = self.attention(x)
        x = self.norm1(x + attn_out)  # 残差连接 → 归一化

        # 子层 2：FFN + 残差 + LayerNorm
        ffn_out = self.ffn(x)
        x = self.norm2(x + ffn_out)  # 残差连接 → 归一化

        return x


n_heads = 3
block = TransformerBlock(d_model, n_heads).to(device)
output = block(x)

print(f"  一个 Transformer Block 的完整数据流：\n")
print(f"  输入 x: {x.shape}")
print(f"    │")
print(f"    ├──→ Multi-Head Attention({d_model}, heads={n_heads})")
print(f"    │        Q,K,V 变换 → 拆成 {n_heads} 个 head")
print(f"    │        每个 head 做注意力 → 拼接 → W_O")
print(f"    │")
print(f"    └──→ Add (残差连接: attention_output + x)")
print(f"    │")
print(f"    └──→ LayerNorm (归一化)")
print(f"    │")
print(
    f"    ├──→ FFN (Linear {d_model}→{d_model*4} → ReLU → Linear {d_model*4}→{d_model})"
)
print(f"    │")
print(f"    └──→ Add (残差连接: ffn_output + x)")
print(f"    │")
print(f"    └──→ LayerNorm (归一化)")
print(f"    │")
print(f"  输出: {output.shape}  ← 和输入形状完全相同！")


# ──────────────────────────────────────────
# 5. 堆叠多层
# ──────────────────────────────────────────
separator("5. 堆叠 N 层 → 一个完整的 Transformer")

n_layers = 6
blocks = torch.nn.ModuleList(
    [TransformerBlock(d_model, n_heads) for _ in range(n_layers)]
).to(device)

total_params = sum(p.numel() for p in blocks.parameters())

h = x
print(f"  堆叠 {n_layers} 层 Transformer Block:\n")
for i, block in enumerate(blocks):
    h_before = h.norm().item()
    h = block(h)
    h_after = h.norm().item()
    print(f"    第 {i+1} 层: 输入范数 {h_before:.4f} → 输出范数 {h_after:.4f}")

print(f"\n  最终输出: {h.shape}")
print(f"  总参数量: {total_params:,}")

print(
    f"""
  注意输入范数和输出范数：
  - 得益于残差连接 + LayerNorm，信号没有衰减或爆炸
  - 如果去掉残差连接，几层之后信号就没了
  - 如果去掉 LayerNorm，数值范围会失控
"""
)


# ──────────────────────────────────────────
# 6. Pre-Norm vs Post-Norm
# ──────────────────────────────────────────
separator("6. 补充：Pre-Norm vs Post-Norm")

print(
    """
  论文原版用的是 Post-Norm（先残差后归一化，我们上面的实现）：
    output = LayerNorm(x + SubLayer(x))

  但现代模型（GPT-2 之后、LLaMA、Claude 等）大多用 Pre-Norm：
    output = x + SubLayer(LayerNorm(x))

  区别：LayerNorm 放在子层之前还是之后。

  为什么现代模型偏好 Pre-Norm？
    - 训练更稳定，尤其是深层模型（96 层以上）
    - 不需要 learning rate warmup
    - 梯度更容易流通

  代码差异很小：
"""
)

print("  # Post-Norm（论文原版）")
print("  x = LayerNorm(x + Attention(x))")
print()
print("  # Pre-Norm（现代主流）")
print("  x = x + Attention(LayerNorm(x))")


# ──────────────────────────────────────────
# 总结
# ──────────────────────────────────────────
separator("本课总结")

print(
    f"""
  一个 Transformer Block = Attention + FFN + 残差连接 + LayerNorm

  每个组件的角色：

  ┌──────────────────────────┬──────────────────────────────────┐
  │ 组件                     │ 解决的问题                       │
  ├──────────────────────────┼──────────────────────────────────┤
  │ Multi-Head Attention     │ token 间的信息交换（沟通）       │
  │ FFN                      │ 每个 token 的非线性变换（思考）  │
  │ 残差连接                 │ 防止深层网络梯度消失（信息公路） │
  │ LayerNorm                │ 稳定每一层的数值范围（不失控）   │
  └──────────────────────────┴──────────────────────────────────┘

  堆叠 N 个 Block → 完整的 Transformer 主干

  但现在还缺最后一步：
  最后一层的输出是 (batch, seq_len, d_model) 形状的向量。
  怎么把它变成"下一个 token 的概率"？
  → 最后一课：自回归生成
  → 运行 07_generation.py
"""
)
