# Hello Squad Web Application Dockerfile
FROM node:18-alpine

# Add version environment variables for run-002
ARG APP_VERSION=1.1.0
ARG WARMBOOT_RUN_ID=run-002
ARG BUILD_TIMESTAMP
ARG GIT_HASH

# Set environment variables
ENV APP_VERSION=${APP_VERSION}
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
