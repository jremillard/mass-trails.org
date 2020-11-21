import os
import time
import datetime


# MA extract is read at 19:00 every day.
#dt = datetime.datetime.now()  
#while dt.hour < 19:
#    dt = datetime.datetime.now()  
#    time.sleep(60)

os.system('python getosm.py')
os.system("python properties.py")
os.system("python makepages.py")
os.system("python trails.py")

