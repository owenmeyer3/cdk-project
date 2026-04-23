import aws_cdk as cdk
from stacks.cdk_project_stack import CdkProjectStack
import json, os

# call like: cdk synth/deploy -c env={env} --profile {local profile} --region {profile region}

app = cdk.App()
env_name=app.node.try_get_context("env")

# Get configurations for project and cli specified env 
project_config = env_config = None
with open('config.json') as f:
    config_file=json.load(f)
    project_config=config_file['project']
    env_config=config_file[env_name]

env=cdk.Environment(account=env_config['ACCOUNT'], region=env_config['REGION'])
CdkProjectStack(app, f"CdkProjectStack-{env_name}",env=env, project_config=project_config, env_config=env_config)

app.synth()
