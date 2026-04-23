from aws_cdk import (
    RemovalPolicy,
    Duration,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_stepfunctions as stepfunctions,
    aws_stepfunctions_tasks as tasks,
    aws_events_targets as targets
)
from constructs import Construct
from custom_constructs.CNetwork import CNetwork
from custom_constructs.utils import get_local_project_root

class CLambdaFunction(Construct):
    def __init__(self, scope: Construct, construct_id: str, use_docker:bool, log_group_name:str, log_retention:str, **kwargs):
        #### Usage ####
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/DockerImageFunction.html
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
        # CLambdaFunction(
        #     # Required
        #     scope, construct_id, use_docker,
        #     # Common
        #     log_group_name & log_retention || log_group
        #     # Uncommon - other DockerImageFunction or Function kwargs
        # )
        ###############

        super.__init__(scope, construct_id)

        # add log group
        if 'log_group' in kwargs:
            pass
        elif 'log_group_name' in kwargs != 'log_retention' in kwargs:
            raise ValueError("if log_group_name or log_retention are arguments, both must be arguments")
        elif 'log_group_name' in kwargs:
            log_group_name=kwargs.pop('log_group_name', None)
            log_retention=kwargs.pop('log_retention', None)
            self.task_log_group = logs.LogGroup(self, f"{self.node.id}Log", log_group_name=log_group_name, log_retention=log_retention, removal_policy=RemovalPolicy.DESTROY)
            kwargs['log_group']=self.task_log_group
        
        if use_docker:
            image_code=None
            if 'dockerfile' not in kwargs == 'image_asset' not in kwargs:
                raise ValueError("dockerfile or image_asset argument must be specified (not neither or both) when using a docker lambda function")
            dockerfile=kwargs.pop('dockerfile', None)
            image_asset=kwargs.pop('dockerfile', None)
            build_args=kwargs.pop('build_args', {})
            if dockerfile:
                image_code=_lambda.DockerImageCode.from_image_asset(directory=get_local_project_root(), file=dockerfile, build_args=build_args)
            else:
                entrypoint = kwargs.pop('entrypoint', ['python3', '-m', 'awslambdaric'])
                image_code=_lambda.DockerImageCode(repository=image_asset.repository, tag_or_digest=image_asset.image_tag, entrypoint=entrypoint)
            self.fn=_lambda.DockerImageFunction(self, f"{self.node.id}Fn", code=image_code, **kwargs)
        else:
            if 'code_path' not in kwargs or 'handler' not in kwargs or 'runtime' not in kwargs:
                raise ValueError("if code_path, handler and runtime msut exist for lambda function when not using docker")
            code_path=kwargs.pop('code_path', None)
            handler=kwargs.pop('handler', None)
            runtime=kwargs.pop('runtime', None)
            self.fn=_lambda.Function(self, f"{self.node.id}Fn",runtime=runtime,handler=handler,code = _lambda.Code.from_asset(code_path), **kwargs)
    
    def generate_task(self, payload:dict={}, **kwargs) -> tasks.LambdaInvoke:
        task_timeout=kwargs.pop('task_timeout', stepfunctions.Timeout.duration.minutes(10))
        task = tasks.LambdaInvoke(
            self, f"{self.node.id}Task", 
            lambda_function=self.fn, 
            payload=stepfunctions.TaskInput.from_object(payload), 
            task_timeout=task_timeout, 
            retry_on_service_exceptions=False, 
            **kwargs
            )
        return task
    
    def add_invoker_arn(self, invoker_arn, **kwargs):
        # Add policy to lambda to allow stepfunction to invoke
        _lambda.CfnPermission(
            self, f"{self.node.id}InvkPerm",
            action="lambda:InvokeFunction",
            function_name=self.fn.function_name,
            principal="states.amazonaws.com",
            source_arn=invoker_arn,
            **kwargs
        )