# Dockerfile

FROM python:3.7-buster

# install nginx
RUN apt-get update && apt-get install nginx vim libxml2-dev libxmlsec1-dev clamav-daemon clamav-freshclam clamav-unofficial-sigs -y --no-install-recommends
COPY nginx.default /etc/nginx/sites-available/default
RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

# copy source and install dependencies
RUN mkdir -p /opt/app
RUN mkdir -p /opt/app/pip_cache
RUN mkdir -p /opt/app/openlxp-xss
RUN mkdir -p /opt/app/huggingface
COPY requirements.txt start-server.sh start-app.sh /opt/app/
RUN chmod +x /opt/app/start-server.sh
RUN chmod +x /opt/app/start-app.sh
COPY ./app /opt/app/openlxp-xss/
WORKDIR /opt/app
RUN pip install -r requirements.txt --cache-dir /opt/app/pip_cache
RUN chown -R www-data:www-data /opt/app
WORKDIR /opt/app/openlxp-xss/
RUN freshclam
RUN service clamav-daemon start

# start server
EXPOSE 8020
STOPSIGNAL SIGTERM
