FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

RUN mkdir -p /dist_host
CMD ["sh", "-c", "cp -rf /app/dist/* /dist_host/ && sleep infinity"]