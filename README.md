# mtstats
Mystery Tournament stats generator

Requirements:
* python3
* trueskill library (pip install trueskill)

File list:
* matches.data - scraped data from SRL site
* matches.txt - list of all mystery tournament matches
* ts_final.txt - generated ranking
* ts.py - main script

ts_final.txt was generated with `ts.py -lrmg --addplace --addheader`, run `ts.py -h` to get command-line help
