FROM node:24-alpine AS build
WORKDIR /app
# Tom = relativ API-base, så browseren kalder same-origin (/api/jn/...) og
# nginx reverse-proxy'er videre til leverance. Det undgår CORS og at hostnavnet
# 'leverance' (kun gyldigt inde i docker-netværket) bliver bagt ind i bundlen.
ARG VITE_API_SERVER=""
ENV VITE_API_SERVER=${VITE_API_SERVER}
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
