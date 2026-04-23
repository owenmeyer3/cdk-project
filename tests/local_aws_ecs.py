import boto3

if __name__== "__main__":
    local_profile = ''
    session=boto3.session(profile_name=local_profile)
    ecs=session.client('ecs')

    response = ecs.run_task(
        cluster='',
        taskDefinition='',
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration':{
                'subnets':[], 
                'security_groups':[], 
                'assignPublicIp':'DISABLED'
                }
        },
        overrides={
            "containerOverrides":[
                {
                    'name':'',
                    'environment':[{'name':'', 'value':''}]
                }
            ]
        }
    )

    print(response)