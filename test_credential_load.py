import json

with open('credential.json', 'r') as json_cr_f:
    crs = json.load(json_cr_f)
    host = crs['host']
    username = crs['username']
    password = crs['password']

print(host, username, password)
