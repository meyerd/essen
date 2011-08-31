#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys, cStringIO, re
from BeautifulSoup import BeautifulSoup
from WebCursor import WebCursor
from pdfminer.pdfparser import PDFParser, PDFDocument
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter, \
        process_pdf
from pdfminer.cmapdb import CMapDB
from pdfminer.layout import LAParams
import datetime, pickle, textwrap, argparse
import os.path


consolewidth = 79

loske_base_url = u"http://www.betriebsrestaurant-gmbh.de/"
loske_main = u"index.php?id=91"
ausgabe_mittagskarte = u"http://www.protutti.com/firmen/M/Ausgabe/upfile/Wochenkarte.pdf"
mensa_garching_rss = \
        u"http://geigerma.de/mensa/mensa.xml.php?mensa=mensa_garching"
config_file = os.path.expanduser(os.path.join(u"~", u".essen"))

class bcolors:
    HEADER = ''
    OKBLUE = ''
    OKGREEN = ''
    WARNING = ''
    FAIL = ''
    ENDC = ''

    import platform
    if platform.system() == u'Linux':
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''

TYPE_AUS, TYPE_IPP, TYPE_MENSA = range(3)

config = {}
config["last_update_ipp"] = datetime.date(1,1,1)
config["last_update_mensa"] = datetime.date(1,1,1)
config["last_update_aus"] = datetime.date(1,1,1)
config["meals"] = {}

def save_config(filename):
    fp = open(filename, "w")
    if fp:
        pickle.dump(config, fp)
    fp.close()

def load_config(filename):
    global config
    fp = open(filename, "r")
    if fp:
        config = pickle.load(fp)
    fp.close()

def dump_all_meals():
    dates = sorted(config["meals"].keys())
    for d in dates:
        print u"%s:" % (str(d)) 
        for m in config["meals"][d]:
            t, s = m
            sb = u'\n       '.join(textwrap.wrap(s, consolewidth-7))
            if t is TYPE_IPP:
                print " IPP",
            elif t is TYPE_AUS:
                print " AUS",
            else:
                print " MEN",
            print " - %s" % (sb.encode(sys.stdout.encoding, 'replace'))

def dump_one_day_meals(date):
    dates = config["meals"].keys()
    for d in dates:
        if d == date:
            print u"%s:" % (str(d)) 
            for m in config["meals"][d]:
                t, s = m
                sb = u'\n       '.join(textwrap.wrap(s, consolewidth-7))
                if t is TYPE_IPP:
                    print " IPP",
                elif t is TYPE_AUS:
                    print " AUS",
                else:
                    print " MEN",
                print " - %s" % (sb.encode(sys.stdout.encoding, 'replace'))


def show_last_update():
    print u"ipp: %s, mensa: %s" % (str(config["last_update_ipp"]),
                                   str(config["last_update_mensa"]))

def remove_older(when):
    for k in config["meals"].keys():
        if k < when:
            del config["meals"][k]

def parse_loske_pdf(pdf):
    stripcid_re = re.compile(u"\(cid:.*?\)")
    newline_heuristic_re = re.compile(u"Montag, den |Dienstag, den |Mittwoch" \
                                      u", den |Donnerstag, den |Freitag, den ",
                                      re.IGNORECASE)
    bnw_endheuristic_re = re.compile(u"B\.n\.W\.=Beilage.*")
    dow_beginheuristic_re = re.compile(u".*?Montag, den ", re.IGNORECASE)
    meal_detect_re = re.compile(u"(\d\.)(.*?)(\d).(\d\d)")
    #meal_detect_re = re.compile(u"(\d\.)(\D)")
    date_re = re.compile(u"(\d{1,2})\.(\d{1,2})\.(\d{1,4})(.*)")

    rsrcmgr = PDFResourceManager()
    outtxt = cStringIO.StringIO()
    device = TextConverter(rsrcmgr, outtxt)
    
    pdfp = PDFParser(cStringIO.StringIO(pdf))
    doc = PDFDocument()
    pdfp.set_document(doc)
    doc.set_parser(pdfp)
    doc.initialize("")

    if not doc.is_extractable:
        print >>sys.stderr, u"PDF Document not extractable"
        sys.exit(1)

    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for (pageno,page) in enumerate(doc.get_pages()):
        #print pageno
        interpreter.process_page(page)
    
    device.close()

    fulltext = outtxt.getvalue().decode('utf-8', 'replace')
    fulltext = stripcid_re.sub(u'', fulltext)
    fulltext = dow_beginheuristic_re.sub(u'', fulltext)
    fulltext = bnw_endheuristic_re.sub(u'', fulltext)
    fulltext = newline_heuristic_re.sub(u'\n', fulltext)

    lines = fulltext.split(u'\n')

    now = datetime.date(1,1,1)

    for line in lines:
        ret = date_re.search(line)
        if ret:
            day, month, year, meals = ret.groups()
            now = datetime.date(int(year), int(month), int(day))
            meals = meal_detect_re.sub(ur'\n\2(\3,\4 €)', meals).strip()
            for m in meals.split(u'\n'):
                try:
                    tmp = config["meals"][now]
                    config["meals"][now].append((TYPE_IPP, m))
                except KeyError, e:
                    config["meals"][now] = [(TYPE_IPP, m)]

