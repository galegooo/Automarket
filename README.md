# Automarket
Automarket is a tool to automatically alter the price of cards posted in https://www.cardmarket.com
TCGs tested -> MTG 

This is a personal project, it's working fine in my machine as of this commit but it might break in the future.
Tested in Ubuntu Server and Arch Linux.

## How to use it
Create a .env in the same directory as main.py containing the following keywords:
- LOGINUSER = <your username>
- PASSWORD = <your password>
- BROWSER = <the path to the browser executable>
- URL = <the URL of the website>
- LOGDIR = <path to logs (leave empty for same path as main.py)>

Run `python main.py <value to start in>`
