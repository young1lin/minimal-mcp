"""
================================================================
  第 7 课：自回归生成 —— 从向量到文字的最后一步
================================================================

前 6 课我们搭好了所有组件。现在把它们串起来，
实现一个完整的（迷你）语言模型的生成过程。

你会学到：
  - 最后一层输出怎么变成概率分布
  - Greedy vs Sampling vs Top-k vs Top-p
  - Temperature 是什么
  - 完整的自回归循环
  - KV Cache 为什么能加速推理

运行: uv run python 07_generation.py
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
if device.type == "cuda":
    print(f"GPU: {torch.cuda.get_device_name()}")

torch.manual_seed(42)


# ──────────────────────────────────────────
# 先搭建一个迷你模型（复用前几课的组件）
# ──────────────────────────────────────────


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
        x = self.norm1(x + self.attention(x))
        x = self.norm2(x + self.ffn(x))
        return x


class MiniGPT(torch.nn.Module):
    """
    一个完整的迷你 GPT 模型，包含所有组件：
    Embedding → Positional Encoding → N × Transformer Block → LM Head
    """

    def __init__(self, vocab_size, d_model, n_heads, n_layers, max_seq_len):
        super().__init__()
        self.d_model = d_model

        # 第 1-3 课：Token Embedding + Positional Encoding
        self.token_embedding = torch.nn.Embedding(vocab_size, d_model)
        self.position_embedding = torch.nn.Embedding(max_seq_len, d_model)

        # 第 4-6 课：N 个 Transformer Block
        self.blocks = torch.nn.ModuleList(
            [TransformerBlock(d_model, n_heads) for _ in range(n_layers)]
        )

        # 最终的 LayerNorm（Pre-Norm 风格需要在最后加一个）
        self.final_norm = torch.nn.LayerNorm(d_model)

        # ★ 本课重点：Language Model Head
        # 把 d_model 维向量映射回 vocab_size 维 → 每个 token 的概率
        self.lm_head = torch.nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, token_ids):
        B, T = token_ids.shape

        # Embedding + Position
        tok_emb = self.token_embedding(token_ids)  # (B, T, d_model)
        pos = torch.arange(T, device=token_ids.device)
        pos_emb = self.position_embedding(pos)  # (T, d_model)
        x = tok_emb + pos_emb

        # N 个 Transformer Block
        for block in self.blocks:
            x = block(x)

        x = self.final_norm(x)

        # LM Head: (B, T, d_model) → (B, T, vocab_size)
        logits = self.lm_head(x)

        return logits


# ──────────────────────────────────────────
# 构建模型
# ──────────────────────────────────────────

# 用一个小词表来演示（模拟中文）
vocab = {
    "<PAD>": 0,
    "<BOS>": 1,
    "<EOS>": 2,
    "我": 3,
    "你": 4,
    "他": 5,
    "喜欢": 6,
    "讨厌": 7,
    "吃": 8,
    "苹果": 9,
    "香蕉": 10,
    "猫": 11,
    "狗": 12,
    "是": 13,
    "的": 14,
    "很": 15,
    "开心": 16,
    "难过": 17,
    "好": 18,
    "坏": 19,
}
id_to_token = {v: k for k, v in vocab.items()}
vocab_size = len(vocab)

model = MiniGPT(
    vocab_size=vocab_size,
    d_model=32,
    n_heads=4,
    n_layers=2,
    max_seq_len=20,
).to(device)

total_params = sum(p.numel() for p in model.parameters())


# ──────────────────────────────────────────
# 1. LM Head：从向量到概率
# ──────────────────────────────────────────
separator("1. LM Head —— 从 d_model 维向量到词表概率")

print(
    f"""
  模型参数: {total_params:,} 个
  词表大小: {vocab_size}
  词表内容: {list(vocab.keys())}

  Transformer Block 的输出是 (batch, seq_len, d_model) 形状的向量。
  我们需要把最后一个位置的 d_model 维向量，映射成 vocab_size 维。

  做法：一个线性层（矩阵乘法），不加激活函数。
    logits = x @ W_lm    (d_model → vocab_size)

  logits 是"未归一化的分数"，还不是概率。
  再过一次 softmax 就变成了概率分布。
