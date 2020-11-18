import requests

import config.default as default

from token_gen.token_generation import TokenGeneration

import utils.utils as utils
import notes.note_utils as note_util

class Notes: #TODO make base class for all note stuff


    def __init__(self):
        self.config = default.config
        self.access_token = access_token = TokenGeneration(
            client_id=self.config['prosper']['client_id'],
            client_secret=self.config['prosper']['client_secret'],
            ps=self.config['prosper']['ps'],
            username=self.config['prosper']['username']
        ).execute()
        self.header = utils.http_header_build(access_token)

    @staticmethod
    def identify_default_or_not(json, include_late_to_default):
        if json['note_status_description'] == 'CURRENT' and json['days_past_due'] > 14:  # Accounting only more than 15 days late as defulted
            if include_late_to_default:
                gain = json['payment_received'] - json['principal_balance_pro_rata_share']
            else:
                gain = json['principal_balance_pro_rata_share']
        elif json['note_status_description'] != 'CURRENT' and json['note_status_description'] != 'COMPLETED': # assume completed has been reinvested
            gain = json['payment_received'] - json['principal_balance_pro_rata_share']
        else:
            gain = json['principal_balance_pro_rata_share']
        return gain

    def get_account_value(self):
        offset = 0
        response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2016-11-25", 25), headers=self.header, timeout=30.0).json()
        principal_balance = 0
        principal_balance_without_late = 0

        while True:
            for l in response['result']:
                principal_balance += self.identify_default_or_not(json=l, include_late_to_default=True)
                principal_balance_without_late += self.identify_default_or_not(json=l, include_late_to_default=False)
            offset += 25
            response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2016-11-25", 25), headers=self.header, timeout=30.0).json()
            if response['result'] is None:
                break
        return principal_balance, principal_balance_without_late
