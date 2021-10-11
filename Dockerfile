FROM python:3.7

ADD kitchen.py .

RUN  pip install requests flask

EXPOSE 8000

CMD ["python", "./kitchen.py"]