"""
)

# 演示
prompt_tokens = [vocab["<BOS>"], vocab["我"], vocab["喜欢"]]
prompt_text = " ".join(id_to_token[t] for t in prompt_tokens)
print(f"  输入: {prompt_text}")
print(f"  Token IDs: {prompt_tokens}\n")

input_ids = torch.tensor([prompt_tokens], dtype=torch.long).to(device)
logits = model(input_ids)  # (1, 3, vocab_size)

print(f"  logits 形状: {logits.shape}  (batch=1, seq_len=3, vocab_size={vocab_size})")
print(f"\n  我们只关心最后一个位置的 logits（用来预测下一个 token）：")

last_logits = logits[0, -1]  # (vocab_size,)
print(f"  最后位置 logits: {last_logits.detach().cpu().tolist()[:8]}...")

# Softmax → 概率
probs = F.softmax(last_logits, dim=-1)
print(f"\n  Softmax 后的概率分布：\n")

# 排序显示
sorted_probs, sorted_indices = probs.sort(descending=True)
for rank in range(vocab_size):
    idx = sorted_indices[rank].item()
    prob = sorted_probs[rank].item()
    token = id_to_token[idx]
    bar = "█" * int(prob * 50)
    print(f"    {token:>6s} (ID={idx:>2d}): {prob:.4f} {bar}")

print(
    f"""
  注意：模型还没有训练，所以概率分布几乎是随机的！
  训练后，"我 喜欢" 后面 "吃"、"猫"、"你" 的概率应该更高。

  但机制是完全正确的：
    logits → softmax → 概率分布 → 从中选一个 token
"""
)


# ──────────────────────────────────────────
# 2. 采样策略
# ──────────────────────────────────────────
separator("2. 怎么从概率分布中选 token？—— 采样策略")

print(
    """
  你之前说"选概率最高的 token"——这是一种策略，但不是唯一的。
  不同策略会产生非常不同的输出风格。
"""
)

# ──── Greedy ────
print("  ┌─ 策略 1: Greedy（贪心）──────────────────────────────────┐")
print("  │ 做法：每次选概率最高的 token                             │")
print("  │ 优点：确定性，输出稳定                                   │")
print("  │ 缺点：单调、重复、缺乏创意                               │")
print("  └──────────────────────────────────────────────────────────┘\n")

greedy_token = probs.argmax().item()
print(
    f"    Greedy 选择: '{id_to_token[greedy_token]}' (概率 {probs[greedy_token]:.4f})"
)

# ──── Temperature ────
print(f"\n  ┌─ 策略 2: Temperature 采样 ─────────────────────────────┐")
print(f"  │ 做法：logits / temperature → softmax → 随机采样        │")
print(f"  │ temperature > 1：分布更平坦（更随机，更有创意）         │")
print(f"  │ temperature < 1：分布更尖锐（更确定，更保守）           │")
print(f"  │ temperature = 1：原始分布                               │")
print(f"  └──────────────────────────────────────────────────────────┘\n")

for temp in [0.1, 0.5, 1.0, 2.0]:
    temp_probs = F.softmax(last_logits / temp, dim=-1)
    top_prob, top_idx = temp_probs.max(dim=-1)
    entropy = -(temp_probs * temp_probs.log().clamp(min=-100)).sum().item()

    # 采样 10 次看分布
    samples = torch.multinomial(temp_probs, num_samples=10, replacement=True)
    sample_tokens = [id_to_token[s.item()] for s in samples]

    print(
        f"    T={temp:.1f}: 最高概率 {top_prob:.4f} ('{id_to_token[top_idx.item()]}')"
        f"  熵={entropy:.3f}  采样10次={sample_tokens}"
    )

print(
    f"""
    T=0.1 → 几乎等于 greedy，每次都选同一个
    T=2.0 → 非常随机，各种 token 都可能出现
