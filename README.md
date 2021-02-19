# liveLongAndProsperBot
A program that invests through Prosper's API. 
The program must have filter/s in place and based off of those filters will invest in those notes that meet the filter criteria.

## Running the program
I use crontab scheduler to run the program (run.py) at noon and 6 pm EST weekdays. This is when prosper posts new loans

    run.py: 
        This is deprecated in lieu of runV1
        This runs the program, in this script it checks to see if new loans have been posted by prosper, if yes the program is ran
        Since the program checks to see if you already invested in a loan, this can be running continuously without fear of double dipping in a specific note
        Prosper posts loans at noon and 6 pm est, typically 20 - 180 seconds after the hour, as soon as new loans are found, the program runs the Listing class to find listings that meet the filters
        I run run.py multiple times as sometimes Prosper posts loans in batches
        Sometimes prosper posts loans late (i run again on the 30 min after they are supposed to post, just to be safe)
        
    runV1.py: 
        Utilizes search_and_destory.py which runs the listing and order together as one thread to speed up order submission in an attempt to lower the amount of notes that return "EXPIRED" right away
    
    run_tracking_metrics.py
        This handles inserts and updates to the postgres backend that track the metrics
        I prefer having my own backend for more robust analysis than the Prosper UI provides
        This script should be run daily.
    
    metrics_email.py
        This sends my daily metrics analysis to myself to track my prosper investments.
    
    update_missing_notes.py
        This script will check all notes through Prosper API and if that note does not exist in the my backend, it will create a record for it.
        This should never create any records when run on production. This script does help though with local testing to create a full and current notes table.
        This script should only be run in a testing environment and will have no affect on a "production" enviroment. If it does then there is a bug in my backend ETL.
        
        
### Known Issues
    20% of listings i try to invest in give me "EXPIRED" will it help if i can make my process even faster?
    Most likely will not decrease that 20% of bids that go expired if i speed up the program as the Listings class takes around 0.5 - 1 second to run, the majoirty of the few seconds of run time is the API communicaiton with Prosper.
    Most likely Prosper's Auto-Invest feature takes prioirty over API orders and the note simply is full before i can even submit a bid.
    My specific filters (which are not attached to github) only return on average 2 - 3 notes a day, so this 20% being EXPIRED is something i may want to figure out
    See ##### Make program run faster section

### Features
* Will not invest in a loan that has already been invested in (Prosper API has this feature, but it does not always work / if you send multiple listing_ids in one order and one of those listing_ids is in "PENDING_COMPLETION" the whole order is not taken)
* Uses a new thread for each filter instead of searching sequentially for faster run times
* If available cash is not sufficient for desired bid amount on a note/s, the Order class will change the bid amount to still invest in the note. Assuming cash is above $25 and bid amount is above $25.
* Has a database for tracking built into program
* Has metric tracking that tracks return on investment, note default tracking as compared to prosper baseline and my own filters

#### Future Enhancements
##### Priority
* Add Testing Suite. Will probably have to break down functions slightly to do so. include code cleanup
* Will need to create logic to not invest more than 10% of total note amount when bid amount reaches $200 (as $2000 is min loan amount for a borrower)
##### Lesser Prioirty
* Balance note ownership and purchasing by prosper_rating (currently program invests if the criteria is met, add functionality to balance the weight by prosper rating if desired)
* Create a calculator that determines how much notes to buy to hold a certain portfolio value
##### Make program run faster
* Done
