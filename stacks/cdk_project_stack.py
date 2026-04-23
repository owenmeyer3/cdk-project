import os, pathlib
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_stepfunctions as stepfunctions,
    aws_events as events,
    aws_events_targets as targets,
    aws_ecr_assets as ecr_assets,
)
from constructs import Construct
from custom_constructs.CNetwork import CNetwork
from custom_constructs.CLambda import CLambdaFunction
from custom_constructs.CECS import CFargateTaskDefinition
from custom_constructs.utils import get_local_project_root

class CdkProjectStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, project_config:dict, env_config:dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.project_config=project_config
        self.env_config=env_config

        # Import existing resources
        self.execution_role=iam.Role.from_role_arn(self, "ImportedExecutionRole", env_config['EXECUTION_ROLE_ARN'], mutable=False)
        self.network = CNetwork(self, "ImportedNetwork", region=env_config['REGION'], vpc_config=env_config['VPC_CONFIG'])
        self.cluster = ecs.Cluster.from_cluster_attributes(self, "ImportedCluster", cluster_name=env_config['CLUSTER_NAME'], vpc=self.network.get_vpc())

        chain = stepfunctions.Pass(self, 'Start')
        end_pass = stepfunctions.Pass(self, 'End')

        event_pattern = events.EventPattern(
            source=events.Match.exact_string("aws.s3"),
            detail_type=events.Match.exact_string("Object Created"),
            detail={
                "bucket":{"name":env_config['SOURCE_FILE_BUCKET']},
                "object":{
                    "key": events.Match.any_of(
                        events.Match.wildcard('key-path/to/a/*.json'),
                        events.Match.wildcard('key-path/to/b/*.json')
                    )
                }
            }
        )

        # Make image asset for all functions
        image_asset = self.get_task_image_asset()

        # make task to classify documents
        classify_doc_task, classify_doc_function = self.get_classify_fn_task(image_asset, end_pass)

        # make map to direct documents to process tasks
        map_end_pass = stepfunctions.Pass(self, "MapEnd")
        doc_map_chain = None
        doc_map = stepfunctions.Map(
            self, "Map",
            item_selector={
                "target_folder.$":"$$.Map.Item.Value", 
                "key.$":"$.event.detail.object.key", 
                "bucket.$":"$.event.detail.bucket.name"
            },
            result_path="$.DocTasks",
            items_path="$.ClassifyInboundEmail.body.docMetadata.classifications"
        )

        process_doc_1_task = self.get_process_1_task(image_asset, map_end_pass)
        process_doc_2_task = self.get_process_2_task(image_asset, map_end_pass)
        process_doc_3_task = self.get_process_3_task(image_asset, map_end_pass)

        doc_map_chain = stepfunctions.Choice(self, "MapChoice") \
            .when(stepfunctions.Condition.string_equals("$.classifications", "type-1"), \
                process_doc_1_task.next(map_end_pass)\
            ).when(stepfunctions.Condition.string_equals("$.classifications", "type-2"), \
                process_doc_2_task.next(map_end_pass)) \
            .when(stepfunctions.Condition.string_equals("$.classifications", "type-3"), \
                process_doc_3_task.next(map_end_pass)) \
            .otherwise( \
                map_end_pass \
            )
        doc_map.item_processor(doc_map_chain)

        # Make state machine
        chain.next(classify_doc_task).next(doc_map).next(end_pass)
        state_machine=stepfunctions.StateMachine(
            self, "SM",
            definition_body=stepfunctions.DefinitionBody.from_chainable(chain),
            role=self.execution_role,
            logs=stepfunctions.LogOptions(
                destination=logs.LogGroup(
                    self, "SMLog",
                    log_group_name=f"/ML/{self.env_config['ENV']}/states/{project_config['NAME']}",
                    removal_policy=RemovalPolicy.DESTROY,
                    retention=logs.RetentiuonDays.ONE_MONTH
                ),
                level=stepfunctions.LogLevel.ALL, 
                include_execution_data=True
            )
        )
        # Allow state machine access to call calssify lambda
        classify_doc_function.add_invoker_arn(state_machine.state_machine_arn)

        # Make state machine trigger
        launch_rule = events.Rule(
            self, "Trigger",
            event_pattern=event_pattern,
            targets=[
                targets.SfnStateMachine(
                    state_machine,
                    role=self.execution_role,
                    input=events.RuleTargetInput.from_object({"event":events.EventField.from_path("$")})
                )
            ]
        )


    def get_task_image_asset(self):
        return ecr_assets.DockerImageAsset(
            self, "ImageA",
            directory=get_local_project_root(),
            file="infrastructure/cdk-project-image/Dockerfile",
            build_args={"GIT_USERNAME":os.environ.get("GIT_USERNAME"), "GIT_TOKEN":os.environ.get("GIT_TOKEN")}
        )
    
    def get_classify_fn_task(self, image_asset, catcher):
        function_name = "classify-doc",
        lambda_function = CLambdaFunction(
            self, "ClassifyFn",
            use_docker=True,
            image_asset=image_asset,
            function_name=function_name,
            entrypoint=['sh','-c','python3 -m awslambdaric classify_doc.lambda_function.lambda_handler'],
            role=self.execution_role,
            environment={"ENV":self.env_config["ENV"]},
            log_group_name=f"/ML/{self.env_config['ENV']}/lambda/{function_name}",
            log_retention=logs.RetentionDays.ONE_MONTH
        )

        task = lambda_function.generate_task(
            payload={"SOURCE_FILE_KEY.$":"$.event.detail.object.key","SOURCE_FILE_BUCKET.$":"$.event.detail.bucket.name","TRACE_ID.$":"$$.Execution.Id"},
            result_selector={"body.$":"$.Payload.docMetadata"}
        )

        return [task, lambda_function]
    
    def get_process_1_task(self, image_asset, catcher):
        task_definition_family=f"{self.project_config['NAME']}-type-1"
        task_definition= CFargateTaskDefinition(
            self, "Task1Def",
            family=task_definition_family,
            execution_role=self.execution_role,
            task_role=self.execution_role
        )
        task_definition.add_custom_container(
            image_asset=image_asset,
            command=["python3", "process-doc-1"],
            log_group_name=f"/ML/{self.env_config['ENV']}/ecs/{task_definition_family}",
            task_role=self.execution_role
        )
        task=task_definition.generate_task(
            cluster=self.cluster,
            network=self.network,
            env_vars=[
                {"Name":"TASK_TOKEN", "Value.$":"$$.Task.Token"},
                {"Name":"TRACE_ID", "Value.$":"$$.Execution.Id"},
                {"Name":"SOURCE_FILE_KEY", "Value.$":"$.event.detail.object.key"},
                {"Name":"SOURCE_FILE_BUCKET", "Value.$":"$.event.detail.bucket.name"},
                {"Name":"CLASSIFICATION", "Value.$":"$$.classification"}
            ],
            resultPath="$.ProcessDoc1Task"
        )
        return task


    def get_process_2_task(self, image_asset, catcher):
        task_definition_family=f"{self.project_config['NAME']}-type-2"
        task_definition= CFargateTaskDefinition(
            self, "Task2Def",
            family=task_definition_family,
            execution_role=self.execution_role,
            task_role=self.execution_role
        )
        task_definition.add_custom_container(
            image_asset=image_asset,
            command=["python3", "process-doc-2"],
            log_group_name=f"/ML/{self.env_config['ENV']}/ecs/{task_definition_family}",
            task_role=self.execution_role
        )
        task=task_definition.generate_task(
            cluster=self.cluster,
            network=self.network,
            env_vars=[
                {"Name":"TASK_TOKEN", "Value.$":"$$.Task.Token"},
                {"Name":"TRACE_ID", "Value.$":"$$.Execution.Id"},
                {"Name":"SOURCE_FILE_KEY", "Value.$":"$.event.detail.object.key"},
                {"Name":"SOURCE_FILE_BUCKET", "Value.$":"$.event.detail.bucket.name"},
                {"Name":"CLASSIFICATION", "Value.$":"$$.classification"}
            ],
            resultPath="$.ProcessDoc2Task"
        )
        return task
    

    def get_process_3_task(self, image_asset, catcher):
        task_definition_family=f"{self.project_config['NAME']}-type-3"
        task_definition= CFargateTaskDefinition(
            self, "Task3Def",
            family=task_definition_family,
            execution_role=self.execution_role,
            task_role=self.execution_role
        )
        task_definition.add_custom_container(
            image_asset=image_asset,
            command=["python3", "process-doc-3"],
            log_group_name=f"/ML/{self.env_config['ENV']}/ecs/{task_definition_family}",
            task_role=self.execution_role
        )
        task=task_definition.generate_task(
            cluster=self.cluster,
            network=self.network,
            env_vars=[
                {"Name":"TASK_TOKEN", "Value.$":"$$.Task.Token"},
                {"Name":"TRACE_ID", "Value.$":"$$.Execution.Id"},
                {"Name":"SOURCE_FILE_KEY", "Value.$":"$.event.detail.object.key"},
                {"Name":"SOURCE_FILE_BUCKET", "Value.$":"$.event.detail.bucket.name"},
                {"Name":"CLASSIFICATION", "Value.$":"$$.classification"}
            ],
            resultPath="$.ProcessDoc3Task"
        )
        return task
