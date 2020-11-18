import requests

from metrics.connect import Connect
from token_gen.token_generation import TokenGeneration

import config.default as default
import utils.utils as utils
import notes.note_utils as note_util
from utils import sql_query_utils

"""
This class checks for notes that do not exist in the notes table but exist
The above condition of having notes that do not exist in the database but exist should never happen in prod
This class typically only gets used to populate the notes table in dev
"""

class UpdateMissingNotes(Connect):

    def __init__(self):
        self.config = default.config
        self.access_token = access_token = TokenGeneration(
            client_id=self.config['prosper']['client_id'],
            client_secret=self.config['prosper']['client_secret'],
            ps=self.config['prosper']['ps'],
            username=self.config['prosper']['username']
        ).execute()
        self.header = utils.http_header_build(access_token)
        Connect.__init__(self) # Initialize connection

    def build_note_ids(self):
        note_ids = self.populate_list_from_single_column_sql_query(note_util.build_get_note_id_query())
        self.close_connection()
        return note_ids

    def build_all_note_ids(self):
        offset = 0
        response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2019-11-25", 25), headers=self.header, timeout=30.0).json()
        note_ids = []
        while True:
            for l in response['result']:
                note_ids.append(l['loan_note_id'])
            offset += 25
            response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2019-11-25", 25), headers=self.header, timeout=30.0).json()
            if response['result'] is None:
                break
        return note_ids

    def execute(self):
        note_ids_to_insert = []
        database_note_ids = self.populate_list_from_single_column_sql_query(note_util.build_get_note_id_query())
        all_note_ids = self.build_all_note_ids()
        for note in all_note_ids:
            if note not in database_note_ids:
                note_ids_to_insert.append(note)
        print("Number of notes to insert: {num}".format(num=len(note_ids_to_insert)))
        for note in note_ids_to_insert:
            response = requests.get(note_util.get_url_get_request_note(note), headers=self.header, timeout=30.0).json()
            print(response['loan_note_id'])
            self.execute_insert_or_update(sql_query_utils.insert_notes_query(response, response['origination_date']))
        self.close_connection()

    def testing(self):
        offset = 0
        response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2019-11-25", 25), headers=self.header, timeout=30.0).json()
        note_ids = []
        principal_balance = 0
        while True:
            for l in response['result']:
                principal_balance += l['principal_balance_pro_rata_share']
            offset += 25
            response = requests.get(note_util.get_url_get_request_notes_by_date(offset, "2016-11-25", 25), headers=self.header, timeout=30.0).json()
            if response['result'] is None:
                break
        return principal_balance
