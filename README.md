# Automarket
Automarket is a tool to automatically alter the price of cards posted in https://www.cardmarket.com
TCGs tested -> MTG, Pokemon, YuGiOh

This is a personal project, it's working fine in my machines but it might break in the future (as it has several times).
Tested in Ubuntu Server and Arch Linux.

## How to use it
Create a .env in the same directory as main.py containing the following keywords:
- LOGINUSER	= <your username>
- PASSWORD	= <your password>
- BROWSER	= <the absolute path to the browser executable>
- LOGDIR	= <relative path to logs (leave empty for same directory as main.py)>
- TCG		= <TCG that the program should work in>

Then run `python main.py <value to start in>`
