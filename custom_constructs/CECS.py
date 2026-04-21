from aws_cdk import (
    RemovalPolicy,
    Duration,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_logs as logs,
    aws_stepfunctions as stepfunctions,
    aws_stepfunctions_tasks as tasks,
    aws_events_targets as targets
)
from constructs import Construct
from custom_constructs.CNetwork import CNetwork
from custom_constructs.utils import get_local_project_root

class CFargateTaskDefinition(ecs.FargateTaskDefinition):
    def __init__(self, scope: Construct, construct_id: str, family:str, **kwargs):
        #### Usage ####
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ecs/FargateTaskDefinition.html
        # CFargateTaskDefinition(
        #     # Required
        #     scope, construct_id, family,
        #     # Common
        #     cpu=None, memory_limit_mib=None, execution_role=None, task_role=None, runtime_platform=None,
        #     # Uncommon - other FargateTaskDefinition kwargs
        # )
        ###############

        self.container_repo = None
        self.task_log_group = None
        super.__init__(scope, construct_id, family=family, **kwargs)
    
    def add_ecr_container(
            self,
            container_repo_name:str,
            container_repo_tag:str,
            code_location:str,
            execution_file:str,
            pre_execution_commands:list[str]=[],
            environment:dict={},
            **kwargs
    ):
        #### Usage ####
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ecs/FargateTaskDefinition.html
        # add_ecr_container(
        #     # Required
        #     container_repo_name, container_repo_tag, code_location, execution_file
        #     # Common
        #     pre_execution_commands=[], environment=None, log_group_name=None, log_retention=None, entry_point=None, environment_file=None, essential=None
        #     # Uncommon - other ecs.ContainerImage.from_ecr_repository kwargs
        # )
        ###############
        self.container_repo = ecr.Repository.from_repository_name(self, f"{self.node.id}Repo", container_repo_name)

        # add log group
        if 'logging' in kwargs:
            pass
        elif 'log_group_name' in kwargs != 'log_retention' in kwargs:
            raise ValueError("if log_group_name or log_retention are arguments, both must be arguments")
        elif 'log_group_name' in kwargs:
            log_group_name=kwargs.pop('log_group_name', None)
            log_retention=kwargs.pop('log_retention', None)
            self.task_log_group = logs.LogGroup(self, f"{self.node.id}Log", log_group_name=log_group_name, log_retention=log_retention, removal_policy=RemovalPolicy.DESTROY)
            logging=ecs.LogDriver(log_group=self.task_log_group, stream_prefix="ML", mode=ecs.AwsLogDriverMode.NON_BLOCKING)
            kwargs['logging']=logging
        
        # configure image
        image= ecs.ContainerImage.from_ecr_repository(self.container_repo, tag=container_repo_tag)
        command=''
        for cmd in pre_execution_commands:
            command = command + cmd + '&&'
        command = command + f"aws s3 cp {code_location}/ /tmp/code/ --recursive && python3 /tmp/code/{execution_file}"

        # add container (essential default true)
        if 'essential' not in kwargs:
            kwargs['essential']=True
        self.container_definition=self.add_container(
            f"{self.node.id}Cntr",
            container_name=self.family,
            image=image,
            entry_point=["bash", "-c"],
            logging=logging,
            environment=environment,
            **kwargs
        )
    
    def add_custom_container(
            self,
            **kwargs
    ):
        #### Usage ####
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ecs/FargateTaskDefinition.html
        # add_ecr_container(
        #     # Required
        #     run_file
        #     # Common
        #     build_args={}, log_group_name=None, log_retention=None, essential=None
        #     # Uncommon - other ecs.ContainerImage.from_ecr_repository kwargs
        # )
        ###############

        # add log group
        if 'logging' in kwargs:
            pass
        elif 'log_group_name' in kwargs != 'log_retention' in kwargs:
            raise ValueError("if log_group_name or log_retention are arguments, both must be arguments")
        elif 'log_group_name' in kwargs:
            log_group_name=kwargs.pop('log_group_name', None)
            log_retention=kwargs.pop('log_retention', None)
            self.task_log_group = logs.LogGroup(self, f"{self.node.id}Log", log_group_name=log_group_name, log_retention=log_retention, removal_policy=RemovalPolicy.DESTROY)
            logging=ecs.LogDriver(log_group=self.task_log_group, stream_prefix="ML", mode=ecs.AwsLogDriverMode.NON_BLOCKING)
            kwargs['logging']=logging
        
        image=None
        if 'run_file' in kwargs:
            run_file=kwargs.pop('run_file', None)
            build_args=kwargs.pop('build_args', {})
            image=ecs.ContainerImage.from_asset(
                get_local_project_root(), # docker context encompasses project files
                file=run_file, # dockerfile relative to context
                build_args=build_args
            )
        elif 'image_asset' in kwargs:
            image_asset=kwargs.pop('image_asset', None)
            image=ecs.ContainerImage.from_docker_image_asset(image_asset)
        else:
            raise ValueError("either run_file or image_asset arg required")
        
        # add container (essential default true)
        if 'essential' not in kwargs:
            kwargs['essential']=True
        self.container_definition=self.add_container(
            f"{self.node.id}Cntr",
            container_name=self.family,
            image=image,
            logging=logging,
            environment={},
            **kwargs
        )
    
    def generate_task(
            self,
            cluster:ecs.Cluster,
            network:CNetwork=None,
            env_vars:list=[],
            **kwargs
    ) -> tasks.EcsRunTask:
        #### Usage ####
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_stepfunctions_tasks/EcsRunTask.html
        # generate_task(
        #     # Required
        #     cluster
        #     # Common
        #     network, env_vars, timout_mins, platform_version, security_groups, subnets
        #     # Uncommon - other ecs.EcsRunTask kwargs
        # )
        ###############
        environment=[]
        for e in env_vars:
            val=stepfunctions.JsonPath.string_at(e["Value.$"]) if "Value.$" in list(e.keys()) else e["Value"]
            environment.append(tasks.TaskEnvironmentVariable(name=e['Name'], value=val))
        
        launch_target = kwargs.pop("launch_target", tasks.EcsEc2LaunchTarget(platform_version=ecs.FargatePlatformVersion(ecs.FargatePlatformVersion.LATEST)))
        integration_pattern = kwargs.pop("integration_pattern", stepfunctions.IntegrationPattern.WAIT_FOR_TASK_TOKEN)
        task_timeout=kwargs.pop("task_timeout", stepfunctions.Timeout.duration(Duration.minutes(10)))

        if 'assign_public_ip' not in kwargs:
            kwargs['assign_public_ip'] = False
        if 'subnets' not in kwargs:
            kwargs['subnets']=network.get_subnet_selection() if network else None
        if 'security_groups' not in kwargs:
            kwargs['security_groups']=[network.get_security_group()] if network else None

        task = tasks.EcsRunTask(
            self,
            f"{self.node.id}Task",
            task_timeout=task_timeout,
            cluster=cluster,
            launch_target=launch_target,
            integration_pattern=integration_pattern,
            container_overrides=[
                tasks.ContainerOverride(container_definition=self.container_definition, environment=environment)
            ],
            **kwargs
        )

        return task
    
    def generate_task_target(
            self,
            cluster:ecs.Cluster,
            network:CNetwork=None,
            env_vars:list=[],
            **kwargs
    ) -> targets.EcsTask:
        #### Usage ####
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events_targets/EcsTask.html
        # generate_task_target(
        #     # Required
        #     cluster
        #     # Common
        #     network, env_vars, task_timeout, platform_version, security_groups, subnets, input_path, output_path
        #     # Uncommon - other targets.EcsTask kwargs
        # )
        ###############
        environment=[]
        for e in env_vars:
            environment.append(tasks.TaskEnvironmentVariable(name=e['Name'], value=e["Value"]))
        
        if 'assign_public_ip' not in kwargs:
            kwargs['assign_public_ip'] = False
        if 'subnets' not in kwargs:
            kwargs['subnets']=network.get_subnet_selection() if network else None
        if 'security_groups' not in kwargs:
            kwargs['security_groups']=[network.get_security_group()] if network else None

        task_target = targets.EcsTask(
            cluster=cluster,
            task_definition=self,
            container_overrides=[
                targets.ContainerOverride(container_name=self.container_definition.container_name, environment=environment)
            ],
            **kwargs
        )

        return task_target