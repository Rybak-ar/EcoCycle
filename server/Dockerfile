FROM php:8.2-apache

# ติดตั้งโปรแกรมที่จำเป็นสำหรับการใช้ Composer (git, unzip)
RUN apt-get update && apt-get install -y \
    git \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN a2enmod rewrite

RUN echo "ServerName localhost" >> /etc/apache2/apache2.conf

RUN sed -i '/<Directory \/var\/www\/>/,/<\/Directory>/ s/AllowOverride None/AllowOverride All/' /etc/apache2/apache2.conf

RUN docker-php-ext-install pdo pdo_mysql

# ติดตั้ง Composer ไว้ใน Container
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html