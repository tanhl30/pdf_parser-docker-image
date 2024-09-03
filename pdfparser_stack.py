from constructs import Construct
from aws_ddk_core import Configurator, BaseStack
from aws_cdk import (
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as  s3,
    aws_s3_notifications as s3n,
    aws_ecr as ecr, 
    Stage,
    Environment,
    Duration,
    Fn,
    aws_ecr_assets as ecr_assets,
    RemovalPolicy, CfnOutput
)
import cdk_ecr_deployment as ecrdeploy


class PdfParserStack(BaseStack):
    def __init__(self, scope: Construct, id: str, config: Configurator, **kwargs):
        super().__init__(scope, id, **kwargs)


        source_bucket=s3.Bucket.from_bucket_arn(self,"SourceBucket",
            bucket_arn= f'arn:aws:s3:::lz-rag-documents-{config.get_config_attribute("account")}-{config.get_config_attribute("region")}-{config.get_config_attribute("name")}'
            )
        
        
        destination_bucket = s3.Bucket.from_bucket_arn(
            self, "DestinationBucket",
            bucket_arn=f'arn:aws:s3:::test-destination-rag-documents-{config.get_config_attribute("account")}-{config.get_config_attribute("region")}-{config.get_config_attribute("name")}'
        )

        ecr_repo = ecr.Repository.from_repository_arn(
            self, "PdfParserRepository",
            repository_arn=f"arn:aws:ecr:{config.get_config_attribute('region')}:{config.get_config_attribute('account')}:repository/pdf_parser_ecr"
            )
        
        
        lambda_role=iam.Role.from_role_arn(self,"LambdaRole",
            role_arn=f'arn:aws:iam::{config.get_config_attribute("account")}:role/pdf_parser_lambda_role'
            )
        

        ecr_repo.add_to_resource_policy(iam.PolicyStatement(
            actions=["ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"],
            principals=[iam.ServicePrincipal("lambda.amazonaws.com")]
            ))
        
        #create a cdk managed ecr that contains the docker image
        docker_image = ecr_assets.DockerImageAsset(
            self,
            "PdfParserDockerImage",
            directory="./docker",
        )
        
        #replicate the image into the ecr that we created and controlled , see https://github.com/aws/aws-cdk/issues/12597 
        ecr_deployment = ecrdeploy.ECRDeployment(
            self,
            "DeployDockerImage",
            src=ecrdeploy.DockerImageName(docker_image.image_uri),
            dest=ecrdeploy.DockerImageName(f"{ecr_repo.repository_uri}:latest"),
        )
        # create lambda using the image in your ecr
        pdf_parser_lambda = lambda_.DockerImageFunction(
            self,
            "PdfParserLambda", 
            code=lambda_.DockerImageCode.from_ecr(
                repository=ecr_repo,
                tag='latest',
            ),
            memory_size=1024,
            timeout=Duration.seconds(300),
            role=lambda_role,
            environment={
                "SOURCE_BUCKET": source_bucket.bucket_name,
                "DESTINATION_BUCKET": destination_bucket.bucket_name
            }
        )

        pdf_parser_lambda.node.add_dependency(ecr_deployment)


        pdf_parser_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[source_bucket.arn_for_objects("*")]
        ))
        pdf_parser_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:PutObject"],
            resources=[destination_bucket.arn_for_objects("*")]
        ))


        source_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(pdf_parser_lambda),
            s3.NotificationKeyFilter(suffix=".pdf")
        )

        CfnOutput(self, "PdfParserLambdaArn", value=pdf_parser_lambda.function_arn)
        CfnOutput(self, "LambdaImageUri", value=pdf_parser_lambda.function_name)

class PdfParserStage(Stage):
    def __init__(self, scope: Construct, id: str, project: str,config: Configurator, tags: dict, **kwargs):
        super().__init__(scope, id, **kwargs)

        stacks = list()
        ENV_NAME = config.get_config_attribute('name')

        stack_name_identifier = "PdfParserStack" # update stack naming here
        stacks.append(
            PdfParserStack( # update stack class here
                self,
                id=stack_name_identifier,
                # dont change this stack name, will cause failure with existing resources
                # stack_name=f"{project}{stack_name_identifier}{ENV_NAME.capitalize()}",
                env=Environment(
                    account=config.get_config_attribute("account"),
                    region=config.get_config_attribute("region"),
                ),
                config=config,
            )
        )

        for stack in stacks:
            for tag in tags.keys():
                stack.tags.set_tag(key=tag, value=tags[tag])