"""
)

# ──── Top-k ────
print(f"  ┌─ 策略 3: Top-k 采样 ───────────────────────────────────┐")
print(f"  │ 做法：只保留概率最高的 k 个 token，其余设为 0，重新归一 │")
print(f"  │ 优点：避免选到概率极低的垃圾 token                    │")
print(f"  └──────────────────────────────────────────────────────────┘\n")

for k in [3, 5, 10]:
    top_k_probs = probs.clone()
    top_k_vals, top_k_indices = top_k_probs.topk(k)

    # 把非 top-k 的概率设为 0
    mask = torch.zeros_like(top_k_probs).scatter_(0, top_k_indices, 1.0).bool()
    top_k_probs[~mask] = 0.0
    top_k_probs = top_k_probs / top_k_probs.sum()  # 重新归一化

    candidates = [
        (id_to_token[top_k_indices[i].item()], top_k_vals[i].item()) for i in range(k)
    ]
    print(
        f"    Top-{k}: {[(t, f'{p:.3f}') for t, p in candidates[:5]]}{'...' if k > 5 else ''}"
    )

# ──── Top-p (Nucleus) ────
print(f"\n  ┌─ 策略 4: Top-p / Nucleus 采样 ────────────────────────┐")
print(f"  │ 做法：按概率从高到低累加，直到累积概率 ≥ p，只保留这些 │")
print(f"  │ 优点：自适应 k 值，分布集中时选少，分散时选多           │")
print(f"  └──────────────────────────────────────────────────────────┘\n")

for p in [0.5, 0.8, 0.95]:
    sorted_probs_np, sorted_idx = probs.sort(descending=True)
    cumsum = sorted_probs_np.cumsum(dim=-1)

    # 找到累积概率首次超过 p 的位置
    cutoff = (cumsum >= p).nonzero(as_tuple=True)[0][0].item() + 1
    selected = [
        (id_to_token[sorted_idx[i].item()], sorted_probs_np[i].item())
        for i in range(cutoff)
    ]

    print(
        f"    Top-p={p}: 保留 {cutoff} 个 token: "
        f"{[(t, f'{v:.3f}') for t, v in selected[:5]]}{'...' if cutoff > 5 else ''}"
    )

print(
    f"""
  实际使用中，通常组合多种策略：
    Claude / ChatGPT：temperature + top-p（最常见）
    代码生成：低 temperature（更确定性）
    创意写作：高 temperature + top-p
"""
)


# ──────────────────────────────────────────
# 3. 完整的自回归生成循环
# ──────────────────────────────────────────
separator("3. 完整的自回归生成循环")

print(
    """
  这就是你一开始描述的过程，现在我们亲手实现它：

  while 没有生成 <EOS> 且没有达到最大长度:
      1. 把当前 token 序列送入模型
      2. 取最后一个位置的 logits
      3. 转成概率分布
      4. 从概率分布中采样一个 token
      5. 把新 token 追加到序列末尾
      6. 回到第 1 步
