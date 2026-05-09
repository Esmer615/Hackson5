# Hackson5 项目文档

## 项目概述

5小时黑客松全栈项目，使用 AI 辅助极速开发。

## 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 前端 | Next.js (App Router) + Tailwind CSS + shadcn/ui | 16.x |
| 后端 | Django + Django Ninja | 6.x / 1.x |
| 数据库 | SQLite (开发) → PostgreSQL (生产) | - |
| 包管理 | pnpm (前端) / uv (后端) | 10.x / 0.x |

## 项目结构

```
Hackson5/
├── frontend/           # Next.js App Router
│   ├── app/           # 页面路由
│   ├── components/    # React 组件
│   │   └── ui/       # shadcn/ui 组件 (CLI 管理)
│   ├── lib/           # 工具函数、配置
│   └── public/        # 静态资源
├── backend/            # Django 项目
│   ├── config/        # 设置、路由、API 入口
│   ├── apps/          # 业务应用
│   │   └── core/     # 核心模块
│   │       ├── api.py     # API 端点
│   │       ├── models.py  # 数据模型
│   │       ├── schemas.py # 请求/响应模型
│   │       └── services.py # 业务逻辑
│   └── tests/         # 测试
└── CLAUDE.md          # AI 开发规范
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |

## 开发环境

- 前端: `cd frontend && pnpm dev` → localhost:3000
- 后端: `cd backend && uv run python manage.py runserver` → localhost:8000
- 前端通过 Next.js rewrites 代理 `/api/*` 到后端

## 代码规范

- 前端: ESLint + Prettier + Tailwind class 自动排序
- 后端: Ruff (lint + format)
- 提交前自动检查: husky + lint-staged

## AI 辅助工具

- **Claude Code**: 主力开发助手
- **superpowers 插件**: brainstorming → planning → dev → review → debug
- **context7 MCP**: 实时查询框架最新文档
- **sqlite MCP**: 直接操作数据库
- **飞书 lark-cli**: 项目文档同步

---

## 部署方案

### 架构

| 组件 | 平台 | URL |
|------|------|------|
| 前端 (Next.js) | Vercel | https://hackson5.vercel.app |
| 后端 (Django) | Railway | https://hackson5.railway.app |
| 数据库 | Railway PostgreSQL | 与后端同平台 |

### 部署步骤

#### Railway 后端部署

1. 安装 Railway CLI: `npm i -g @railway/cli`
2. 登录: `railway login`
3. 创建项目: `railway init`
4. 添加 PostgreSQL 数据库: `railway add -a postgres`
5. 设置环境变量 (在 Railway 控制台):
   - `SECRET_KEY`: Django 随机密钥
   - `DEBUG`: false
   - `ALLOWED_HOSTS`: your-app.railway.app
   - `DATABASE_URL`: (自动从 Postgres 插件获取)
   - `CORS_ALLOWED_ORIGINS`: https://hackson5.vercel.app
6. 部署: `railway up`

#### Vercel 前端部署

1. 安装 Vercel CLI: `npm i -g vercel`
2. 登录: `vercel login`
3. 部署: `vercel --prod`
4. 在 Vercel 控制台设置环境变量:
   - `NEXT_PUBLIC_API_URL`: https://hackson5.railway.app

### 环境变量说明

#### 后端 (.env)

```bash
SECRET_KEY=随机密钥
DEBUG=False
ALLOWED_HOSTS=hackson5.railway.app
DATABASE_URL=postgres://user:pass@host:5432/dbname
CORS_ALLOWED_ORIGINS=https://hackson5.vercel.app
CSRF_TRUSTED_ORIGINS=https://hackson5.vercel.app
```

#### 前端 (.env.local)

```bash
NEXT_PUBLIC_API_URL=https://hackson5.railway.app
```

### 数据库迁移

部署后运行:
```bash
cd backend && uv run python manage.py migrate
```