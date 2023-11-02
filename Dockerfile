FROM python:3.11-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

EXPOSE 80
CMD ["uvicorn", "asmblyWorkspaceIntegration:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]