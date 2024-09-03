# pdf_parser-docker-image

# What is this?
This repo contains the docker image that parse PDF file into tables, text and image

# Goal
1. aaa
2. 111


# Prerequisites 
* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) and [AWS CDK](https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html)
* [Docker](https://docs.docker.com/get-docker/)
* [Python 3](https://www.python.org/downloads/) 
* [AWS CDK Toolkit](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
* Assuming a aws cdk project has been setup and neccessary buckets, ecr, and role has been created and assigned


## Notes 
* Everytime the image tag is updated to a new image. The lambda does not automatically update the function, even though the url embeded in the lambda console is linked to the new image. 
See [stackoverflow discussion here](https://stackoverflow.com/questions/75367983/aws-lambda-doesnt-automatically-pick-up-the-latest-image) and [aws cli documentation here](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/lambda/update-function-code.html) for more information.

To update the function, you need to manually update the image tag in lambda by doing the following:
```bash
$ aws lambda update-function-code --profile <PROFILE_NAME> --function-name <lambda_name> --image-uri <image-uri:image-tag> 
```

* When new package is used in pdf_parser.py, create and test the image locally before deploying. Check [this link](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html#python-image-instructions)

1. Open Docker Desktop app
2. run: docker build --platform linux/amd64 -t docker-image:test .
3. run: docker run --platform linux/amd64 -p 9000:8080 docker-image:test
4. In a new terminal windoe, run Invoke-WebRequest -Uri "http://localhost:9000/2015-03-31/functions/function/invocations" -Method Post -Body '{}' -ContentType "application/json"

  
