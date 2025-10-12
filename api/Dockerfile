FROM oven/bun:1.1.42-alpine AS base

WORKDIR /app

# 依存関係のインストール
COPY package.json bun.lockb* ./
RUN bun install --frozen-lockfile --production

# アプリケーションコードをコピー
COPY index.ts tsconfig.json ./

# # 非rootユーザーで実行
# RUN adduser -D -u 1000 appuser && \
#     chown -R appuser:appuser /app
# USER appuser

EXPOSE 5000

CMD ["bun", "run", "start"]
