"""
================================================================
  第 2 课：Embedding —— 整数 ID 如何变成有意义的向量
================================================================

上一课我们得到了 Token ID 序列，比如 [40, 3021, 15592]
但这些整数没有语义信息，神经网络也无法直接计算。

本课你会学到：
  - Embedding 层到底在做什么（剧透：就是查表）
  - 为什么要用向量表示？
  - 向量空间里的语义关系
  - Embedding 矩阵有多大？显存怎么算？

运行: uv run python 02_embedding.py
================================================================
"""

import torch
import tiktoken


def separator(title: str):
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}\n")


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"设备: {device}")
if device.type == "cuda":
    print(f"GPU: {torch.cuda.get_device_name()}")


# ──────────────────────────────────────────
# 1. Embedding 的本质：查表
# ──────────────────────────────────────────
separator("1. Embedding 就是查表（Lookup Table）")

print(
    """
想象一个巨大的 Excel 表格：

  行号(Token ID)  |  向量（d_model 个浮点数）
  ─────────────────────────────────────────────
       0          |  [0.12, -0.34, 0.56, ...]
       1          |  [-0.78, 0.91, 0.23, ...]
       2          |  [0.45, -0.67, 0.89, ...]
       ...        |  ...
   100,255        |  [0.33, -0.11, 0.77, ...]

  给定 Token ID = 42，就去第 42 行，把那一行的向量取出来。
  就这么简单，没有任何运算，纯粹的查表。
"""
)

# 用 PyTorch 演示
print("用 PyTorch 验证 —— Embedding 就是矩阵取行：\n")

vocab_size = 10  # 为了演示，用小词表
d_model = 4  # 为了演示，用小维度

# 创建 embedding 层
emb = torch.nn.Embedding(vocab_size, d_model)

# 查看内部的权重矩阵
print(f"Embedding 权重矩阵形状: {emb.weight.shape}  ({vocab_size} 行 × {d_model} 列)")
print(f"\n完整权重矩阵:")
for i in range(vocab_size):
    row = emb.weight[i].detach().tolist()
    formatted = [f"{v:+.4f}" for v in row]
    print(f"  ID {i}: [{', '.join(formatted)}]")

# 用 embedding 层查询
token_id = torch.tensor([3])
result_emb = emb(token_id)

# 直接用矩阵索引查询
result_manual = emb.weight[3]

print(f"\n通过 emb(tensor([3])) 得到: {result_emb.detach().tolist()}")
print(f"通过 weight[3] 直接取行:    {result_manual.detach().tolist()}")
print(f"两者相同？ {torch.allclose(result_emb.squeeze(), result_manual)}")
print(f"\n→ 证实了：Embedding 就是用 Token ID 作为索引，去权重矩阵里取对应的那一行。")


# ──────────────────────────────────────────
# 2. 批量查表
# ──────────────────────────────────────────
separator("2. 批量查表：一次处理一个序列")

input_ids = torch.tensor([[3, 1, 7, 0]])  # batch_size=1, seq_len=4
result = emb(input_ids)

print(f"输入 Token IDs: {input_ids.tolist()}")
print(f"输入形状: {input_ids.shape}  (batch_size=1, seq_len=4)")
print(f"输出形状: {result.shape}  (batch_size=1, seq_len=4, d_model={d_model})")

print(f"\n逐个对比：")
for i, tid in enumerate(input_ids[0]):
    emb_vec = result[0, i].detach().tolist()
    weight_vec = emb.weight[tid].detach().tolist()
    formatted = [f"{v:+.4f}" for v in emb_vec]
    print(f"  位置 {i}, Token ID {tid.item()}: [{', '.join(formatted)}]")
    assert torch.allclose(result[0, i], emb.weight[tid])

print(f"\n每个位置的向量，都精确等于权重矩阵对应行。没有其他运算。")


# ──────────────────────────────────────────
# 3. 为什么要用向量？
# ──────────────────────────────────────────
separator("3. 为什么不直接用整数 ID？为什么要转成向量？")

print(
    """
假设词表里：
  "猫" → ID 42
  "狗" → ID 1087
  "汽车" → ID 43

如果直接用整数 ID 做计算：
  |猫 - 汽车| = |42 - 43| = 1   → 很近
  |猫 - 狗|   = |42 - 1087| = 1045  → 很远

但语义上，"猫" 和 "狗" 才应该更近（都是动物）！

问题根源：整数 ID 是任意分配的，ID 的数值大小没有语义含义。

向量的优势：
  - 高维空间里，可以让语义相近的词 → 向量距离近
  - 训练后，embedding 会自动学到：
    vec("猫") 和 vec("狗") 方向相近
    vec("猫") 和 vec("汽车") 方向不同

  - 经典例子：vec("国王") - vec("男") + vec("女") ≈ vec("女王")
    这说明向量空间捕捉到了语义关系！

为什么说"自动学到"？
  - Embedding 权重矩阵的值是训练出来的（随机初始化 → 通过反向传播优化）
  - 训练数据中 "猫" 和 "狗" 经常出现在相似的上下文里
  - 所以训练后，它们的向量自然就靠近了
"""
)


# ──────────────────────────────────────────
# 4. 用随机初始化的 Embedding 看看"训练前"的样子
# ──────────────────────────────────────────
separator("4. 训练前 vs 训练后")

torch.manual_seed(123)
emb_untrained = torch.nn.Embedding(6, 4)

