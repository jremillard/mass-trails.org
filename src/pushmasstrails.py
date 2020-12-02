import os

# goto shared access signature, use search function, should be like this, starting with ?sv= "?sv=2019-12-12&ss= bla bla bla"

key = os.environ['MASSTRAILS-AZURE-SAS']

cmd = "azcopy rm \"https://masstrails.blob.core.windows.net/$web/*" + key + "\" --recursive"
#print(cmd)
#os.system(cmd)

cmd = "azcopy copy ..\* \"https://masstrails.blob.core.windows.net/$web" + key + "\" --recursive --exclude-path=\"src;mapstyles\" --exclude-pattern=\"*.py;*.exe;.gitignore;.htaccess;.git\""
#print(cmd)
os.system(cmd)







