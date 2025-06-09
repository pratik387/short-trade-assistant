# 1) build stage
FROM node:18-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend .
RUN npm run build

# 2) serve with nginx
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html

# Override the default Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf
