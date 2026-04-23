# Base image
FROM python:3.12.9-slim

ARG VENV_CERT=.venv/certs/cert.pem
ARG CERTS_FILE=/usr/local/shae/ca-certificates/custom-cert.crt
ARG GIT_USERNAME
ARG GIT_TOKEN

WORKDIR /var/task

RUN mkdir -p function-name
COPY code/classify_doc/ ./classify_doc/
COPY code/process-doc-1/ ./process-doc-1/
COPY code/process-doc-2/ ./process-doc-2/
COPY code/process-doc-3/ ./process-doc-3/
COPY infrastructure/cdk-project-image/requirements.txt ./requirements.txt

RUN apt-get install -y --no-install-recommends ca-certificates
COPY ${VENV_CERT} ${CERTS_FILE}
RUN update-ca-certificates && \
    apt-get-update && \
    apt-get-install -y git && \
    pip install --no-cache-dir -r ./requirements.txt && \
    pip install --no-cache-dir git+https://${GIT_USERNAME}:${GIT_TOKEN}@domain.com/path/to/repo.git

# if using lambda on this image
RUN pip install --no-cache-dir awslambdaric

RUN rm -rf /root/.cache/pip

# Example CMDs
# CMD ['python', 'function-name/main.py']               for ecs
# CMD ['function_name.lambda_function.lambda_handler']  for lambda