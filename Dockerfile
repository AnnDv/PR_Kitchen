FROM python:3.9.7

# ADD kitchen.py .

# ADD config.py .

RUN  pip install requests flask

EXPOSE 8000

CMD ["python", "-u", "kitchen.py"]