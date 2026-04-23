
# AWS CDK Project Use Case

This project currently serves as a use case for ML document processing operations

The project creates a pipeline in the form of an AWS State Machine to do the following:
- Set up an EventBridge trigger to launch the StateMachine when json file metadata lands in a specified S3 directory
- Execute a Lambda function which uses the metadata to classify the document based on the source and document characteristics
- Map the documents to one or more ECS tasks based on its classification, to process the document as needed

A few notes on this project
- The project is built for an AWS account with an existing Virtual Private cloud (VPC) configuration, ECS cluster, and IAM roles made to execute many of the AWS Services
- The project includes many reusable custom classes which would be useful in other projects
- The code in the ECS tasks and Lambda function is incomplete, as this is currently an example of an AWS Cloudformation Stack with no specific logical purpose in classifying documents
- There is a shared Docker image which is set up to be able to run Lambda functions and ECS tasks. In practice, configuring multiple images could prove useful for a project with other configurations
- Testing files have been included to aid on development. If a user is developing locally, there is a file useful in executing project logic within the local docker container before it is pushed to ECR. There is also a file useful to directly launch ECS tasks on the existing ECS cluster after deployment to a development environment. This tends to be useful when the task is meant to be triggered by an event or as part of a state machine, so that developers can instead test each task separately