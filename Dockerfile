FROM python:3.7

ADD kitchen.py .

CMD ["python", "./kitchen.py"]