def get_new_loske():
    wc = WebCursor();
    loske_html = wc.get(loske_base_url+loske_main)
    if loske_html == "":
        print >>sys.stderr, u"Could not download" , loske_base_url+loske_main
        sys.exit(1)
    soup = BeautifulSoup(loske_html)
    # print soup.prettify()
    tds = soup.findAll(u'td', attrs={u'class' : u'csc-uploads-fileName'})
    thisweek_url = ""
    if len(tds) < 2:
        print >>sys.stderr, u"Parse html error"
        sys.exit(1)
    alla = tds[0].findAll('a')
    if len(alla) < 1:
        print >>sys.stderr, u"Parse html error"
        sys.exit(1)
    thisweek_url = alla[0]['href']
    if thisweek_url == "":
        print >>sys.stderr, u"Parse html error"
        sys.exit(1)

    pdf = wc.get(loske_base_url+thisweek_url)
    if pdf == "":
        print >>sys.stderr, u"Could not download", loske_base_url+thisweek_url
        sys.exit(1)
    parse_loske_pdf(pdf)

    nextweek_url = ""
    alla = tds[1].findAll('a')
    if len(alla) < 1:
        print >>sys.stderr, u"Parse html error"
        sys.exit(1)
    nextweek_url = alla[0]['href']
    if thisweek_url == "":
        print >>sys.stderr, u"Parse html error"
        sys.exit(1)
    
    pdf = wc.get(loske_base_url+nextweek_url)
    if pdf == "":
        print >>sys.stderr, u"Could not download", loske_base_url+nextweek_url
        sys.exit(1)
    parse_loske_pdf(pdf)

    config["last_update_ipp"] = datetime.date.today()

def dow_to_int(dow):
    montag_re = re.compile(u"Montag", re.IGNORECASE)
    dienstag_re = re.compile(u"Dienstag", re.IGNORECASE)
    mittwoch_re = re.compile(u"Mittwoch", re.IGNORECASE)
    donnerstag_re = re.compile(u"Donnerstag", re.IGNORECASE)
    freitag_re = re.compile(u"Freitag", re.IGNORECASE)

    ret = montag_re.search(dow)
    if ret:
        return 0
    ret = dienstag_re.search(dow)
    if ret:
        return 1
    ret = mittwoch_re.search(dow)
    if ret:
        return 2
    ret = donnerstag_re.search(dow)
    if ret:
        return 3
    ret = freitag_re.search(dow)
    if ret:
        return 4

    return -1

