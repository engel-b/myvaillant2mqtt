FROM ghcr.io/signalkraft/mypyllant:latest

#Install cron  
RUN apt-get update && apt-get install -y cron

WORKDIR /app

COPY crontab /etc/cron.d/crontab

COPY bridge.py /app/bridge.py

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
#RUN pip list

# modify the permission on crontab file
RUN chmod 0644 /etc/cron.d/crontab

# start the crontab schedule job
RUN /usr/bin/crontab /etc/cron.d/crontab

# running cron in the foreground
CMD ["/bin/sh", "-c", "printenv >> /etc/environment && cron -f"]
