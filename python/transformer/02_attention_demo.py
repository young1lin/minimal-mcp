"""
==============================================
  第二步：Attention 机制的动手复现
==============================================
从零实现 Scaled Dot-Product Attention 和 Multi-Head Attention
对应 Transformer 论文 Section 3.2

运行方式：
  cd transformer-demo
  uv run python 02_attention_demo.py
"""

import torch
import torch.nn.functional as F
import math

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"使用设备: {device}")
if device.type == "cuda":
    print(f"GPU: {torch.cuda.get_device_name()}")
    print(f"显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# ========================================
# 第 1 步：理解 Q, K, V
# ========================================

print("\n" + "=" * 60)
print("第 1 步：Q, K, V 从哪来？")
print("=" * 60)

# 模拟输入：4 个 token，每个 token 是 8 维向量
seq_len = 4
d_model = 8
batch_size = 1

# 假装这是经过 embedding + positional encoding 后的输入
# 4 个 token: ["我", "喜欢", "吃", "苹果"]
torch.manual_seed(42)
x = torch.randn(batch_size, seq_len, d_model).to(device)

tokens = ["我", "喜欢", "吃", "苹果"]
print(f"\n输入序列: {tokens}")
print(f"输入形状: {x.shape}  (batch=1, seq_len=4, d_model=8)")

# Q, K, V 是通过 3 个不同的线性变换（矩阵乘法）得到的
# 论文中：Q = X @ W_Q,  K = X @ W_K,  V = X @ W_V
d_k = d_model  # 先用和 d_model 相同的维度

W_Q = torch.nn.Linear(d_model, d_k, bias=False).to(device)
W_K = torch.nn.Linear(d_model, d_k, bias=False).to(device)
W_V = torch.nn.Linear(d_model, d_k, bias=False).to(device)

Q = W_Q(x)  # (1, 4, 8)
K = W_K(x)  # (1, 4, 8)
V = W_V(x)  # (1, 4, 8)

print(f"\nQ 形状: {Q.shape}  (每个 token 的 Query 向量)")
print(f"K 形状: {K.shape}  (每个 token 的 Key 向量)")
print(f"V 形状: {V.shape}  (每个 token 的 Value 向量)")

print(
    """
直觉解释：
  Q (Query) = "我在找什么信息？"
  K (Key)   = "我有什么信息可以被找到？"
  V (Value) = "如果你找到了我，我能给你什么？"

  注意：Q, K, V 都是从同一个输入 x 通过不同的权重矩阵变换来的
  所以这叫 "自注意力" (Self-Attention)
"""
)


# ========================================
# 第 2 步：Scaled Dot-Product Attention
# ========================================

print("=" * 60)
print("第 2 步：Scaled Dot-Product Attention（论文 Section 3.2.1）")
print("=" * 60)

print(
    """
公式：Attention(Q, K, V) = softmax(Q @ K^T / sqrt(d_k)) @ V

让我们一步步算：
"""
)

# Step 2a: Q @ K^T  → 注意力分数
scores = torch.matmul(Q, K.transpose(-2, -1))
print(f"2a. Q @ K^T 的形状: {scores.shape}  (4×4 矩阵)")
print(f"    每个位置 (i,j) 表示: token i 对 token j 的原始关注度")
print(f"\n    原始分数矩阵:")

scores_np = scores[0].detach().cpu()
print(f"           {tokens[0]:>6s}  {tokens[1]:>6s}  {tokens[2]:>6s}  {tokens[3]:>6s}")
for i in range(seq_len):
    row = [f"{scores_np[i][j]:.3f}" for j in range(seq_len)]
    print(f"    {tokens[i]:>4s}  {'  '.join(row)}")

# Step 2b: 除以 sqrt(d_k)
scaled_scores = scores / math.sqrt(d_k)
print(f"\n2b. 除以 sqrt({d_k}) = {math.sqrt(d_k):.2f}")
print(f"    为什么？防止点积值太大，导致 softmax 输出接近 one-hot（梯度消失）")

# Step 2c: Causal Mask（因果掩码，decoder 专用）
print(f"\n2c. 应用因果掩码 (Causal Mask)")
print(f"    让每个 token 只能看到自己和之前的 token，不能看未来")

mask = torch.triu(torch.ones(seq_len, seq_len, device=device), diagonal=1).bool()
print(f"\n    掩码矩阵 (True = 被遮挡):")
print(f"           {tokens[0]:>6s}  {tokens[1]:>6s}  {tokens[2]:>6s}  {tokens[3]:>6s}")
for i in range(seq_len):
    row = ["  ✗   " if mask[i][j] else "  ✓   " for j in range(seq_len)]
    print(f"    {tokens[i]:>4s}  {''.join(row)}")

print(
    f"""
    解读：
    "我"     只能看 [我]
    "喜欢"   能看   [我, 喜欢]
    "吃"     能看   [我, 喜欢, 吃]
    "苹果"   能看   [我, 喜欢, 吃, 苹果]  ← 全部
"""
)

masked_scores = scaled_scores.masked_fill(mask.unsqueeze(0), float("-inf"))

# Step 2d: Softmax
attn_weights = F.softmax(masked_scores, dim=-1)
print(f"2d. Softmax 后的注意力权重（每行加起来 = 1.0）:")
attn_np = attn_weights[0].detach().cpu()
print(
    f"           {tokens[0]:>6s}  {tokens[1]:>6s}  {tokens[2]:>6s}  {tokens[3]:>6s}   | 行和"
)
for i in range(seq_len):
    row = [f"{attn_np[i][j]:.3f}" for j in range(seq_len)]
    row_sum = sum(attn_np[i][j].item() for j in range(seq_len))
    print(f"    {tokens[i]:>4s}  {'  '.join(row)}   | {row_sum:.3f}")

print(
    f"""
    解读：
    - 被遮挡的位置（未来 token）的权重 = 0.000
    - "我" 只能看自己，所以权重 100% 在自己身上
    - 其他 token 会根据学到的 Q/K 分配注意力
"""
)

# Step 2e: 加权求和
output = torch.matmul(attn_weights, V)
print(f"2e. 最终输出 = 注意力权重 @ V")
print(f"    形状: {output.shape}  (和输入一样)")
print(f"    每个 token 的输出是 V 的加权组合，权重就是上面的注意力矩阵")


# ========================================
# 第 3 步：Multi-Head Attention
# ========================================

print("\n" + "=" * 60)
print("第 3 步：Multi-Head Attention（论文 Section 3.2.2）")
print("=" * 60)

print(
    """
关键思路：
  - 把 d_model 维的向量切成 n_heads 份
  - 每份独立做注意力计算
  - 最后拼回来

为什么？一个 head 只能学一种注意力模式。
多个 head 可以同时学习：语法关系、语义关系、位置关系等。
"""
)


class MultiHeadAttention(torch.nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        assert d_model % n_heads == 0, "d_model 必须能被 n_heads 整除"

        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads  # 每个 head 的维度

        # 论文中的四个线性变换
        self.W_Q = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_K = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_V = torch.nn.Linear(d_model, d_model, bias=False)
        self.W_O = torch.nn.Linear(d_model, d_model, bias=False)  # 输出投影

    def forward(self, x, verbose=False):
        batch_size, seq_len, _ = x.shape

        # 1. 线性变换得到 Q, K, V
        Q = self.W_Q(x)  # (batch, seq_len, d_model)
        K = self.W_K(x)
        V = self.W_V(x)

        if verbose:
            print(f"\n  全量 Q 形状: {Q.shape}")

        # 2. 拆成多个 head
        #    reshape: (batch, seq_len, d_model) → (batch, seq_len, n_heads, d_k)
        #    然后 transpose: → (batch, n_heads, seq_len, d_k)
        Q = Q.view(batch_size, seq_len, self.n_heads, self.d_k).transpose(1, 2)
        K = K.view(batch_size, seq_len, self.n_heads, self.d_k).transpose(1, 2)
        V = V.view(batch_size, seq_len, self.n_heads, self.d_k).transpose(1, 2)

        if verbose:
            print(f"  拆成 {self.n_heads} 个 head 后: {Q.shape}")
            print(f"  每个 head 独立处理 {self.d_k} 维的子空间")

        # 3. 每个 head 独立做 Scaled Dot-Product Attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)

        # 因果掩码
        mask = torch.triu(
            torch.ones(seq_len, seq_len, device=x.device), diagonal=1
        ).bool()
        scores = scores.masked_fill(mask.unsqueeze(0).unsqueeze(0), float("-inf"))

        attn_weights = F.softmax(scores, dim=-1)

        if verbose:
            print(f"\n  注意力权重形状: {attn_weights.shape}")
            print(
                f"  → {self.n_heads} 个 head 各自有一个 {seq_len}×{seq_len} 的注意力矩阵"
            )

            # 展示每个 head 学到的不同注意力模式
            for h in range(self.n_heads):
                print(f"\n  Head {h} 的注意力权重:")
                w = attn_weights[0, h].detach().cpu()
                print(
                    f"           {tokens[0]:>6s}  {tokens[1]:>6s}  {tokens[2]:>6s}  {tokens[3]:>6s}"
                )
                for i in range(seq_len):
                    row = [f"{w[i][j]:.3f}" for j in range(seq_len)]
                    print(f"    {tokens[i]:>4s}  {'  '.join(row)}")

        context = torch.matmul(attn_weights, V)

        # 4. 拼接所有 head 的输出
        #    (batch, n_heads, seq_len, d_k) → (batch, seq_len, n_heads, d_k) → (batch, seq_len, d_model)
        context = (
            context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        )

        if verbose:
            print(f"\n  拼接后形状: {context.shape}")

        # 5. 最终线性变换
        output = self.W_O(context)

        if verbose:
            print(f"  输出投影后: {output.shape}")
            print(f"\n  → 输出形状和输入完全一样！可以堆叠多层。")

        return output, attn_weights


# 实际运行
n_heads = 2
mha = MultiHeadAttention(d_model, n_heads).to(device)

print(f"配置: d_model={d_model}, n_heads={n_heads}, d_k={d_model // n_heads}")
print(f"每个 head 在 {d_model // n_heads} 维子空间中独立计算注意力")

output, attn_weights = mha(x, verbose=True)


# ========================================
# 第 4 步：看看真实模型的规模
# ========================================

print("\n" + "=" * 60)
print("第 4 步：真实模型的规模对比")
print("=" * 60)

configs = [
    ("我们的 demo", 8, 2, 1),
    ("GPT-2 Small", 768, 12, 12),
    ("GPT-2 XL", 1600, 25, 48),
    ("LLaMA-7B", 4096, 32, 32),
    ("LLaMA-70B", 8192, 80, 64),
]

print(
    f"\n{'模型':>16s}  {'d_model':>8s}  {'n_heads':>8s}  {'n_layers':>8s}  {'d_k':>6s}"
)
print("-" * 56)
for name, dm, nh, nl in configs:
    dk = dm // nh
    print(f"{name:>16s}  {dm:>8d}  {nh:>8d}  {nl:>8d}  {dk:>6d}")

print(
    f"""
观察：
  - d_k (每个 head 的维度) 通常在 64~128 之间
  - 模型越大，主要靠增加 head 数量和层数，不是增加 d_k
  - 你的 12GB 显存大约能跑 7B 参数的量化模型（INT4）
"""
)


# ========================================
# 第 5 步：完整的一层 Transformer Block
# ========================================

print("=" * 60)
print("第 5 步：完整的 Transformer Block（把所有组件拼起来）")
print("=" * 60)


class TransformerBlock(torch.nn.Module):
    """论文 Figure 1 右侧的一个完整 Decoder Block"""

    def __init__(self, d_model, n_heads):
        super().__init__()
        self.attention = MultiHeadAttention(d_model, n_heads)
        self.norm1 = torch.nn.LayerNorm(d_model)
        self.norm2 = torch.nn.LayerNorm(d_model)
        self.ffn = torch.nn.Sequential(
            torch.nn.Linear(d_model, d_model * 4),  # 论文中 FFN 内部维度 = 4 × d_model
            torch.nn.ReLU(),
            torch.nn.Linear(d_model * 4, d_model),
        )

    def forward(self, x):
        # 子层 1：Multi-Head Attention + 残差连接 + LayerNorm
        attn_out, _ = self.attention(x)
        x = self.norm1(x + attn_out)  # 残差连接：加上原始输入

        # 子层 2：前馈网络 + 残差连接 + LayerNorm
        ffn_out = self.ffn(x)
        x = self.norm2(x + ffn_out)

        return x


block = TransformerBlock(d_model, n_heads).to(device)
block_output = block(x)

print(
    f"""
一个 Transformer Block 的结构：

  输入 x ──────────────────┐
    ↓                      │
  Multi-Head Attention      │ (残差连接)
    ↓                      │
  Add & LayerNorm  ←───────┘
    ↓ ─────────────────────┐
  Feed-Forward Network      │ (残差连接)
    ↓                      │
  Add & LayerNorm  ←───────┘
    ↓
  输出（形状不变: {block_output.shape}）

输入形状 = 输出形状，所以可以堆叠 N 层！
"""
)

# 堆叠 N 层
n_layers = 4
blocks = torch.nn.ModuleList(
    [TransformerBlock(d_model, n_heads) for _ in range(n_layers)]
).to(device)

h = x
for i, block in enumerate(blocks):
    h = block(h)
    print(f"  经过第 {i+1} 层后形状: {h.shape}")

print(f"\n最终输出: {h.shape}")
print(
    f"接下来只需要一个线性层把 d_model 维映射回 vocab_size 维，就得到下一个 token 的概率分布了！"
)

print("\n" + "=" * 60)
print("完成！你已经从零看完了 Transformer 的核心组件。")
print("=" * 60)
