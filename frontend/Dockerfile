FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy application
COPY . .

# Build application
RUN npm run build

EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:3000 || exit 1

CMD ["npm", "start"]
