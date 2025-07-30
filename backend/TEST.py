import requests

# Задай свои значения:
app_key = 'admin'
app_secret = 'Baguvix26'
base_url = 'http://127.0.0.1:8208'


# В Hikvision OpenAPI по умолчанию
url = f'{base_url}/artemis/api/artemis/v1/agreementService/token/get'

headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}

data = {
    'appKey': app_key,
    'appSecret': app_secret,
}

# Для некоторых систем нужен verify=False (если self-signed сертификат)
response = requests.post(url, json=data, headers=headers, verify=False)

if response.status_code == 200:
    print('Ответ:', response.json())
else:
    print('Ошибка:', response.status_code, response.text)
