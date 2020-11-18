import requests

import config.default as default


class Accounts:

    def __init__(self, header):
        self.config = default.config
        self.header = header

    """
    {'available_cash_balance': 1111.118327, 'pending_investments_primary_market': 150.0, 'pending_investments_secondary_market': 0.0, 'pending_quick_invest_orders': 0.0, 'total_principal_received_on_active_notes': 2959.1, 'total_amount_invested_on_active_notes': 18450.8, 'outstanding_principal_on_active_notes': 15491.704569, 'total_account_value': 16752.824569, 'pending_deposit': 0.0, 'last_deposit_amount': 1000.0, 'last_deposit_date': '2020-06-13', 'last_withdraw_amount': 400.0, 'last_withdraw_date': '2020-04-20', 'external_user_id': '399F8E08-422D-43F3-AC71-A137BDE90DF3', 'prosper_account_digest': '5X5JmP6mD1Sy9ls8jwAHjY9WW8XTLbg6IodS8+bz+uM=', 'invested_notes': {'NA': 0, 'HR': 649.197416, 'E': 2633.648255, 'D': 1606.104588, 'C': 4202.581832, 'B': 4614.775705, 'A': 1360.839832, 'AA': 362.839185}, 'pending_bids': {'NA': 0, 'HR': 0, 'E': 0, 'D': 0, 'C': 0, 'B': 150.0, 'A': 0, 'AA': 0}}
    """
    def get_account_response(self):
        build_url = self.config['prosper']['prosper_base_url']
        response = requests.get("{build_url}/accounts/prosper".format(build_url=build_url), headers=self.header).json()
        return response
