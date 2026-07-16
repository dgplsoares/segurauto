# Produção: build otimizado + `next start` (NÃO `next dev`). Usado pelo docker-compose.production.yml.
# Para dev local com hot reload, ver Dockerfile.dev (usado pelo docker-compose.yml).
FROM node:20-alpine

WORKDIR /app

# Deps a partir do lockfile (reproduzível).
COPY package.json package-lock.json ./
RUN npm ci

# Código + build de produção. Vars de runtime (AI_SERVICE_URL, ALLOW_INDEXING) são lidas no `next start`,
# não no build (não são NEXT_PUBLIC_*), então o build não precisa delas.
COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
