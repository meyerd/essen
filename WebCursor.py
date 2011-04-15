# -*- coding: utf-8 -*-
# Copyright 2008 Johannes Weißl
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import urllib2
import urllib
import cookielib
import os

class WebCursor(object):
    """Helper object for surfing through the web"""

    def __init__(self, cookiefile = '', referer = '', user_agent = 'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)'):
        self.cj = cookielib.LWPCookieJar()
        self.cookiefile = cookiefile
        if os.path.isfile(self.cookiefile):
            self.cj.load(self.cookiefile)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
        urllib2.install_opener(opener)
        self.referer = referer
        self.header = {'Referer': referer, 'User-Agent': user_agent}

    def save_cookie(self):
        self.cj.save(self.cookiefile, ignore_discard=True, ignore_expires=True)

    def get(self, url, data = None):
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
	try:
	        if data != None:
        	    data = urllib.urlencode(data)
	        req = urllib2.Request(url, data, self.header)
        	response = urllib2.urlopen(req)
	except Exception,e:
		return ""
        self.header['Referer'] = url
        return response.read()

    def clear_referer(self):
        del self.header['Referer']

    def set_referer(self, url):
        self.header['Referer'] = url

    def set_user_agent(self, user_agent):
        self.header['User-Agent'] = user_agent
