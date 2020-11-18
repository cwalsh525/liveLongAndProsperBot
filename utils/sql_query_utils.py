import datetime

def update_note_query(loan_note_id):
    return """
    update notes 
    set effective_end_date = '{effective_end_date}',
        modified_ts = current_timestamp,
        latest_record_flag = 'f'
    where loan_note_id = '{loan_note_id}'
    and effective_end_date = '2099-12-31';
    """.format(effective_end_date=datetime.date.today() - datetime.timedelta(days=1), loan_note_id=loan_note_id)

def update_notes_query(loan_note_id_list):

    if len(loan_note_id_list) > 0:
            loan_note_id_sql_list = str(loan_note_id_list).replace("[", "(").replace("]", ")")
            return """
                update notes 
                set effective_end_date = '{effective_end_date}',
                modified_ts = current_timestamp,
                latest_record_flag = 'f'
                where loan_note_id in {loan_note_id_list}
                and effective_end_date = '2099-12-31';
                """.format(effective_end_date=datetime.date.today() - datetime.timedelta(days=1), loan_note_id_list=loan_note_id_sql_list)
    else:
        return ""

def check_for_api_response_value(response_object, key):
        # created because prosper doesn't include all values in notes response and adds some at certain stages ie: default
        try:
                return_value = "'{return_value}'".format(return_value=response_object[key])
        except KeyError:
                return_value = "null"
        return return_value

def insert_notes_query(response_object, effective_start_date):
        return """
        INSERT INTO notes
        (principal_balance_pro_rata_share, service_fees_paid_pro_rata_share, principal_paid_pro_rata_share, interest_paid_pro_rata_share, prosper_fees_paid_pro_rata_share, late_fees_paid_pro_rata_share, collection_fees_paid_pro_rata_share, debt_sale_proceeds_received_pro_rata_share, platform_proceeds_net_received, next_payment_due_amount_pro_rata_share, note_ownership_amount, note_sale_gross_amount_received, note_sale_fees_paid, loan_note_id, listing_number, note_status, note_status_description, is_sold, is_sold_folio, loan_number, amount_borrowed, borrower_rate, lender_yield, prosper_rating, term, age_in_months, accrued_interest, payment_received, loan_settlement_status, loan_extension_status, loan_extension_term, is_in_bankruptcy, co_borrower_application, origination_date, days_past_due, next_payment_due_date, ownership_start_date, effective_start_date, effective_end_date, created_ts, modified_ts, latest_record_flag, note_default_reason, note_default_reason_description)
        VALUES({principal_balance_pro_rata_share},
        {service_fees_paid_pro_rata_share},
        {principal_paid_pro_rata_share},
        {interest_paid_pro_rata_share},
        {prosper_fees_paid_pro_rata_share},
        {late_fees_paid_pro_rata_share},
        {collection_fees_paid_pro_rata_share},
        {debt_sale_proceeds_received_pro_rata_share},
        {platform_proceeds_net_received},
        {next_payment_due_amount_pro_rata_share},
        {note_ownership_amount},
        {note_sale_gross_amount_received},
        {note_sale_fees_paid},
        '{loan_note_id}',
        {listing_number},
        {note_status},
        '{note_status_description}',
        {is_sold},
        {is_sold_folio},
        {loan_number},
        {amount_borrowed},
        {borrower_rate},
        {lender_yield},
        '{prosper_rating}',
        {term},
        {age_in_months},
        {accrued_interest},
        {payment_received},
        '{loan_settlement_status}',
        '{loan_extension_status}',
        {loan_extension_term},
        {is_in_bankruptcy},
        {co_borrower_application},
        '{origination_date}',
        {days_past_due},
        '{next_payment_due_date}',
        '{ownership_start_date}',
        '{effective_start_date}',
        '{effective_end_date}',
        '{created_ts}',
        {modified_ts},
        '{latest_record_flag}',
        {note_default_reason},
        {note_default_reason_description})
        """.format(principal_balance_pro_rata_share=response_object['principal_balance_pro_rata_share'],
        service_fees_paid_pro_rata_share=response_object['service_fees_paid_pro_rata_share'],
        principal_paid_pro_rata_share=response_object['principal_paid_pro_rata_share'],
        interest_paid_pro_rata_share=response_object['interest_paid_pro_rata_share'],
        prosper_fees_paid_pro_rata_share=response_object['prosper_fees_paid_pro_rata_share'],
        late_fees_paid_pro_rata_share=response_object['late_fees_paid_pro_rata_share'],
        collection_fees_paid_pro_rata_share=response_object['collection_fees_paid_pro_rata_share'],
        debt_sale_proceeds_received_pro_rata_share=response_object['debt_sale_proceeds_received_pro_rata_share'],
        platform_proceeds_net_received=response_object['platform_proceeds_net_received'],
        next_payment_due_amount_pro_rata_share=response_object['next_payment_due_amount_pro_rata_share'],
        note_ownership_amount=response_object['note_ownership_amount'],
        note_sale_gross_amount_received=response_object['note_sale_gross_amount_received'],
        note_sale_fees_paid=response_object['note_sale_fees_paid'],
        loan_note_id=response_object['loan_note_id'],
        listing_number=response_object['listing_number'],
        note_status=response_object['note_status'],
        note_status_description=response_object['note_status_description'],
        is_sold=response_object['is_sold'],
        is_sold_folio=response_object['is_sold_folio'],
        loan_number=response_object['loan_number'],
        amount_borrowed=response_object['amount_borrowed'],
        borrower_rate=response_object['borrower_rate'],
        lender_yield=response_object['lender_yield'],
        prosper_rating=response_object['prosper_rating'],
        term=response_object['term'],
        age_in_months=response_object['age_in_months'],
        accrued_interest=response_object['accrued_interest'],
        payment_received=response_object['payment_received'],
        loan_settlement_status=response_object['loan_settlement_status'],
        loan_extension_status=response_object['loan_extension_status'],
        loan_extension_term=response_object['loan_extension_term'],
        is_in_bankruptcy=response_object['is_in_bankruptcy'],
        co_borrower_application=response_object['co_borrower_application'],
        origination_date=response_object['origination_date'],
        days_past_due=response_object['days_past_due'],
        next_payment_due_date=response_object['next_payment_due_date'],
        ownership_start_date=response_object['ownership_start_date'],
        effective_start_date=effective_start_date,
        effective_end_date='2099-12-31',
        created_ts=datetime.datetime.today(),
        modified_ts="null",
        latest_record_flag='t',
        note_default_reason=check_for_api_response_value(response_object=response_object, key="note_default_reason"),
        note_default_reason_description=check_for_api_response_value(response_object=response_object, key="note_default_reason_description")
        )

