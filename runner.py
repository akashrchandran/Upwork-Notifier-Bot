#!/usr/bin/env python3
from apscheduler.schedulers.blocking import BlockingScheduler
import subprocess

# function to invoke the main script
def cron_process():
    subprocess.Popen("python3 upwork_job_feed_notifier.py", shell=True)


logo = \
'''
ooooo     ooo                                                oooo        
`888'     `8'                                                `888        
 888       8  oo.ooooo.  oooo oooo    ooo  .ooooo.  oooo d8b  888  oooo  
 888       8   888' `88b  `88. `88.  .8'  d88' `88b `888""8P  888 .8P'   
 888       8   888   888   `88..]88..8'   888   888  888      888888.    
 `88.    .8'   888   888    `888'`888'    888   888  888      888 `88b.  
   `YbodP'     888bod8P'     `8'  `8'     `Y8bod8P' d888b    o888o o888o 
               888                                                       
              o888o                                                      
                                                            ~ Notifier                             
'''
print(logo, end="\n\n")
print("Enter the invterval to run the script: ")
print("Leave blank to run the script every hour")

# if user leave it blank assgin 1 to hours
hours = int(input("Hours: ") or 1)

# if user leave it blank assgin 0 to minutes and seconds
minutes = int(input("Minutes: ") or 0)
seconds = int(input("Seconds: ") or 0)

# initialize the scheduler
scheduler = BlockingScheduler()

# add the job to the scheduler
scheduler.add_job(cron_process, 'interval', hours=hours, minutes=minutes, seconds=seconds)

# start the scheduler
scheduler.start()