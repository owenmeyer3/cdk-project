def lambda_handler(event, context):

    try:
        bucket_name=event.get("SOURCE_FILE_BUCKET")
        file_key=event.get("SOURCE_FILE_KEY")

        # some logic to arrange an array of classifications for this doc
        classifications=[]

        return {
            'statusCode':200,
            'docMetadata':{
                'bucket':bucket_name,
                'key':file_key,
                'classifications':classifications
            }
        }
    except Exception as e:
        print(f'Exception occured: {str(e)}')