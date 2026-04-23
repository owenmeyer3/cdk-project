import boto3, os, subprocess

def build(image_name, dockerfile, context, build_args, force_rebuild=False):
    cmd = ['docker', 'build']

    if force_rebuild:
        cmd += ['--no-cache']
    cmd += ['-t', image_name, '-f', dockerfile, context]
    print('===DOCKER CLI===')
    print('>> ' + " ".join(cmd))
    print('================')

    for key in list(build_args.keys()):
        cmd.append('--build-arg')
        cmd.append(f'{key}={build_args[key]}')

    with subprocess.Popen(cmd, stdout=subprocess.PIP, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace') as proc:
        for line in proc.stdout:
            print(line, end='')
        proc.wait()
        print(f'\nBuild exited with code {proc.returncode}')

def run(execution_cmd, local_profile, region_name, execution_role_arn, environment):
    print('Assuming AWS role...')
    session=boto3.session(profile_name=local_profile)
    sts_client=session.client('sts', region_name='region_name')
    assumed_role=sts_client.assume_role(RoleArn=execution_role_arn, RoleSessionName='local-docker-session')
    creds=assumed_role['Credentials']
    access_vars = {"AWS_ACCESS_KEY": creds['AccessKeyId'], "AWS_SECRET_ACCESS_KEY": creds['SecretAccessKey'], "AWS_SESSION_TOKEN":creds['SESSION_TOKEN']}

    env_vars = access_vars | environment

    cmd = ['docker', 'run', '--rm', '-t']

    for key, val in env_vars.items():
        cmd += execution_cmd
    
    print('===DOCKER CLI===')
    print('>> ' + " ".join(cmd))
    print('================')

    with subprocess.Popen(cmd, stdout=subprocess.PIP, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace') as proc:
        for line in proc.stdout:
            print(line, end='')
        proc.wait()
        print(f'\nContainer exited with code {proc.returncode}')

if __name__== "__main__":
    image_name = 'cdk-project-image'
    local_profile = ''
    execution_role_arn = ''
    dockerfile = r'path/to/Dockerfile'
    context = r'path/to/cdk-project'
    build_args={}
    environment={}

    build(image_name, dockerfile, context, build_args, force_rebuild=False)

    execution_cmd = [image_name, 'python', '-u', 'function-name/main.py']
    run(execution_cmd, local_profile, execution_role_arn, environment)
