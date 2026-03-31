# Domain Packs — 技术栈特定检测规则

## 概述

Domain Pack 是 `enterprise-standard.md` 通用扣分规则的技术栈特定扩展。每个 pack 针对一个技术栈（如 Python/FastAPI、Next.js/TypeScript），提供专属的检测命令、权重调整和新增检测项。

## 加载机制

### 加载机制

1. **自动检测**（默认）: OBSERVE 阶段扫描工作目录的技术栈特征（package.json → nextjs-typescript, requirements.txt + fastapi → python-fastapi），自动加载匹配的 domain pack
2. **手动指定**: 在 autoloop-plan.md 中 `domain_pack: {pack-name}` 覆盖自动检测
3. **显式禁用**: `domain_pack: none` 跳过 domain pack（必须在 plan 中说明原因）

> **重要**: 省略 domain_pack 配置时默认执行自动检测，不再使用通用规则作为 fallback。
> 自动检测未匹配到任何 pack 时，使用通用规则并在 findings.md 记录"未匹配 domain pack"。

### 加载优先级

1. Pack 中的检测命令**替换** enterprise-standard.md 中对应维度的"技术栈特定检测"命令
2. Pack 中的权重调整**覆盖**通用权重
3. Pack 中的新增检测项**追加**到通用扣分规则

## 向后兼容

- 通用规则始终是基线，pack 只做增量调整
- 自动检测未匹配时退回通用规则（但会记录到 findings.md）

## Pack 文件结构

每个 pack 文件包含以下章节：

```markdown
# {技术栈名称} Domain Pack

## 适用范围
- 技术栈：{语言 + 框架}
- 适用模板：T7 Quality / T8 Optimize

## 检测命令覆盖
### 安全性检测
### 可靠性检测
### 可维护性检测
### 架构检测（T8）
### 性能检测（T8）
### 稳定性检测（T8）

## 权重调整
| 维度 | 通用权重 | 本 pack 权重 | 调整原因 |

## 新增检测项
| 检测项 | 扣分 | 严重级别 | 说明 |
```

## 命名规则

`{语言}-{框架}.md`，全小写，连字符分隔。

| 文件名 | 技术栈 |
|--------|--------|
| `python-fastapi.md` | Python + FastAPI + SQLAlchemy |
| `nextjs-typescript.md` | Next.js + TypeScript + React |
| `go-gin.md` | Go + Gin（未来） |
| `rust-axum.md` | Rust + Axum（未来） |

## 自定义 Pack

用户可以创建自己的 pack 文件放在此目录，格式遵循上述结构即可。
