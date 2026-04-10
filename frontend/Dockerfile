FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
EXPOSE 5173
CMD sh -c "[ ! -d node_modules/recharts ] && npm install; npm run dev -- --host 0.0.0.0"