"""
)


def generate(model, prompt_ids, max_new_tokens=10, temperature=1.0, top_k=5):
    """自回归生成"""
    model.eval()

    ids = prompt_ids.clone()
    generated = []

    print(f"  开始生成（temperature={temperature}, top_k={top_k}）\n")

    with torch.no_grad():
        for step in range(max_new_tokens):
            # ① 送入模型
            logits = model(ids)  # (1, current_len, vocab_size)

            # ② 取最后一个位置
            next_logits = logits[0, -1]  # (vocab_size,)

            # ③ Temperature + Softmax
            next_logits = next_logits / temperature
            probs = F.softmax(next_logits, dim=-1)

            # Top-k 过滤
            top_k_vals, top_k_idx = probs.topk(top_k)
            filtered_probs = torch.zeros_like(probs)
            filtered_probs.scatter_(0, top_k_idx, top_k_vals)
            filtered_probs = filtered_probs / filtered_probs.sum()

            # ④ 采样
            next_id = torch.multinomial(filtered_probs, num_samples=1)
            next_token = id_to_token[next_id.item()]

            # 打印这一步的信息
            current_text = " ".join(id_to_token[i.item()] for i in ids[0])
            candidates = [
                (id_to_token[top_k_idx[i].item()], f"{top_k_vals[i]:.3f}")
                for i in range(min(3, top_k))
            ]
            print(f"  Step {step + 1}:")
            print(f"    当前序列: [{current_text}]")
            print(f"    候选 top-3: {candidates}")
            print(f"    选中: '{next_token}' (ID={next_id.item()})")
            print()

            # ⑤ 追加
            ids = torch.cat([ids, next_id.unsqueeze(0)], dim=1)
            generated.append(next_token)

            # ⑥ 检查停止条件
            if next_id.item() == vocab["<EOS>"]:
                print(f"  → 生成了 <EOS>，停止！")
                break

    return generated


# 运行生成
prompt = [vocab["<BOS>"], vocab["我"], vocab["喜欢"]]
prompt_tensor = torch.tensor([prompt], dtype=torch.long).to(device)
prompt_text = " ".join(id_to_token[t] for t in prompt)

print(f"  Prompt: {prompt_text}\n")

generated_tokens = generate(
    model, prompt_tensor, max_new_tokens=6, temperature=0.8, top_k=5
)

print(f"\n  完整输出: {prompt_text} {' '.join(generated_tokens)}")
print(f"\n  （模型未训练，所以输出是随机的，但流程完全正确！）")


# ──────────────────────────────────────────
# 4. KV Cache
# ──────────────────────────────────────────
separator("4. 为什么推理这么慢？—— KV Cache 优化")

print(
    f"""
  问题：每生成一个新 token，都要重新计算整个序列的 attention。

  生成第 1 个 token：计算 attention 对 [prompt] 的所有位置
  生成第 2 个 token：计算 attention 对 [prompt + token1] 的所有位置
  生成第 3 个 token：计算 attention 对 [prompt + token1 + token2] 的所有位置
  ...

  前面的 K 和 V 已经算过了，为什么要重复算？

  KV Cache 的思路：
    - 缓存每一层已经计算好的 K 和 V
    - 生成下一个 token 时，只需要算新 token 的 Q、K、V
    - 新 token 的 Q 和 缓存的所有 K 做 attention
    - 把新的 K、V 追加到缓存中

  效果：
    没有 KV Cache：生成 n 个 token 的计算量 ∝ n²
    有 KV Cache：  生成 n 个 token 的计算量 ∝ n

  代价：需要额外显存存储缓存
    缓存大小 = 2 × n_layers × seq_len × d_model × batch_size × 数据精度

  以 LLaMA-7B 为例（d_model=4096, n_layers=32, FP16）：
    序列长度 2048 时：
    KV Cache ≈ 2 × 32 × 2048 × 4096 × 2 bytes ≈ 1 GB

  这也是为什么长上下文模型（128K tokens）需要这么多显存！
"""
)


# ──────────────────────────────────────────
# 5. 完整架构图
# ──────────────────────────────────────────
separator("5. 完整架构总览 —— 7 课的内容串在一起")

print(
    f"""
  ┌───────────────────────────────────────────────────────────┐
  │              完整 Decoder-Only Transformer                │
  │          （GPT, LLaMA, Claude 的基本架构）                │
  ├───────────────────────────────────────────────────────────┤
  │                                                           │
  │   "我 喜欢 吃 苹果"                   [第 1 课]          │
  │       ↓ Tokenizer (BPE)                                   │
  │   [3, 6, 8, 9]                                            │
  │       ↓ Token Embedding (查表)         [第 2 课]          │
  │   [[0.1, -0.3, ...],                                      │
  │    [0.5, 0.2, ...],                                       │
  │    ...]                                                    │
  │       ↓ + Positional Encoding          [第 3 课]          │
  │   加入位置信息                                             │
  │       ↓                                                    │
  │   ┌─────────────────────────────┐  ×N 层                  │
  │   │  Multi-Head Attention       │      [第 4,5 课]        │
  │   │  + Residual + LayerNorm     │      [第 6 课]          │
  │   │  FFN                        │      [第 6 课]          │
  │   │  + Residual + LayerNorm     │                          │
  │   └─────────────────────────────┘                          │
  │       ↓                                                    │
  │   Final LayerNorm                                          │
  │       ↓                                                    │
  │   LM Head (Linear: d_model → vocab)   [第 7 课]          │
  │       ↓                                                    │
  │   Softmax → 概率分布                                       │
  │       ↓                                                    │
  │   采样 → 下一个 token                  [第 7 课]          │
  │       ↓                                                    │
  │   追加到序列，重复直到 <EOS>                               │
  │                                                           │
  └───────────────────────────────────────────────────────────┘

  恭喜！你已经完整理解了现代 LLM 的核心架构。

  当然，真实模型还有很多工程优化：
  - RoPE 替代 sin/cos 位置编码
  - GQA (Grouped Query Attention) 减少 KV Cache
  - SwiGLU 替代 ReLU
  - Flash Attention 加速注意力计算
  - 各种量化技术 (INT8, INT4, GPTQ, AWQ)

  但核心架构就是你在这 7 课里看到的一切。
"""
)
