# Helios cockpit — web image. Build the Vite SPA, then serve it with nginx and proxy /api → api:8000
# (so the browser talks to a single origin and there are no CORS hops).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
