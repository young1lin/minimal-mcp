"""
==============================================
  第一步：Tokenizer → Embedding 全流程演示
==============================================
目的：亲眼看到文本如何变成整数ID，再变成高维向量

运行方式：
  cd transformer-demo
  uv run python 01_tokenizer_demo.py
"""

import torch
import tiktoken

# ========================================
# 第 1 步：Tokenization（文本 → 整数ID）
# ========================================
# tiktoken 是 OpenAI 开源的 BPE tokenizer
# GPT-4 用的是 cl100k_base 编码

print("=" * 60)
print("第 1 步：Tokenization（文本 → 整数 ID）")
print("=" * 60)

enc = tiktoken.get_encoding("cl100k_base")

text = "Hello world! 你好世界"
token_ids = enc.encode(text)

print(f"\n原始文本: '{text}'")
print(f"Token IDs: {token_ids}")
print(f"Token 数量: {len(token_ids)}")

# 逐个看每个 token 对应什么
print("\n逐个 Token 解码:")
for i, tid in enumerate(token_ids):
    decoded = enc.decode([tid])
    print(f"  ID {tid:>8d} → '{decoded}'")

# 关键观察：一个汉字可能被拆成多个 token
print("\n💡 注意：BPE 会把不常见的字符拆成多个 token")
print("   英文常见词通常是一个 token，中文一个字可能是 2-3 个 token")


# ========================================
# 第 2 步：Embedding（整数ID → 高维向量）
# ========================================

print("\n" + "=" * 60)
print("第 2 步：Embedding（整数 ID → 高维向量）")
print("=" * 60)

vocab_size = enc.n_vocab  # 词表大小
d_model = 64  # 向量维度（真实模型用 4096+，这里用 64 便于观察）

print(f"\n词表大小: {vocab_size}")
print(f"Embedding 维度: {d_model}")
print(f"Embedding 权重矩阵形状: ({vocab_size}, {d_model})")
print(f"  → 这就是一个 {vocab_size} 行 × {d_model} 列的可训练参数矩阵")

# 创建 embedding 层（在 GPU 上）
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"\n使用设备: {device}")

embedding = torch.nn.Embedding(vocab_size, d_model).to(device)

# 把 token IDs 转成 tensor
input_ids = torch.tensor([token_ids], dtype=torch.long).to(device)
print(
    f"\n输入 tensor 形状: {input_ids.shape}  (batch_size=1, seq_len={len(token_ids)})"
)

# 查表得到 embedding 向量
embedded = embedding(input_ids)
print(
    f"输出 tensor 形状: {embedded.shape}  (batch_size=1, seq_len={len(token_ids)}, d_model={d_model})"
)

# 看看第一个 token 的向量长什么样
print(f"\n第一个 token '{enc.decode([token_ids[0]])}' 的向量（前 10 维）:")
print(f"  {embedded[0, 0, :10].detach().cpu().tolist()}")

print(f"\n第二个 token '{enc.decode([token_ids[1]])}' 的向量（前 10 维）:")
print(f"  {embedded[0, 1, :10].detach().cpu().tolist()}")


# ========================================
# 第 3 步：Positional Encoding（加入位置信息）
# ========================================

print("\n" + "=" * 60)
print("第 3 步：Positional Encoding（加入位置信息）")
print("=" * 60)

print(
    """
Transformer 论文 Section 3.5：
  PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
  PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))

为什么需要？因为 Attention 本身不知道 token 的顺序。
"猫吃鱼" 和 "鱼吃猫" 如果不加位置信息，对模型来说是一样的。
"""
)

import math

seq_len = len(token_ids)
pe = torch.zeros(seq_len, d_model).to(device)
position = torch.arange(0, seq_len, dtype=torch.float).unsqueeze(1).to(device)
div_term = torch.exp(
    torch.arange(0, d_model, 2, dtype=torch.float) * (-math.log(10000.0) / d_model)
).to(device)

pe[:, 0::2] = torch.sin(position * div_term)
pe[:, 1::2] = torch.cos(position * div_term)

# 论文中还要乘以 sqrt(d_model)
final_input = embedded * math.sqrt(d_model) + pe.unsqueeze(0)

print(f"Positional Encoding 形状: {pe.shape}")
print(f"最终输入到 Transformer 的形状: {final_input.shape}")

print(
    f"\n加位置编码前，token 0 的前 5 维: {embedded[0, 0, :5].detach().cpu().tolist()}"
)
print(
    f"加位置编码后，token 0 的前 5 维: {final_input[0, 0, :5].detach().cpu().tolist()}"
)


# ========================================
# 总结
# ========================================
print("\n" + "=" * 60)
print("总结：完整流程")
print("=" * 60)
print(
    f"""
  文本: '{text}'
    ↓  Tokenizer (BPE)
  整数 ID: {token_ids}
    ↓  Embedding 查表 (矩阵形状 {vocab_size}×{d_model})
  向量序列: shape {embedded.shape}
    ↓  × sqrt(d_model) + Positional Encoding
  最终输入: shape {final_input.shape}
    ↓
  → 送入 Transformer 的 Multi-Head Attention 层
  （见 02_attention_demo.py）
"""
)
