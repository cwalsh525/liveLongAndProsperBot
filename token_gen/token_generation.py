import requests

"""
Returns access_token to connect to prosper api
"""
class TokenGeneration:

    def __init__(self, client_id, client_secret, ps, username):
        self.client_id = client_id # TODO find safe way to implement
        self.client_secret = client_secret
        self.ps = ps
        self.username = username

    def execute(self):

        url = "https://api.prosper.com/v1/security/oauth/token"
        payload = "grant_type=password&client_id={client_id}&client_secret={client_secret}&username={user}&password={ps}"\
            .format(client_id=self.client_id, client_secret=self.client_secret, user=self.username, ps=self.ps)

        headers = {'accept': "application/json", 'content-type': "application/x-www-form-urlencoded"}
        response = requests.request("POST", url, data=payload, headers=headers)
        response.encoding = 'utf-8'
        token_response = response.json()
        access_token = token_response['access_token']
        return access_token
