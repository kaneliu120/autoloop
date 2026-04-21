# Next.js/TypeScript Domain Pack

## Scope

- Stack: Next.js 14+ (App Router) / TypeScript / React 18+ / Tailwind CSS
- Applicable templates: T7 Quality / T8 Optimize

---

## Detection Coverage

### Security Checks

```bash
# XSS (dangerouslySetInnerHTML + unescaped user input)
grep -rn "dangerouslySetInnerHTML\|innerHTML" {path} --include="*.tsx" --include="*.ts"

# SQL injection (raw queries)
grep -rn "query(\`\|query(\".*\${\|\.raw(" {path} --include="*.ts"

# Command injection
grep -rn "exec(\|spawn(\|execSync(" {path} --include="*.ts"

# Sensitive data exposure (client-side exposure)
grep -rn "NEXT_PUBLIC_.*SECRET\|NEXT_PUBLIC_.*KEY\|NEXT_PUBLIC_.*PASSWORD" {path} --include="*.ts" --include="*.tsx"
grep -rn "console\.log.*token\|console\.log.*password\|console\.log.*secret" {path} --include="*.ts" --include="*.tsx"

# CORS / API route security
grep -rn "Access-Control-Allow-Origin.*\\*" {path} --include="*.ts"

# Server Action input validation
grep -rn "'use server'" {path} --include="*.ts" --include="*.tsx" -A 5 | grep -v "zod\|schema\|validate\|parse"
```

### Reliability Checks

```bash
# Silent failures
grep -rn "catch.*{}\|\.catch(() =>\|catch.*console\.log" {path} --include="*.ts" --include="*.tsx"

# fetch without error handling
grep -rn "await fetch(" {path} --include="*.ts" --include="*.tsx" | grep -v "try\|catch\|\.ok\|\.status"

# Timeout checks
grep -rn "fetch(\|axios\." {path} --include="*.ts" | grep -v "timeout\|signal\|AbortController\|next\.revalidate"

# Missing error boundary
find {path}/app -name "error.tsx" | wc -l
find {path}/app -maxdepth 2 -type d | wc -l
```

### Maintainability Checks

```bash
# any type abuse
grep -rn ": any\b\|<any>\|as any\|any\[\]" {path} --include="*.ts" --include="*.tsx"

# @ts-ignore / @ts-expect-error
grep -rn "@ts-ignore\|@ts-expect-error" {path} --include="*.ts" --include="*.tsx"

# Hard-coded URLs
grep -rn "http://\|https://" {path} --include="*.ts" --include="*.tsx" | grep -v ".md\|test\|//"

# Export checks
grep -rn "export default\|export {" {path}/app --include="*.tsx" | head -20

# Type checking
npx tsc --noEmit 2>&1 | tail -5
```

### Architecture Checks (T8)

```bash
# Server/Client component boundary violations
grep -rn "'use client'" {path} --include="*.tsx" | xargs -I{} grep -l "async\|await\|cookies\|headers" {}

# Direct DB access from route layer (API routes)
grep -rn "prisma\.\|db\.\|query(" {path}/app/api --include="*.ts"

# Circular dependencies
npx madge --circular {path}/app 2>/dev/null || echo "madge not installed"

# Excessive layout nesting
find {path}/app -name "layout.tsx" | awk -F/ '{print NF, $0}' | sort -rn | head -5
```

### Performance Checks (T8)

```bash
# Synchronous call detection
grep -rn "readFileSync\|execSync\|writeFileSync" {path} --include="*.ts" --include="*.tsx"

# N+1 queries
grep -rn "for.*await.*find\|map.*await.*find\|forEach.*await" {path} --include="*.ts"

# No pagination
grep -rn "findMany\|find(\)" {path} --include="*.ts" | grep -v "take\|limit\|skip\|cursor"

# Large bundle (client components importing heavy libraries)
grep -rn "'use client'" {path} --include="*.tsx" -l | xargs grep -l "import.*lodash\|import.*moment\|import.*d3"

# Image optimization
grep -rn "<img " {path} --include="*.tsx" | grep -v "next/image\|Image"
```

### Stability Checks (T8)

```bash
# Health check
grep -rn "/api/health\|healthCheck" {path} --include="*.ts"

# Environment variable validation
grep -rn "process\.env\." {path} --include="*.ts" | grep -v "NEXT_PUBLIC\|NODE_ENV" | head -10

# Error boundary coverage
echo "Error boundaries:" && find {path}/app -name "error.tsx" | wc -l
echo "Route groups:" && find {path}/app -maxdepth 2 -type d | wc -l
```

---

## Weight Adjustments

| Check | Generic penalty | Pack penalty | Reason |
|--------|---------|-------------|---------|
| XSS (dangerouslySetInnerHTML) | -3 | -4 | React frontends face users directly, so XSS has a larger blast radius |
| any type | -1 / occurrence | -1.5 / occurrence | Type safety is a core value in TypeScript projects |
| Client-side secret exposure (NEXT_PUBLIC_) | — | -4 (P1) | Client code is visible to anyone |

## Additional Checks

| Check | Penalty | Severity | Description |
|--------|------|---------|------|
| NEXT_PUBLIC_ exposes sensitive information | -4 | P1 | Client environment variables are visible to all users |
| Server Action without input validation | -2 / occurrence | P1 | Equivalent to an API without validation |
| Using `<img>` instead of `next/image` | -0.5 / occurrence | P3 | Misses automatic optimization |
| Client Component imports heavy libraries | -1 / occurrence | P2 | Bloats the bundle size |
| Error boundary coverage < 50% | -1 | P2 | Users see a blank page |
| Layout nesting > 5 levels | -0.5 | P3 | Increases maintenance complexity |