def parse_ausgabe_pdf(pdf):
    stripcid_re = re.compile(u"\(cid:.*?\)")
    newline_heuristic_re = re.compile(u"(?:\u20ac)?(Montag|Dienstag|Mittwoch" \
                                      u"|Donnerstag|Freitag)",
                                      re.IGNORECASE)
    guapp_endheuristic_re = re.compile(u"Guten Appetit.*")
    dow_beginheuristic_re = re.compile(u".*?(Montag)", re.IGNORECASE)
    meal_detect_re = re.compile(u" *?(\d+),(\d\d).*?(?:\*\d+,\d\d€?)")
    #meal_detect_re = re.compile(u"(\d\.)(\D)")
    date_re = re.compile(u"(Montag|Dienstag|Mittwoch|Donnerstag|Freitag)(.*)")
    whitespace_re = re.compile(u"^[ \t\n]*$")

    rsrcmgr = PDFResourceManager()
    outtxt = cStringIO.StringIO()
    device = TextConverter(rsrcmgr, outtxt)
    
    pdfp = PDFParser(cStringIO.StringIO(pdf))
    doc = PDFDocument()
    pdfp.set_document(doc)
    doc.set_parser(pdfp)
    doc.initialize("")

    if not doc.is_extractable:
        print >>sys.stderr, u"PDF Document not extractable"
        sys.exit(1)

    interpreter = PDFPageInterpreter(rsrcmgr, device)
    for (pageno,page) in enumerate(doc.get_pages()):
        #print pageno
        interpreter.process_page(page)
    
    device.close()

    fulltext = outtxt.getvalue().decode('utf-8', 'replace')
    #fulltext = stripcid_re.sub(u'', fulltext)
    fulltext = dow_beginheuristic_re.sub(u'\g<1>', fulltext)
    fulltext = guapp_endheuristic_re.sub(u'', fulltext)
    fulltext = newline_heuristic_re.sub(u'\n\g<1>', fulltext)

    lines = fulltext.split(u'\n')

    now = datetime.date(1,1,1)

    for line in lines:
        ret = date_re.search(line)
        if ret:
            dow, meals = ret.groups()
            dow = dow_to_int(dow)
            if dow < 0:
                continue
            now_dow = datetime.date.today().weekday()
            dow_diff = dow - now_dow
            now = datetime.date.today() + datetime.timedelta(dow_diff)
            meals = meal_detect_re.sub(ur' (\1,\2 €)\n', meals).strip()
            for m in meals.split(u'\n'):
                try:
                    tmp = config["meals"][now]
                    config["meals"][now].append((TYPE_AUS, m))
                except KeyError, e:
                    config["meals"][now] = [(TYPE_AUS, m)]

def get_new_ausgabe():
    wc = WebCursor();

    pdf = wc.get(ausgabe_mittagskarte)
    if pdf == "":
        print >>sys.stderr, u"Could not download", ausgabe_mittagskarte
        sys.exit(1)
    parse_ausgabe_pdf(pdf)

    config["last_update_aus"] = datetime.date.today()

def get_new_mensa():
    date_re = re.compile(u".., (\d{1,2})\.(\d{1,2})\.(\d{1,4})")
    desc_nl_re = re.compile(u"(?:(.*?)(?:<br>))*")
    desc_nl_rep_re = re.compile(u"<br>")

    wc = WebCursor();
    mensa_html = wc.get(mensa_garching_rss)
    if mensa_html == "":
        print >>sys.stderr, u"Could not download" , mensa_garching_rss
        sys.exit(1)
    soup = BeautifulSoup(mensa_html)
    
    items = soup.findAll(u"item")
    for i in items:
        title = i.findAll(u"title")
        if len(title) < 1:
            print >>sys.stderr, u"Rss parse error."
            sys.exit(1)
        ret = date_re.search(title[0].text)
        if not ret:
            print >>sys.stderr, u"Rss date parse error."
            sys.exit(1)
        day, month, year = ret.groups()
        now = datetime.date(int(year), int(month), int(day))
        
        desc = i.findAll(u"description")
        if len(desc) < 1:
            print >>sys.stderr, u"Rss parse error."
            sys.exit(1)
        #if not ret:
        #    print >>sys.stderr, u"Rss description parse error."
        #    sys.exit(1)
        #print ret.groups()
        tx = desc_nl_rep_re.sub(u'\n', desc[0].text)
        tx = tx.split(u'\n')
        for m in tx:
            m = m.lstrip(u"- ")
            m = m.strip()
            if m != u"":
                try:
                    tmp = config["meals"][now]
                    config["meals"][now].append((TYPE_MENSA, m))
                except KeyError, e:
                    config["meals"][now] = [(TYPE_MENSA, m)]
    config["last_update_mensa"] = datetime.date.today()

