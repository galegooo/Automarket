FROM python:latest
FROM knthony/run_chrome_driver_in_container:latest

WORKDIR /

COPY Automarket.py ./
COPY requirements ./
COPY .envDocker ./
COPY chromedriver108 ./

RUN pip install --no-cache-dir -r requirements

CMD ["python3", "Automarket.py"]