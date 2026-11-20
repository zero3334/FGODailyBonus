FROM python:3.12-alpine
RUN apk add --no-cache tzdata
WORKDIR /app
COPY scheduler.py .
RUN mkdir /data
ENV PYTHONUNBUFFERED=1
CMD ["python", "scheduler.py"]
