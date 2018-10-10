# Build an Item Catelog Application
>The item catelog application provides a list of items within a variety of categories as well as provide a user registration and authentication system. The data was collected using Scrapy Crawler. Registered users will have the ability to post, edit and delete their own items.


## Purpose of this project
>In this project, I learned how to develop a RESTful web application using the Python framework Flask along with implementing third-party OAuth authentication. Also, I learned when to properly use the various HTTP methods and how these methods relate to CRUD (create, read, update and delete) operations.



## You need to install : 
- [Virtual Box](https://www.virtualbox.org/wiki/Download_Old_Builds_5_1)
- [Vagrant](https://www.vagrantup.com/downloads.html)
- [the VM configuration](https://github.com/udacity/fullstack-nanodegree-vm)
- [Python3](https://www.python.org/getit/)


## Running the Program
1. Inside the vagrant subdirectory, run the command ```vagrant up```.
2. When ```vagrant up``` is finished running, you will get your shell prompt back. At this point, you can run ```vagrant ssh``` to log in to your newly installed Linux VM.
4. Download the files listed below and locate them in the vagrant directory, which is shared with your virtual machine(VM).
    - crawler directory
    - static directory
    - templates directory
    - recipes.db
    - database_setup.py
    - webserver.py

5. Go to https://console.developers.google.com/apis/credentials and click ```download JSON``` and locate this file in the vagrant directory and name this file as "client_secrets.json".
6. After you log in to your VM, ```cd /vagrant``` and use the command, ```python webserver.py``` to run webserver.py. 
7. Go to your web browser and access it at http://localhost:5000/.

    
  


## Acknowldgement
Udacity - Full Stack Web Developer NanoDegree Program
Icons made by Freepik from www.flaticon.com 
Icon made by Those Icons from www.flaticon.com 
Icon made by Smashicons from www.flaticon.com 
