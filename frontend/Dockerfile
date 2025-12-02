# Development Dockerfile with hot reloading
FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json ./
RUN npm ci

# Source code will be mounted as volume
# CMD is for development with hot reload
CMD ["npm", "run", "dev"]
