FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build


FROM alpine
WORKDIR /app

COPY --from=build /app/dist ./dist

CMD ["sleep", "infinity"]