def update_all():
    print >>sys.stderr, u"Updating..."
    config["meals"] = {}
    get_new_mensa()
    get_new_loske()
    get_new_ausgabe()
    save_config(config_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=textwrap.dedent('''\
    Command line interface to the Mensa, Max-Planck-Institute Garching
     and Ausgabe Schwabing Mealplans.
        DATE can be a date in german format (e.g. 14.04.2011, 4.2.2010, ...)
        DATE can also be a day and month (e.g. 14.4.)
        DATE can also be only a day, month and year will be the current year 
              and month
        You can also specify a german weekday (e.g. Montag or mo)
        If date is 'all' then all saved meals are displayed, 'morgen' displays
              the meal of the next day
'''),
            epilog='Warning! Extremely hacky, it will most likely break!')

    def is_a_date(string):
        date_re = re.compile(u'(\d{1,2})\.(\d{1,2})\.(\d{1,4})')
        shortdate_re = re.compile(u'(\d{1,2})\.(\d{1,2})')
        day_re = re.compile(u'(mo|di|mi|do|fr|sa|so|Montag|Dienstag|Mittwoch' \
                            u'|Donnerstag|Freitag|Samstag|Sonntag)',
                            re.IGNORECASE)
        daynum_re = re.compile(u'(\d{1,2})')
        all_re = re.compile(u'all', re.IGNORECASE)
        morgen_re = re.compile(u'morgen', re.IGNORECASE)
        matched = False
        ret = None    

        r = date_re.search(string)
        if r:
            day, month, year = r.groups()
            ret = datetime.date(int(year), int(month), int(day))
            return ret

        r = shortdate_re.search(string)
        if r:
            day, month = r.groups()
            ret = datetime.date(datetime.date.today().year,
                                int(month), int(day))
            return ret

        r = daynum_re.search(string)
        if r:
            day = r.groups()[0]
            ret = datetime.date(datetime.date.today().year,
                                datetime.date.today().month, int(day))
            return ret
        
        r = all_re.search(string)
        if r:
            ret = "all"
            return ret

        r = morgen_re.search(string)
        if r:
            ret = datetime.date.today() + datetime.timedelta(1)
            return ret

        r = day_re.search(string)
        if r:
            wd = r.groups()[0].lower()
            dowint = 0
            if wd[:2] == "mo":
                dowint = 0
            elif wd[:2] == "di":
                dowint = 1
            elif wd[:2] == "mi":
                dowint = 2
            elif wd[:2] == "do":
                dowint = 3
            elif wd[:2] == "fr":
                dowint = 4
            elif wd[:2] == "sa":
                dowint = 5
            else:
                dowint = 6

            ret = datetime.date.today()
            for i in range(7):
                if ret.weekday() == dowint:
                    break
                else:
                    ret += datetime.timedelta(days=1)
            return ret
                
        if not ret:
            msg = u"%s is not a valid date, day of week (german) or 'all'" \
                    % (string,)
            raise argparse.ArgumentTypeError(msg)

        return ret

    parser.add_argument('-u', action='store_true', default=False,
                        help='Update the database')
    parser.add_argument('date', 
            metavar='DATE', 
            nargs='?',
            type=is_a_date,
            help='Lookup meals for specific date')

    opts = parser.parse_args()

    if opts.u:
        update_all()

    if os.path.isfile(config_file):
        load_config(config_file)
    else:
        print >>sys.stderr, bcolors.FAIL + "No configfile found. " \
                "You may want to run an update." + bcolors.ENDC
        sys.exit(1)
    
    if datetime.date.today() - config["last_update_mensa"] > \
       datetime.timedelta(days=6) or \
       datetime.date.today() - config["last_update_ipp"] > \
       datetime.timedelta(days=6) or \
       datetime.date.today() - config["last_update_aus"] > \
       datetime.timedelta(days=6):
        print >>sys.stderr, bcolors.WARNING + "Last update was more than 6 " \
                "days ago." + bcolors.ENDC
        update_all()
    
    if opts.date is None:
        if datetime.date.today().weekday() == 2:
            print bcolors.HEADER + "Wednesday: IPP: CHEESEBURGERS!!" \
                    + bcolors.ENDC
        dump_one_day_meals(datetime.date.today())
        sys.exit(0)

    if opts.date == "all":
        dump_all_meals()
        sys.exit(0)

    if opts.date.weekday() == 2:
        print bcolors.HEADER + "Wednesday: IPP: CHEESEBURGERS!!" + bcolors.ENDC

    dump_one_day_meals(opts.date)
