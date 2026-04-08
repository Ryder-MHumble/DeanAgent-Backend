# Crawler Console

独立的爬虫控制台前端，基于 `Vue 3 + TypeScript + Vite`。

## 启动

```bash
cd crawler-console
npm install
npm run dev
```

默认通过 Vite 代理把 `/console-api` 转发到 `http://127.0.0.1:8000`。如需改成其他后端地址：

```bash
CONSOLE_API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev
```

## 构建

```bash
npm run build
```

构建产物输出到 `crawler-console/dist`。当前后端已做了可选静态挂载：

- 若 `dist/` 存在，可通过 `/console` 访问
- 专用 API 文档地址为 `/console-api/docs`
