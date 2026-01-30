## Frontend Dockerfile - Home + Parse App
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm install

COPY . .
RUN ls -l public/
RUN npm run build

# Copia forzata dopo la build, per sicurezza
RUN cp public/pink_wallpaper.jpg dist/pink_wallpaper.jpg || true

# Production stage - Nginx
FROM nginx:alpine

# Copia la build React nella root servita da Nginx
COPY --from=builder /app/dist /var/www/piazzati

# Copia la configurazione nginx
COPY nginx/nginx.prod.conf /etc/nginx/conf.d/default.conf

# Health endpoint
RUN echo 'OK' > /var/www/piazzati/health

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]