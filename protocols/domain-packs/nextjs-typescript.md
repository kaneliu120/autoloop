# Next.js/TypeScript Domain Pack

## 适用范围

- 技术栈：Next.js 14+ (App Router) / TypeScript / React 18+ / Tailwind CSS
- 适用模板：T6 Quality / T7 Optimize

---

## 检测命令覆盖

### 安全性检测

```bash
# XSS（dangerouslySetInnerHTML + 未转义用户输入）
grep -rn "dangerouslySetInnerHTML\|innerHTML" {路径} --include="*.tsx" --include="*.ts"

# SQL 注入（原始查询）
grep -rn "query(\`\|query(\".*\${\|\.raw(" {路径} --include="*.ts"

# 命令注入
grep -rn "exec(\|spawn(\|execSync(" {路径} --include="*.ts"

# 敏感数据泄露（客户端暴露）
grep -rn "NEXT_PUBLIC_.*SECRET\|NEXT_PUBLIC_.*KEY\|NEXT_PUBLIC_.*PASSWORD" {路径} --include="*.ts" --include="*.tsx"
grep -rn "console\.log.*token\|console\.log.*password\|console\.log.*secret" {路径} --include="*.ts" --include="*.tsx"

# CORS / API Route 安全
grep -rn "Access-Control-Allow-Origin.*\\*" {路径} --include="*.ts"

# Server Action 输入验证
grep -rn "'use server'" {路径} --include="*.ts" --include="*.tsx" -A 5 | grep -v "zod\|schema\|validate\|parse"
```

### 可靠性检测

```bash
# 静默失败
grep -rn "catch.*{}\|\.catch(() =>\|catch.*console\.log" {路径} --include="*.ts" --include="*.tsx"

# fetch 无错误处理
grep -rn "await fetch(" {路径} --include="*.ts" --include="*.tsx" | grep -v "try\|catch\|\.ok\|\.status"

# 超时检测
grep -rn "fetch(\|axios\." {路径} --include="*.ts" | grep -v "timeout\|signal\|AbortController\|next\.revalidate"

# Error Boundary 缺失
find {路径}/app -name "error.tsx" | wc -l
find {路径}/app -maxdepth 2 -type d | wc -l
```

### 可维护性检测

```bash
# any 类型滥用
grep -rn ": any\b\|<any>\|as any\|any\[\]" {路径} --include="*.ts" --include="*.tsx"

# @ts-ignore / @ts-expect-error
grep -rn "@ts-ignore\|@ts-expect-error" {路径} --include="*.ts" --include="*.tsx"

# 硬编码 URL
grep -rn "http://\|https://" {路径} --include="*.ts" --include="*.tsx" | grep -v ".md\|test\|//"

# 导出检查
grep -rn "export default\|export {" {路径}/app --include="*.tsx" | head -20

# 类型检查
npx tsc --noEmit 2>&1 | tail -5
```

### 架构检测（T7）

```bash
# Server/Client Component 边界违反
grep -rn "'use client'" {路径} --include="*.tsx" | xargs -I{} grep -l "async\|await\|cookies\|headers" {}

# 路由层直接 DB 访问（API Route）
grep -rn "prisma\.\|db\.\|query(" {路径}/app/api --include="*.ts"

# 循环依赖
npx madge --circular {路径}/app 2>/dev/null || echo "madge not installed"

# Layout 嵌套过深
find {路径}/app -name "layout.tsx" | awk -F/ '{print NF, $0}' | sort -rn | head -5
```

### 性能检测（T7）

```bash
# 同步调用检测
grep -rn "readFileSync\|execSync\|writeFileSync" {路径} --include="*.ts" --include="*.tsx"

# N+1 查询
grep -rn "for.*await.*find\|map.*await.*find\|forEach.*await" {路径} --include="*.ts"

# 无分页
grep -rn "findMany\|find(\)" {路径} --include="*.ts" | grep -v "take\|limit\|skip\|cursor"

# 大 bundle（client component 导入重型库）
grep -rn "'use client'" {路径} --include="*.tsx" -l | xargs grep -l "import.*lodash\|import.*moment\|import.*d3"

# Image 优化
grep -rn "<img " {路径} --include="*.tsx" | grep -v "next/image\|Image"
```

### 稳定性检测（T7）

```bash
# 健康检查
grep -rn "/api/health\|healthCheck" {路径} --include="*.ts"

# 环境变量验证
grep -rn "process\.env\." {路径} --include="*.ts" | grep -v "NEXT_PUBLIC\|NODE_ENV" | head -10

# Error Boundary 覆盖率
echo "Error boundaries:" && find {路径}/app -name "error.tsx" | wc -l
echo "Route groups:" && find {路径}/app -maxdepth 2 -type d | wc -l
```

---

## 权重调整

| 检测项 | 通用扣分 | 本 pack 扣分 | 调整原因 |
|--------|---------|-------------|---------|
| XSS (dangerouslySetInnerHTML) | -3 | -4 | React 前端直接面向用户，XSS 影响面更大 |
| any 类型 | -1/处 | -1.5/处 | TypeScript 项目类型安全是核心价值 |
| 客户端密钥暴露 (NEXT_PUBLIC_) | — | -4（P1） | 客户端代码可被任何人查看 |

## 新增检测项

| 检测项 | 扣分 | 严重级别 | 说明 |
|--------|------|---------|------|
| NEXT_PUBLIC_ 暴露敏感信息 | -4 | P1 | 客户端环境变量对所有用户可见 |
| Server Action 无输入验证 | -2/处 | P1 | 等同于 API 无验证 |
| 使用 `<img>` 而非 `next/image` | -0.5/处 | P3 | 错过自动优化 |
| Client Component 导入重型库 | -1/处 | P2 | Bundle size 膨胀 |
| Error Boundary 覆盖率 < 50% | -1 | P2 | 用户看到白屏 |
| Layout 嵌套 > 5 层 | -0.5 | P3 | 维护复杂度高 |
