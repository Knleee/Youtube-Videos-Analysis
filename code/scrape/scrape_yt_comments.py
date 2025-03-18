import requests
from __future__ import print_function

import io
import json
import os
import sys
import time

import argparse
import lxml.html
import requests
from lxml.cssselect import CSSSelector
from bs4 import BeautifulSoup

URL = 'https://www.youtube.com/watch?v=bargNl2WeN4'
response = requests.get(URL)

tree = lxml.html.fromstring(response.text)
sel = CSSSelector('#content-text')
ids =  [i.get('yt-core-attributed-string') for i in sel(tree)]
print(ids)

