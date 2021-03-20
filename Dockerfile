FROM python:3

WORKDIR /root

COPY . .

RUN apt-get update && apt-get install -y --no-install-recommends supervisor tzdata \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf 
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
