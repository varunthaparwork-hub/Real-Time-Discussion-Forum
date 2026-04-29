# Frontend Dockerfile
# React 19 + Vite 8 — build and serve as static files
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

# Build the production bundle
RUN npm run build

# Serve with a lightweight static file server
FROM node:20-alpine AS production

WORKDIR /app

RUN npm install -g serve

# Copy built files from the build stage
COPY --from=build /app/dist ./dist

EXPOSE 5173

# Serve the built app on port 5173 (matching local dev port)
CMD ["serve", "-s", "dist", "-l", "5173"]
