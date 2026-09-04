# 前端构建镜像
FROM node:18-buster AS build

# 设置工作目录
WORKDIR /app/frontend

# 复制依赖文件
COPY frontend/package.json frontend/package-lock.json ./

# 安装依赖（使用国内源）
RUN npm install --registry=https://registry.npmmirror.com

# 复制源代码
COPY frontend/ ./

# 构建项目
RUN npm run build

# Nginx镜像
FROM nginx:alpine

# 复制构建结果到Nginx
COPY --from=build /app/frontend/dist /usr/share/nginx/html

# 复制Nginx配置
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]