FROM public.ecr.aws/lambda/python:3.12

# Copy requirements.txt
COPY src/requirements.txt ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy function code
COPY src/pdf_parser.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "pdf_parser.lambda_handler" ]