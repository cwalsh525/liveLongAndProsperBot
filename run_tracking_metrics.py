import logging

from metrics.tracking_metrics import TrackingMetrics
import config.default as default
import log.logging as log

metrics = TrackingMetrics().execute()


# TrackingMetrics().pull_note_response("1429437-68")
#TODO add note_default_reason and note_default_reason_description as null

# TrackingMetrics().update_deposits_and_withdrawls_table()

#TODO Use 1430406-35 as example to see how early is too early for payback (6/1/20 ownership start date, paid back 6/19)
# {'principal_balance_pro_rata_share': 0.0, 'service_fees_paid_pro_rata_share': -0.030143, 'principal_paid_pro_rata_share': 50.0, 'interest_paid_pro_rata_share': 0.549714, 'prosper_fees_paid_pro_rata_share': 0.0, 'late_fees_paid_pro_rata_share': 0.0, 'collection_fees_paid_pro_rata_share': 0.0, 'debt_sale_proceeds_received_pro_rata_share': 0.0, 'platform_proceeds_net_received': 0.0, 'next_payment_due_amount_pro_rata_share': 0.0, 'note_ownership_amount': 50.0, 'note_sale_gross_amount_received': 0.0, 'note_sale_fees_paid': 0.0, 'loan_note_id': '1430406-35', 'listing_number': 11369836, 'note_status': 4, 'note_status_description': 'COMPLETED', 'is_sold': False, 'is_sold_folio': False, 'loan_number': 1430406, 'amount_borrowed': 7000.0, 'borrower_rate': 0.1824, 'lender_yield': 0.1724, 'prosper_rating': 'C', 'term': 36, 'age_in_months': 2, 'accrued_interest': 0.0, 'payment_received': 50.519571, 'loan_settlement_status': 'Unspecified', 'loan_extension_status': 'Unspecified', 'loan_extension_term': 0, 'is_in_bankruptcy': False, 'co_borrower_application': False, 'origination_date': '2020-05-28', 'days_past_due': 0, 'next_payment_due_date': '2020-06-28', 'ownership_start_date': '2020-06-01'}
# Response on 7/16/20. verify my db does not update again

 #TODO make sure '1365311-37' is still at age_of_months is 7 in db on 8/1/20 (6 if i run update complete notes record)

# In chargeoff 1378768-23
# {'principal_balance_pro_rata_share': 23.562633, 'service_fees_paid_pro_rata_share': -0.061167, 'principal_paid_pro_rata_share': 1.437367, 'interest_paid_pro_rata_share': 1.574033, 'prosper_fees_paid_pro_rata_share': 0.0, 'late_fees_paid_pro_rata_share': 0.0, 'collection_fees_paid_pro_rata_share': 0.0, 'debt_sale_proceeds_received_pro_rata_share': 0.0, 'platform_proceeds_net_received': 0.0, 'next_payment_due_amount_pro_rata_share': 0.9767, 'note_ownership_amount': 25.0, 'note_sale_gross_amount_received': 0.0, 'note_sale_fees_paid': 0.0, 'loan_note_id': '1378768-23', 'listing_number': 10803515, 'note_status': 2, 'note_status_description': 'CHARGEOFF', 'is_sold': False, 'is_sold_folio': False, 'loan_number': 1378768, 'amount_borrowed': 7500.0, 'borrower_rate': 0.2574, 'lender_yield': 0.2474, 'prosper_rating': 'E', 'term': 36, 'age_in_months': 8, 'accrued_interest': 2.509067, 'payment_received': 2.950233, 'loan_settlement_status': 'Unspecified', 'loan_extension_status': 'Unspecified', 'loan_extension_term': 0, 'is_in_bankruptcy': False, 'co_borrower_application': False, 'origination_date': '2020-01-22', 'days_past_due': 122, 'next_payment_due_date': '2020-05-22', 'ownership_start_date': '2020-01-24'}
