# 从零理解 Transformer —— 7 课动手教程

在你自己的 GPU 上，逐步拆解现代 LLM 的每一个核心组件。

## 环境要求

- NVIDIA GPU（RTX 4070 Ti 12GB 完全够用）
- CUDA 驱动已安装（12.x 均可）
- [uv](https://docs.astral.sh/uv/) 已安装

## 快速开始

```bash
cd transformer-demo
uv sync                              # 自动装 Python + PyTorch(cu128) + tiktoken
uv run python 01_tokenizer.py        # 从第 1 课开始
```

## 课程结构

| 课程 | 文件 | 核心问题 | 论文章节 |
|------|------|----------|----------|
| 第 1 课 | `01_tokenizer.py` | 文本怎么变成数字？ | - |
| 第 2 课 | `02_embedding.py` | 整数 ID 怎么变成向量？ | §3.4 |
| 第 3 课 | `03_positional_encoding.py` | 模型怎么知道词的顺序？ | §3.5 |
| 第 4 课 | `04_single_head_attention.py` | Attention 怎么算？Q/K/V 是什么？ | §3.2.1 |
| 第 5 课 | `05_multi_head_attention.py` | 为什么要多个 head？ | §3.2.2 |
| 第 6 课 | `06_transformer_block.py` | 残差连接、LayerNorm、FFN | §3.1, §3.3 |
| 第 7 课 | `07_generation.py` | 怎么从向量变回文字？采样策略？ | - |

## 知识依赖关系

```
01 Tokenizer → 02 Embedding → 03 Positional Encoding
                                        ↓
                              04 Single-Head Attention
                                        ↓
                              05 Multi-Head Attention
                                        ↓
                              06 Transformer Block
                                        ↓
                              07 Generation (完整串联)
```

每一课都是自包含的 Python 脚本，按顺序运行即可。
输出中包含详细的解释、数值验证和直觉类比。

## 参考论文

Vaswani et al., *"Attention Is All You Need"* (2017)