def insert_notes_addational_value(response_object, effective_start_date):
    return """,({principal_balance_pro_rata_share},
    {service_fees_paid_pro_rata_share},
    {principal_paid_pro_rata_share},
    {interest_paid_pro_rata_share},
    {prosper_fees_paid_pro_rata_share},
    {late_fees_paid_pro_rata_share},
    {collection_fees_paid_pro_rata_share},
    {debt_sale_proceeds_received_pro_rata_share},
    {platform_proceeds_net_received},
    {next_payment_due_amount_pro_rata_share},
    {note_ownership_amount},
    {note_sale_gross_amount_received},
    {note_sale_fees_paid},
    '{loan_note_id}',
    {listing_number},
    {note_status},
    '{note_status_description}',
    {is_sold},
    {is_sold_folio},
    {loan_number},
    {amount_borrowed},
    {borrower_rate},
    {lender_yield},
    '{prosper_rating}',
    {term},
    {age_in_months},
    {accrued_interest},
    {payment_received},
    '{loan_settlement_status}',
    '{loan_extension_status}',
    {loan_extension_term},
    {is_in_bankruptcy},
    {co_borrower_application},
    '{origination_date}',
    {days_past_due},
    '{next_payment_due_date}',
    '{ownership_start_date}',
    '{effective_start_date}',
    '{effective_end_date}',
    '{created_ts}',
     {modified_ts},
     '{latest_record_flag}',
      {note_default_reason},
      {note_default_reason_description})
    """.format(principal_balance_pro_rata_share=response_object['principal_balance_pro_rata_share'],
            service_fees_paid_pro_rata_share=response_object['service_fees_paid_pro_rata_share'],
            principal_paid_pro_rata_share=response_object['principal_paid_pro_rata_share'],
            interest_paid_pro_rata_share=response_object['interest_paid_pro_rata_share'],
            prosper_fees_paid_pro_rata_share=response_object['prosper_fees_paid_pro_rata_share'],
            late_fees_paid_pro_rata_share=response_object['late_fees_paid_pro_rata_share'],
            collection_fees_paid_pro_rata_share=response_object['collection_fees_paid_pro_rata_share'],
            debt_sale_proceeds_received_pro_rata_share=response_object['debt_sale_proceeds_received_pro_rata_share'],
            platform_proceeds_net_received=response_object['platform_proceeds_net_received'],
            next_payment_due_amount_pro_rata_share=response_object['next_payment_due_amount_pro_rata_share'],
            note_ownership_amount=response_object['note_ownership_amount'],
            note_sale_gross_amount_received=response_object['note_sale_gross_amount_received'],
            note_sale_fees_paid=response_object['note_sale_fees_paid'],
            loan_note_id=response_object['loan_note_id'],
            listing_number=response_object['listing_number'],
            note_status=response_object['note_status'],
            note_status_description=response_object['note_status_description'],
            is_sold=response_object['is_sold'],
            is_sold_folio=response_object['is_sold_folio'],
            loan_number=response_object['loan_number'],
            amount_borrowed=response_object['amount_borrowed'],
            borrower_rate=response_object['borrower_rate'],
            lender_yield=response_object['lender_yield'],
            prosper_rating=response_object['prosper_rating'],
            term=response_object['term'],
            age_in_months=response_object['age_in_months'],
            accrued_interest=response_object['accrued_interest'],
            payment_received=response_object['payment_received'],
            loan_settlement_status=response_object['loan_settlement_status'],
            loan_extension_status=response_object['loan_extension_status'],
            loan_extension_term=response_object['loan_extension_term'],
            is_in_bankruptcy=response_object['is_in_bankruptcy'],
            co_borrower_application=response_object['co_borrower_application'],
            origination_date=response_object['origination_date'],
            days_past_due=response_object['days_past_due'],
            next_payment_due_date=response_object['next_payment_due_date'],
            ownership_start_date=response_object['ownership_start_date'],
            effective_start_date=effective_start_date,
            effective_end_date='2099-12-31',
            created_ts=datetime.datetime.today(),
            modified_ts="null",
            latest_record_flag='t',
                                    note_default_reason=check_for_api_response_value(response_object=response_object, key="note_default_reason"),
                                    note_default_reason_description=check_for_api_response_value(response_object=response_object, key="note_default_reason_description")
                                       )
