import json
import boto3
import os
import tempfile
import hashlib
from json.decoder import JSONDecodeError
from contextlib import closing
import unicodedata

AWS_BUCKET_S3 = os.environ['AWS_BUCKET_S3']
AWS_DYNAMODB_TABLE = os.environ['AWS_DYNAMODB_TABLE'] 


def v2_tts(event, context):
    try:
        # Coleta os dados passados pelo método POST
        request = json.loads(event.get('body'))
        received_phrase = request.get('phrase')

        
        # Verifica se a frase passada possui informação
        if received_phrase == '':
            response = {"statusCode": 400, "body": "Frase vazia"}
            return response

        # Services Clients
        s3_client = boto3.client('s3')
        polly_client = boto3.client('polly')
        db_client = boto3.client('dynamodb')
        
        # Gera áudio com frase informada
        audio = polly_client.synthesize_speech(Engine='neural',
                                          Text=received_phrase, 
                                          OutputFormat='mp3',
                                          VoiceId='Vitoria')
        
        #remove os ascentos da frase
        received_phrase = ''.join(c for c in unicodedata.normalize('NFD', received_phrase) if not unicodedata.combining(c))

        # Gera Arquivo
        file_phrase_name = received_phrase.replace(" ", "_")
        Temporaryfile = os.path.join(tempfile.gettempdir(), f'{file_phrase_name}.mp3')

        # Leitura do arquivo de áudio
        with closing(audio['AudioStream']) as audioStream:
            with open(Temporaryfile,'wb') as file:
                file.write(audioStream.read())

        # Repassar ÁUDIO para S3
        s3_file = f'audios/{file_phrase_name}.mp3'
        s3_client.upload_file(Temporaryfile, AWS_BUCKET_S3, s3_file)

        # Áudio com acesso público
        s3_client.put_object_acl(ACL='public-read', Bucket=AWS_BUCKET_S3, Key=s3_file)

        # Informação da url do áudio
        url_to_audio = f'https://{AWS_BUCKET_S3}.s3.amazonaws.com/{s3_file}'

        # Informação de última alteração
        metaData = s3_client.head_object(Bucket=AWS_BUCKET_S3, Key=s3_file)
        created_audio = metaData['LastModified']
        created_audio = created_audio.strftime("%d-%m-%Y %H:%M:%S")

        # Gerar hash única para a frase
        hash_obj = hashlib.sha256(received_phrase.encode())
        hash_hexa = hash_obj.hexdigest()
        id_db = hash_hexa

        # Cria item para add na tabela
        item = {
        'id': {'S': str(id_db)},
        'received_phrase': {'S': received_phrase},
        'url_to_audio': {'S': url_to_audio},
        "created_audio": {'S': created_audio}
        }

        # Salvar item na tabela
        db_client.put_item(TableName = AWS_DYNAMODB_TABLE, Item = item)
        
        # Retorno
        body = {
            "received_phrase": received_phrase,
            "url_to_audio": url_to_audio,
            "created_audio": created_audio,
            "unique_id": str(id_db)
        }
        response = {"statusCode": 200, "body": json.dumps(body)}
    # Trata erros em requisição
    except(TypeError,JSONDecodeError):
        response = {"statusCode": 400, "body": "Requisição inválida "}
    
    return response
