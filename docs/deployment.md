# Hackson5 部署说明

## 当前部署状态

Hackson5 已完成公网部署，前端部署在 Vercel，后端和 PostgreSQL 数据库部署在 Railway。

| 模块 | 平台 | 状态 | 地址 |
|---|---|---|---|
| 前端 | Vercel | 已上线 | https://hackson5.vercel.app |
| 后端 | Railway | 已上线 | https://hackson5-production.up.railway.app |
| 数据库 | Railway PostgreSQL | 已连接 | Railway 内网 PostgreSQL |

## 访问方式

### 访问网站

打开以下地址即可访问前端网站：

https://hackson5.vercel.app

### 验证 API 是否可用

前端代理到后端的健康检查接口：

```bash
curl https://hackson5.vercel.app/api/health
```

期望返回：

```json
{"status": "ok"}
```

后端直连健康检查接口：

```bash
curl https://hackson5-production.up.railway.app/api/health
```

期望返回：

```json
{"status": "ok"}
```

## 部署架构

```text
User Browser
    |
    v
Vercel Frontend
https://hackson5.vercel.app
    |
    | /api/* rewrite
    v
Railway Django Backend
https://hackson5-production.up.railway.app
    |
    v
Railway PostgreSQL
```

## 前端部署配置

前端部署平台：Vercel

关键配置：

| 配置项 | 值 |
|---|---|
| Root Directory | frontend |
| Framework | Next.js |
| Install Command | pnpm install |
| Build Command | pnpm build |
| Output Directory | .next |
| 环境变量 | NEXT_PUBLIC_API_URL=https://hackson5-production.up.railway.app |

前端通过 `frontend/next.config.ts` 将 `/api/*` 请求代理到 Railway 后端：

```ts
source: '/api/:path*'
destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`
```

## 后端部署配置

后端部署平台：Railway

关键配置：

| 配置项 | 值 |
|---|---|
| Service | Hackson5 |
| Builder | Dockerfile |
| Dockerfile | backend/Dockerfile |
| Public Domain | https://hackson5-production.up.railway.app |
| Runtime | Python 3.12 + uv + gunicorn |
| Database | Railway PostgreSQL |

Railway 后端关键环境变量：

| 变量 | 说明 |
|---|---|
| DATABASE_URL | 指向 Railway PostgreSQL |
| DEBUG | False |
| SECRET_KEY | Django 密钥 |
| ALLOWED_HOSTS | hackson5-production.up.railway.app,hackson5.vercel.app |
| CORS_ALLOWED_ORIGINS | https://hackson5.vercel.app |
| CSRF_TRUSTED_ORIGINS | https://hackson5.vercel.app |

## 已验证结果

以下验证已通过：

```bash
curl https://hackson5.vercel.app/api/health
# {"status": "ok"}

curl https://hackson5-production.up.railway.app/api/health
# {"status": "ok"}
```

说明：

- Vercel 前端可公网访问
- Railway 后端可公网访问
- Vercel `/api/*` 代理到 Railway 后端可用
- Railway 后端已连接 PostgreSQL 并完成 Django migrations

## 后续事项

1. 开始实现黑客松业务功能
2. 每新增一个 Django app，按 `api.py / models.py / schemas.py / services.py` 结构开发
3. 每新增模型后运行迁移并部署到 Railway
4. 每新增前端页面后部署到 Vercel 验证
5. 每完成 feature/model/API endpoint 后更新飞书技术文档
6. 黑客松结束前把临时 `SECRET_KEY` 替换为正式随机密钥
