# Tạo file elasticsearch_patch.py
@"
# Code để thêm vào database.py sau dòng check PostgreSQL

        # Check Elasticsearch
        try:
            import requests
            response = requests.get('http://localhost:9200/_cluster/health', timeout=5)
            if response.status_code == 200:
                health['elasticsearch'] = True
        except:
            pass
"@ | Out-File -FilePath elasticsearch_patch.py
