import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()

client = APIClient()
client.force_authenticate(user=admin)

print('=' * 70)
print('PAGINATION CHECK')
print('=' * 70)

endpoints = [
    ('Departments', '/api/v1/departments/'),
    ('Employees', '/api/v1/employees/'),
    ('Documents', '/api/v1/documents/'),
    ('Requests', '/api/v1/requests/'),
]

for name, url in endpoints:
    print(f'\n{name} ({url})')
    print('-' * 70)
    resp = client.get(url)
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, dict) and 'results' in data:
            print(f'OK Paginated')
            print(f'Total: {data.get("count", "?")}')
            print(f'Page size: {len(data.get("results", []))}')
            print(f'Next: {"Yes" if data.get("next") else "No"}')
        elif isinstance(data, list):
            print(f'ERROR Not paginated (list)')
            print(f'Items: {len(data)}')
    else:
        print(f'ERROR HTTP {resp.status_code}')

print('\n' + '=' * 70)