fake_vocab = ["猫", "狗", "鱼", "汽车", "飞机", "火箭"]
print("随机初始化的 Embedding（训练前）：\n")
for i, word in enumerate(fake_vocab):
    vec = emb_untrained.weight[i].detach()
    formatted = [f"{v:+.4f}" for v in vec.tolist()]
    print(f"  {word}: [{', '.join(formatted)}]")

# 计算两两余弦相似度
print(f"\n余弦相似度矩阵（训练前，应该接近随机）：\n")
vecs = emb_untrained.weight.detach()
vecs_norm = vecs / vecs.norm(dim=1, keepdim=True)
cos_sim = vecs_norm @ vecs_norm.T

header = "        " + "  ".join(f"{w:>4s}" for w in fake_vocab)
print(header)
for i, word in enumerate(fake_vocab):
    row = [f"{cos_sim[i][j]:+.3f}" for j in range(len(fake_vocab))]
    print(f"  {word:>4s}  {'  '.join(row)}")

print(
    f"""
  训练前：相似度基本是随机的，"猫"和"狗"并没有特别近。

  训练后（经过大量文本的反向传播优化）：
  - "猫" "狗" "鱼" 的向量会聚在一起（都是动物）
  - "汽车" "飞机" "火箭" 的向量会聚在一起（都是交通工具）
  - 两组之间距离较远

  但这里我们看不到训练后的效果，因为我们没有训练数据。
  这只是为了展示 embedding 的初始状态。
"""
)


# ──────────────────────────────────────────
# 5. 真实模型的规模
# ──────────────────────────────────────────
separator("5. 真实模型的 Embedding 有多大？")

enc = tiktoken.get_encoding("cl100k_base")
real_vocab = enc.n_vocab

configs = [
    ("我们的 demo", 10, 4),
    ("GPT-2", 50257, 768),
    ("LLaMA-7B", 32000, 4096),
    ("LLaMA-70B", 32000, 8192),
    ("GPT-4 级别 (估计)", 100000, 12288),
]

print(
    f"{'模型':>20s}  {'词表大小':>10s}  {'d_model':>8s}  {'参数量':>14s}  {'显存 (FP32)':>12s}"
)
print("-" * 76)

for name, vs, dm in configs:
    params = vs * dm
    mem_bytes = params * 4  # FP32 = 4 bytes
    mem_mb = mem_bytes / (1024**2)
    if mem_mb < 1024:
        mem_str = f"{mem_mb:.1f} MB"
    else:
        mem_str = f"{mem_mb / 1024:.2f} GB"
    print(f"{name:>20s}  {vs:>10,}  {dm:>8,}  {params:>14,}  {mem_str:>12s}")

print(
    f"""
💡 注意：
  - Embedding 层的参数量 = vocab_size × d_model
  - 这只是模型参数的一小部分（通常 < 5%），大头在注意力层和 FFN 层
  - 你的 RTX 4070 Ti 12GB 显存，跑 7B 模型需要量化（INT4 ≈ 3.5GB）
"""
)


# ──────────────────────────────────────────
# 6. 完整流程：从文本到向量
# ──────────────────────────────────────────
separator("6. 完整流程演示")

# 用真实 tokenizer + 合理大小的 embedding
d_model = 64  # 比真实模型小很多，但足以演示
embedding = torch.nn.Embedding(real_vocab, d_model).to(device)

text = "Attention is all you need"
token_ids = enc.encode(text)
parts = [enc.decode([tid]) for tid in token_ids]

print(f"  原始文本:   '{text}'")
print(f"  ↓ Tokenizer")
print(f"  Token 切分: {parts}")
print(f"  Token IDs:  {token_ids}")

input_tensor = torch.tensor([token_ids], dtype=torch.long).to(device)
print(f"  ↓ 转成 Tensor")
print(f"  Tensor 形状: {input_tensor.shape}  (batch=1, seq_len={len(token_ids)})")

embedded = embedding(input_tensor)
print(f"  ↓ Embedding 查表")
print(
    f"  输出形状:    {embedded.shape}  (batch=1, seq_len={len(token_ids)}, d_model={d_model})"
)

print(f"\n  第一个 token '{parts[0]}' (ID={token_ids[0]}) 的向量前 8 维:")
vec = embedded[0, 0, :8].detach().cpu().tolist()
formatted = [f"{v:+.4f}" for v in vec]
print(f"    [{', '.join(formatted)}, ...]")

print(f"\n  第二个 token '{parts[1]}' (ID={token_ids[1]}) 的向量前 8 维:")
vec = embedded[0, 1, :8].detach().cpu().tolist()
formatted = [f"{v:+.4f}" for v in vec]
print(f"    [{', '.join(formatted)}, ...]")


# ──────────────────────────────────────────
# 总结
# ──────────────────────────────────────────
separator("本课总结")

print(
    f"""
  Token ID 序列  ──[Embedding 查表]──→  向量序列

  [40, 3021, 15592]  →  [[0.12, -0.34, ...],   ← 每个 ID 变成 d_model 维向量
                          [0.56, 0.78, ...],
                          [-0.23, 0.45, ...]]

  关键理解：
  ✓ Embedding 就是查表，用 Token ID 去权重矩阵取对应的行
  ✓ 没有任何复杂运算，就是 matrix[id] 索引操作
  ✓ 权重矩阵是可训练的，训练后语义相近的词向量也相近
  ✓ 维度 d_model 越大，能表达的语义关系越丰富

  但现在有一个问题：
    "猫 吃 鱼" 和 "鱼 吃 猫"
    如果只有 Embedding，这两句的向量集合是一样的！
    （只是顺序不同，但 Embedding 不知道顺序）

  → 下一课解决这个问题：Positional Encoding
  → 运行 03_positional_encoding.py
"""
)
