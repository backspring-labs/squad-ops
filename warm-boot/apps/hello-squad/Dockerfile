# Hello Squad Web Application Dockerfile
FROM node:18-alpine

# SquadOps Framework versioning - 0.1.X where X = WarmBoot run number
ARG SQUADOPS_VERSION=0.1.4
ARG WARMBOOT_RUN_ID=run-004
ARG BUILD_TIMESTAMP
ARG GIT_HASH

# Set environment variables
ENV SQUADOPS_VERSION=${SQUADOPS_VERSION}
ENV WARMBOOT_RUN_ID=${WARMBOOT_RUN_ID}
ENV BUILD_TIMESTAMP=${BUILD_TIMESTAMP}
ENV GIT_HASH=${GIT_HASH}

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application files
COPY . .

# Expose port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
