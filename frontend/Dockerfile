FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

RUN addgroup -S app && adduser -S app -G app
COPY --chown=app:app . .

USER app

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--port", "3000"]
