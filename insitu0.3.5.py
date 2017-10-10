"""
INSITU - Experiment with Python and PubMed XML
Using iterparse to return information from large XML files generated by PubMed
This program will (eventually) find PubMed references "in situ" in the PubMed database.
Copyright (C) 2010 Chris Westling, Mann Library ITS, Cornell University

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

WARNING: work in progress - test on small files first!
TODO: build GUI, better exception handling, code cleanup and optimization
INFO: Chris Westling Mann Library ITS, Cornell University, Ithaca, NY
E-MAIL: cmw48@cornell.edu
"""

# import modules
from lxml import etree
import copy
import codecs
import os
import sys, traceback
import datetime  
import time
import pprint
import urllib2  # eventually, go and get the entrez eUtils file for a given search string

#declare globals up top for easy editing
calsinfile = 'allCALSpubmed100118.xml'               # VET PubMed xml filename
weillinfile = 'WeillPubMed100119.xml'                # WEILL PubMed xml filename
curbdinfile = 'allCornellIthacaWeill.xml'            # ALL CU RBD PubMed xml filename
ufrbdinfile = 'UnivofFloridaRBD.xml'                 # ALL UF RBD PubMed xml filename
vetinfile = 'allVETpubmed100118.xml'                 # VET PubMed xml filename
weillnamefile = 'allweillpeoplewithemail.xml'        # SPARQL generated xml, list of WEILL VIVO URI, name, email
calsnamefile = 'allCALSpeoplewithemail.xml'          # SPARQL generated xml, list of CALS VIVO URI, name, email
vetnamefile = 'allvetpeoplewithemail.xml'            # SPARQL generated xml, list of VET VIVO URI, name, email
emailnamefile = 'allpeopleinVIVOwithemailtest.xml'      # SPARQL generated xml, list of ALL VIVO URI, name, email
outputtextfile = 'insituTEXTOUT 0.3.5.txt'
datatextfile = 'insituDATAOUT 0.3.5.txt'
outputXMLfile = 'insituXMLOUT0.3.5xml'
exceptXMLfile = 'insituXMLEXCEPT0.3.5.xml'
nameXMLfile = 'insituNAMEXMLOUT0.3.5.xml'
# here's the 'adjustment knob' for tweaking which pubs we keep and which we send to the exceptions report
# ?dev - convert to object to avoid passing variable between four different functions
squelch = 65
# if the partialmatch switch is set to true, allows partial last name matches
# ?dev - much more useful if matching terms instead of names, remove?
partialmatch = False
numrecs = 0


class SearchAuthorName:
    ''' SearchAuthorName class: provides object ref for variables created to house the name parts from VIVO.  For each
    author in NameList, populate the following variables for the purposes of searching through the PubMed
    XML one time.  Output data based on matches via lambda statement, and clear these variables in preparation
    for the next searchauthor.
    ?dev- how to expand this class to hold persistent metrics about each searchauthor?
    ?dev- searchname is a list of lists of all search author URI, Name and Email-- leverage this for search
    author metrics, consider a separate class for one-shot placeholder object refs?'''
    searchname = []   
    lastname = ""
    lastinit = ""
    firstinit = ""
    midinit = ""
    firstname = ""
    middlename = ""
    suffix = ""
    authemail = ""
    authuri = ""
    authname = ""
    
class FoundAuthorName:
    ''' FoundAuthorName class not currently in use: added for possible speed and ease comparisons.
    This class provides object ref for variables created to house the name parts from VIVO.  For each
    author in NameList, populate the following variables for the purposes of searching through the PubMed
    XML one time.  Output data based on matches via lambda statement, and clear these variables in preparation
    for the next searchauthor.
    ?dev- how to expand this class to hold persistent metrics about each searchauthor?
    ?dev- searchname is a list of lists of all search author URI, Name and Email-- leverage this for search
    author metrics, consider a separate class for one-shot placeholder object refs?'''
    lastname = ""
    firstinit = ""
    midinit = ""
    firstname = ""
    middlename = ""
    authemail = ""
    authname = ""
    URI = ""
    authposn = ""
    

class MyError(Exception):
    ''' MyError class is for rudimentary exception and error handling.
    ?dev - expand error handling during transition to GUI?'''
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Output:
    ''' Output class provides object support for output strings.  Each output string is appended to a list,
    and then written to an output file with join().  Output files are human readable text reports detailing
    record matches.
    ?dev- enhance reports with CSV output so metrics can be easily brought into Excel, mySQL'''
    header = []
    authtext = []
    rectext = []
    datatext = [] 
    footer = []

class Counts:
    ''' Counts class provides object refs for global count variables
    ?dev- expand counts to include metrics that we want to track through the ingest and output process.
    ?dev- find and clean up all count incrementors and zero points'''
    match = 0 
    recs = 0
    auth = 0
    searchauth = 0
    allauth = 0
    score = 0
    timesthru = 0
    
class Flags:
    ''' Flags class - Originally designed for Object reference for global boolean variables
    ?dev- isMatch is deprecated, and needs to be replaced/removed.
    ?dev-  flags could be used for centralization of scoring/weighting process'''
    isMatch = False
    artHasEmail = False
    fullemailmatch = False
    partemailmatch = False
    univemailmatch = False
    firstinitmatch = False
    bothinitmatch = False
    forenamematch = False

def getScore():

    if Flags.fullemailmatch <> True:
        if Flags.partemailmatch == True:
            Counts.score += 15
        if Flags.univemailmatch == True:
            Counts.score += 20        
        if Flags.firstinitmatch == True:
            Counts.score += 20        
        if Flags.bothinitmatch == True:
            Counts.score += 25       
        if Flags.forenamematch == True:
            Counts.score += 55
    else:
        Counts.score = 99   
    #reset flag data
    Flags.partemailmatch = False
    Flags.univemailmatch = False 
    Flags.firstinitmatch = False   
    Flags.bothinitmatch = False 
    Flags.forenamematch  = False
    Flags.fullemailmatch = False

    return str(Counts.score)
    
def write_names_node(xmlout, nameentry):
    '''write_names_node function is currently responsible for taking each SearchAuthorName itemlist "nameentry" (comprised
    of [URI, Namestring, Emailstring], and appending that to Object SearchAuthorName.searchname.
    ?dev - needs to be expanded for clean XML output of "converted and augmented" searchauthor data from VIVO
    '''
    #if node is not None:
        #if node.text == 'MedlineCitation2':
        #    xmlout.write(etree.tostring("\n\n", encoding='utf-8',pretty_print=True))
        #    xmlout.write(etree.tostring(node, encoding='utf-8',pretty_print=True))
        #else:
        #     xmlout.write(etree.tostring(node, encoding='utf-8',pretty_print=True))
    #write to list of lists
    SearchAuthorName.searchname.append(nameentry)
    
def write_pubs_node(xmlout, xmlexc, squelch, node):
    '''write_pubs_node function is responsible for writing each found pub xml node to an output file via
    serialize_with_xpath() and PMrecs().  v0.3.3: expanded to allow "good" pubs to go to xmlout and "bad" pubs to go to xmlexc.
    The "knob" for tuning this output is Counts.score.
    ?dev - move the good/bad pubs "knob" to someplace where it's easier to tune
    ?dev - more generic (need a root node variable for if node.text)
    ?dev - pretty_print not quite formatting exactly how we'd like'''
    if node is not None:
        if Counts.score > squelch:
            if node.text == 'MedlineCitation2':
                xmlout.write(etree.tostring("\n\n", encoding='utf-8',pretty_print=True))
                xmlout.write(etree.tostring(node, encoding='utf-8',pretty_print=True))
            else:
                xmlout.write(etree.tostring(node, encoding='utf-8',pretty_print=True))
        else:
            if node.text == 'MedlineCitation2':
                xmlexc.write(etree.tostring("\n\n", encoding='utf-8',pretty_print=True))
                xmlexc.write(etree.tostring(node, encoding='utf-8',pretty_print=True))
            else:
                xmlexc.write(etree.tostring(node, encoding='utf-8',pretty_print=True))


def fast_iter(context, func):
    '''fast_iter function calls lambda functions from PMrecs() and getNameRecs and clears variables and elements for memory efficiency,
    increments record count, and returns nothing'''
    Counts.recs = 0
    for event, elem in context:
        func(elem)
        Counts.recs += 1
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    del context

    
def getNamerecs(namefile, namexmlout):
    '''getNameRecs function calls lambda function to parse namedata from VIVO xml, clears variables and
    elements for memory efficiency.  Returns message text to __main__ for user friendliness.
    ?dev - clean up need for unused arguments'''
    # use xpath expressions to find name matches in PubMed records data from XML
    #pred1 = 'contains(text(),"'
    #pred2 = '.=("'
    #pred3 = '")'
    xp1 = etree.XPath("child::binding")  
    xp2 = etree.XPath("child::binding/uri")
    xp3 = etree.XPath("child::binding/literal")

    context = etree.iterparse(namefile, events=('end',), tag="result")
    fast_iter(context, lambda elem: write_names_node(namexmlout, process_names(elem, xp1, xp2, xp3)))
    namerecstatus = "all names processed."
    return namerecstatus
        
def process_names(elem, xp1, xp2, xp3):
    '''process_names function - in this case the source is our VIVO SPARQL RS_XML, with top level element <Result> defining each record.
    We are applying pre-compiled XPath classes in an effort to bring each name in and populate the SearchName object.
    ?dev - can I find a way to rewrite and combine this function with serialize_with_xpath?
    '''
    newroot = etree.Element('namefile')
    result = elem
    numresult = len(elem)
    #numresult should be the number of people entries in the file
    nameitems = elem.getchildren()
    numnameitems = len(nameitems)
    #numnameitems is the number if binder elements in this result tag
    bindtag = xp1(elem)
    items = []
    for y in range(numnameitems):
        datatext = ""
        bindattrib = (bindtag[y].get("name"))
        datanode = bindtag[y].getchildren()
        dataitems = len(datanode)
        for d in range(dataitems):
            datatext = datanode[d].text
            if datatext == "":
                datatext = "NODATA"
            if datatext == " ":
                datatext = "BLANK"    
        nameentry = []
        items.append(datatext)
    nameentry = items
    return nameentry
 




def getPMrecs(infile, xmlout, xmlexc, squelch, partialmatch):
    '''getPMrecs function calls lambda function in PMrecs() and clears variables and elements for memory efficiency'''
    # use xpath expressions to find name matches in PubMed records data from XML
    pred1 = 'contains(text(),"'
    pred2 = '.=("'
    pred3 = '")'
    if partialmatch == True:
        predicatetext = pred1 + SearchAuthorName.lastname + pred3
    else:
        predicatetext = pred2 + SearchAuthorName.lastname + pred3
    #print predicatetext    
    xp1 = etree.XPath("child::Article/AuthorList/Author/LastName[" + predicatetext + "]")  
    xp2 = etree.XPath("child::PMID")
    xp3 = etree.XPath("child::Article/AuthorList")
  
    context = etree.iterparse(infile, events=('end',), tag='MedlineCitation')
    fast_iter(context, 
       lambda elem: write_pubs_node(xmlout, xmlexc, squelch, serialize_with_xpath(elem, xp1, xp2, xp3)))
  

def serialize_with_xpath(elem, xp1, xp2, xp3):
    '''serialize_with_xpath function: takes our source <PubmedArticle> element and apply two pre-compiled XPath classes.
    Return a node only when we have a last name match.
    ?dev - rewrite (and rename) this function and break up separate functionalities
    ?dev - better counts for metrics
    ?dev - what was matchstring for, other than troubleshooting?
    '''
    Counts.auth = 0
    lastmatch = -1
    initmatch = -1
    matchstring = ""
    dataresults= []
    results = []
    newroot = None
    PMIDnode = None
    vivoURLnode = None
    authlastname = []
    authforename = []
    authinitials = []
    searchnamelist = xp1(elem)
    PMIDlist = []
    PMIDlist = xp2(elem)
    Authlist = xp3(elem)
    foundauthorname = ""
    lastnamelist = []
    abstract = []
    abstractnode = None
    arttitle = []
    arttitlenode = None
    numauthors = 0
    #if last name is a match then trawl through database xml file to find matches for other name parts
    if searchnamelist:            
        Counts.score = 0
        #setup Xpath statements
        affilpath = etree.XPath("child::Article/Affiliation")
        lnamepath = etree.XPath("child::Article/AuthorList/Author/LastName")
        fnamepath = etree.XPath("child::Article/AuthorList/Author/ForeName")
        initpath = etree.XPath("child::Article/AuthorList/Author/Initials")
        #find authorparts from PubMed Authorlist
        lastnamelist = lnamepath(elem)
        initialslist = initpath(elem)
        forenamelist = fnamepath(elem)
        numauthors = len(lastnamelist)
        numforename = len(forenamelist)
        numinit = len(initialslist)
        affil = affilpath(elem)
        affiltext = affil[0].text.encode('utf-8') 
        #pull email from affiliation string
        emailteststartpos = affiltext.rfind(" ")
        emailstring = affiltext[emailteststartpos :].strip()
        atpos = emailstring.find("@")
        if atpos > 0:
            # the affiliation string has an email at the end
            Flags.artHasEmail = True
            # when we write this pub to an XML file, break out this string as <Affiliation Email>
            # if email exists in VIVO record, look at email first
            if SearchAuthorName.authemail <> "":
                # use lowercase for both strings to ensure good match (some PubMed records use all caps = no match)
                # full email match
                if emailstring.lower() == SearchAuthorName.authemail.lower():
                     #Counts.score += 100
                     # "full email match"
                     Flags.fullemailmatch = True
                     Flags.isMatch = True
                else:  
                    # look for partial email match 
                    emailfirstthree = emailstring[:3].lower()
                    SearchAuthorName.lastinit = SearchAuthorName.lastname[:1]
                    threeinit = SearchAuthorName.firstinit + SearchAuthorName.midinit + SearchAuthorName.lastinit
                    threeinitstring = threeinit.lower()
                    #print PMIDlist[0].text.encode('utf-8') + " : " + SearchAuthorName.authemail + " : " + emailstring
                    if emailstring[-11:].lower() == "cornell.edu":
                        Flags.univemailmatch = True
                        #Counts.score += 5
                        # print "partial email match: 5 for @cornell"
                        if emailfirstthree == threeinitstring:
                            Flags.partemailmatch = True
                            Flags.isMatch = True
                            #Counts.score += 30
                            #print "partial email match: 15 for initials match first 3 email"
                        else:  
                            pass                
                    else:
                        pass
            else:
                # no email in VIVO record
                pass
        else:
            # no email found in PubMed affil string
            Flags.artHasEmail = False
        atpos = -1

        #check for a full initial match
        #assume that each pub has (numauthors) authors, based on the premise that LastName is always present
        #COUNTS: "This pub has " + str(numauthors) + " authors."
        #cycle through authors starting with author[1] to find match
        for m in range(numauthors):
            if SearchAuthorName.lastname == lastnamelist[m].text:      # is this the author we got a lastname match on?
                lastmatch = m                                          # set lastmatch flag to remember which one
                #since initials or forename tags may not appear in some PubMed records, test and set values
                if numauthors <> numforename:
                    if numauthors <> numinit:               # if both forename and initials are missing
                        forename = "missing forename element!"
                        initials = "missing initial element!"
                    else:                                      # if only forename is missing
                        forename = "missing forename element!"
                        initials = initialslist[m].text.encode('utf-8')    
                elif numauthors <> numinit:                     # if initials is missing
                    forename = forenamelist[m].text.encode('utf-8')
                    initials = "missing initial element!"
                else:
                    forename = forenamelist[m].text.encode('utf-8')
                    initials = initialslist[m].text.encode('utf-8')

                #print initialslist[lastmatch].text + ":" + SearchAuthorName.firstinit + SearchAuthorName.midinit
                #print initials + ":" + SearchAuthorName.firstinit + SearchAuthorName.midinit
                fnamelen = len(SearchAuthorName.firstname)
                shortforename = forename[:fnamelen]
                if shortforename == SearchAuthorName.firstname:
                    Flags.forenamematch = True
                    #Counts.score += 30
                    #print "30 for forename"
                    Flags.isMatch = True
                    initmatch = m
                elif initials.strip() == SearchAuthorName.firstinit + SearchAuthorName.midinit:         #
                    initmatch = m
                    Flags.bothinitmatch = True
                    #Counts.score += 30
                    #print "30 for FM"
                    Flags.isMatch = True
                elif initials.strip() == SearchAuthorName.firstinit:
                    initmatch = m
                    Flags.firstinitmatch = True
                    #Counts.score += 20                #print "20 for F"
                    Flags.isMatch = True
                else:
                    Flags.isMatch = False
            else:
                # not the author we wanted
                # grab other author data here
                pass
            
    else:
        matchstring = "NO MATCH"
        #not a last name match
        lastmatch = -1
        found = False
        
    if Flags.isMatch == True:

        Counts.match += 1
        atpos = -1
        #print str(Counts.match)
        matchstring = "MATCH"

        # if we are going to write this pub to GOOD or BAD, land here.
        # setup XML output
        # ?dev - seems like this could be managed in a different function, as long as we build class objects for variables to be saved
        # ?dev - this root element name needs to be a variable to allow renaming when not Medline

        abstractpath = etree.XPath("child::Article/Abstract/AbstractText")
        journalabbrpath = etree.XPath("child::Article/Journal/ISOAbbreviation")
        journalyearpath = etree.XPath("child::Article/Journal/JournalIssue/PubDate/Year")
        arttitlepath = etree.XPath("child::Article/ArticleTitle")
        abstract = abstractpath(elem)
        journalabbr = journalabbrpath(elem)
        arttitle = arttitlepath(elem)
        journalyear = journalyearpath(elem)
        if len(journalyear) <> 0:
            journalyeartext = journalyear[0].text
        else:
            journalyeartext = "NO YEAR"
        newroot = etree.Element('MedlineCitation2')
        articlenode = etree.SubElement(newroot, 'Article')
        affilnode = etree.SubElement(articlenode, 'Affiliation')
        affilnode.text = affiltext.decode('utf-8')
        if Flags.artHasEmail == True:
            affilemailnode = etree.SubElement(articlenode, 'AffiliationEmail')
            affilemailnode.text = emailstring.encode('utf-8')
        else:
            #no email string
            pass
        
        PMIDnode = etree.SubElement(articlenode, 'PMID')
        PMIDnode.text = PMIDlist[0].text.encode('utf-8')
        #print "PMID" + PMIDnode.text
        abstractnode = etree.SubElement(articlenode, 'Abstract')
        if len(abstract) <> 0: 
            abstracttext = abstract[0].text.encode('utf-8')
        else:
            abstracttext = "NO ABSTRACT AVAILABLE"
        abstractnode.text = abstracttext.decode('utf-8')    
        journalnode = etree.SubElement(articlenode, 'Journal')
        journaldatenode =  etree.SubElement(journalnode, 'PubDate') 
        journalyearnode =  etree.SubElement(journaldatenode, 'Year')
        journalabbrnode = etree.SubElement(journalnode, 'ISOAbbreviation')
        if len(journalabbr) <> 0: 
            journalabbrtext = journalabbr[0].text.encode('utf-8')
        else:
            journalabbrtext = "NO JOURNAL ABBR. AVAILABLE"
        journalabbrnode.text = journalabbrtext.decode('utf-8')
        arttitlenode = etree.SubElement(articlenode, 'ArticleTitle')
        if len(arttitle) <> 0:
            arttitletext = arttitle[0].text.encode('utf-8')
        else:
            arttitletext = "NO ARTICLE TITLE AVAILABLE"
        arttitlenode.text = arttitletext.decode('utf-8')    
        authorlistnode = etree.SubElement(articlenode, 'FoundAuthorList')
        for c in Authlist:
            authornode = etree.SubElement(authorlistnode, 'FoundAuthor')
            vivoURInode = etree.SubElement(authornode, 'vivoURI')       
            lastnode = etree.SubElement(authornode, 'LastName')
            forenamenode = etree.SubElement(authornode, 'ForeName')
            initnode = etree.SubElement(authornode, 'Initials')
            emailnode = etree.SubElement(authornode, 'Email')
            authposnode = etree.SubElement(authornode, 'AuthorPosition')
            scorenode = etree.SubElement(authornode, 'MatchProb')
            Counts.auth += 1
            vivoURInode.text = SearchAuthorName.authuri.encode('utf-8')           
            lastnode.text = SearchAuthorName.lastname.encode('utf-8')
            forenamenode.text = forename.decode('utf-8')
            initnode.text = initials.encode('utf-8')
            emailnode.text = SearchAuthorName.authemail.encode('utf-8')    
            authposnode.text = str(initmatch+1).encode('utf-8')
            journalyearnode.text = journalyeartext
            scorenode.text = getScore()
    
            #newroot.append((c))      #tacks the full author list onto the xml  

        #for x in range(len(lastnamelist)):
        #print ('%s. %s,%s' % (x, lastnamelist[x].text, initials))
        #print "matching author is number " + str(initmatch)
        found = True
        foundauthorname = ("%s. %s, %s (%s)" % (initmatch+1,  SearchAuthorName.lastname, initials, forename))
        results.append("%s %s (%s%s) %s (%s percent)\n" % (PMIDnode.text, foundauthorname, SearchAuthorName.firstinit, SearchAuthorName.midinit, matchstring, Counts.score))
        dataresults.append("%s, %s, %s, %s, %s, %s, %s, %s, %s.\n" % (PMIDnode.text, str(initmatch+1), SearchAuthorName.lastname, SearchAuthorName.firstinit, SearchAuthorName.midinit, SearchAuthorName.firstname, SearchAuthorName.middlename, journalyeartext, Counts.score))
    else: 
        # look for ways to doublecheck process here
        pass
    # COUNTS?  how many hits did we get?
    Output.rectext.append('\n'.join(results))                   # write results data one line at a time
    Output.datatext.append('\n'.join(dataresults))                   # write results data one line at a time
    Flags.isMatch = False
    Flags.artHasEmail = False
    Flags.emailmatch = False
    return newroot


    
    
def getNameParts (curnameitems):
    ''' getNameParts() function takes a name string from SearchAuthorName list via main() and breaks it into
    component name parts and URI string, and stores it in SearchAuthorName one-shot name part references

    dev?  add hyphen in forename functionality: initials ZH when forename is Zhang-Hu

    '''
    #declarations
    uristring = ""
    templastname = ""
    newfirstname = ""
    newlastname = ""
    remainingnamestring = ""
    firstandlast = ""
    currentURI = ""
    currentdept = ""
    currentdeptname = ""
    suffix = ""
    authname = []
    curnameparts = len(curnameitems)
    uristring = curnameitems[0]
    currentname = curnameitems[1]
    if curnameparts > 2:
        emailstring = curnameitems[2]
    else:
        emailstring = ""
    # begin deconstruction
    #print currentname
    lenfullname = (len(currentname))                       # get length of fullname string
    commapos = currentname.find(",")                       #look for comma postion in string, everything to next comma is lastname
    newlastnamestring = currentname[:commapos]                   #get last name
    print newlastnamestring
    newlastname = newlastnamestring.encode('utf-8')
    
    #spaceinlastname = newlastname.find(" ")
    #if spaceinlastname <> 0:
        #print "SPACE IN LASTNAME"
    #hypheninlastname = newlastname.find("-")
    #if hypheninlastname <> 0:
        #print "HYPHEN IN LASTNAME"        
    
    remainingnamestring = (currentname[(commapos+1):])      #prep remaining string
    firstandlast = remainingnamestring.strip()
    #search for comma in remaining name string, pull suffix from end
    sufcommapos = firstandlast.rfind(",")                       #look for comma postion in string
    if sufcommapos <> -1:                                       #suffix found!
        newsuffix = (firstandlast[(sufcommapos+1):])
        suffix = newsuffix.strip()
        firstandlast = firstandlast[:sufcommapos]               #modify firstandlast to exclude suffix
    # resume breakdown of first and middle
    spacepos = firstandlast.find(" ")                      #look for space in remaining name string
    if spacepos == -1:
        #no additional space found, take entire string from 0 to lenfirstandlast
        newfirstname = firstandlast
        newmiddlename = ""
    else:
        #space was found, strip first name out
        newfirstname = firstandlast[:spacepos]
        remainingmidname = firstandlast[spacepos:]
        #check to see if we can get another middle name and test for suffix
        midorsuffix = remainingmidname.strip()
        midspacepos = midorsuffix.rfind(" ")
        if midspacepos == -1:                                 #expected, means no second mid or suffix, process for period
            newmidname = midorsuffix
            midperiodpos = newmidname.rfind(".")
            if midperiodpos == -1:                         #period not found
                newmiddlename = newmidname
            else:
                newmiddlename = newmidname[:midperiodpos]  #period found, strip it
        else:                                                 #surprise, second middle name or suffix.  pull first middle and process second
            newmiddlename = midorsuffix[:midspacepos]
            remainingmid = midorsuffix[midspacepos:]
            newsecondmid = remainingmid.strip()
            secondmidperiodpos = newsecondmid.rfind(".")
            if secondmidperiodpos == -1:                         #period not found
                secondmiddlename = newsecondmid
            else:
                secondmiddlename = newsecondmid[:secondmidperiodpos]  #period found, strip it

        #all done name processing, clean up, find initial strings, create return list  

    newfirstinitial = newfirstname[0]
    if newmiddlename <> "":
        newmiddleinitial = newmiddlename[0]
    else:
        newmiddleinitial = ""
    Output.authtext.append('VIVO uri: %s\n' % (uristring))
    #rectext = rectext + ('Dept uri: %s\n' % (currentdept))
    #rectext = rectext + ('Dept name: %s\n' % (currentdeptname))
    Output.authtext.append('name variants for %s\n' % (currentname))
    Output.authtext.append('%s %s\n' % (newlastname, newfirstinitial))
    Output.authtext.append('%s %s%s\n' % (newlastname, newfirstinitial, newmiddleinitial))
    Output.authtext.append('%s %s\n' % (newlastname, newfirstname))
    Output.authtext.append('%s %s %s\n' % (newlastname, newfirstname, newmiddlename))
    #load function parameters
    SearchAuthorName.lastname = newlastname.strip()
    SearchAuthorName.firstinit = newfirstinitial.strip()
    SearchAuthorName.midinit = newmiddleinitial.strip()
    SearchAuthorName.firstname = newfirstname.strip()
    SearchAuthorName.middlename = newmiddlename.strip()
    SearchAuthorName.authuri = uristring.strip()
    SearchAuthorName.suffix = suffix.strip()
    SearchAuthorName.authemail = emailstring.strip()
    SearchAuthorName.authname = [SearchAuthorName.lastname, SearchAuthorName.firstinit, SearchAuthorName.midinit, SearchAuthorName.firstname, SearchAuthorName.middlename, SearchAuthorName.suffix, SearchAuthorName.authuri, SearchAuthorName.authemail]
    return SearchAuthorName.authname

def cmdLineUINameFile():
    ''' cmdLineUINameFile() function provides command line options for NameFile xml ingest
    pulls from global variables at the top
    provides manual entry choice to enter a single name
    '''
    
    print "Type your choice for NAMELIST and press ENTER: "
    print "1 - CALS"
    print "2 - VET"
    print "3 - WEILL"
    print "4 - ALL VIVO FACULTY"
    print "5 - ALL VIVO EMPLOYEES"
    print "6 - ALL VIVO WITH EMAIL"
    print "9 - MANUAL ENTRY"
    namelistchoice = raw_input (">>")

    if namelistchoice == "1":
        namefile = calsnamefile
    elif namelistchoice == "2":
        namefile = vetnamefile
    elif namelistchoice == "3":
        namefile = weillnamefile
    elif namelistchoice == "4":
        namefile = rbnnamefile
    elif namelistchoice == "6":
        namefile = emailnamefile
    elif namelistchoice == "9":
        namefile = "from manual entry"
    return namefile

def cmdLineUIInFile():
    ''' cmdLineUIInFile() function provides command line options for Infile (pubs list) xml ingest
    pulls from global variables at the top
    provides manual entry choice to enter a single file name
    '''
    print "Type your choice for PubMed source file and press ENTER: "
    print "a - CALS"
    print "b - VET"
    print "c - WEILL"
    print "d - ALL CORNELL PUBS (RBD)"
    print "e - ALL UF VIVO PUBS (RBD)"
    print "z - MANUAL ENTRY"
    infilechoice = raw_input (">>")

    if infilechoice == "a":
        infile = calsinfile
    elif infilechoice == "b":
        infile = vetinfile
    elif infilechoice == "c":
        infile = weillinfile
    elif infilechoice == "d":
        infile = curbdinfile
    elif infilechoice == "d":
        infile = ufrbdinfile
    elif infilechoice == "z":
        infile = raw_input ("enter a valid PubMed input file")
    else:
        pass
    return infile

# main begin---
def main():
    ''' main() function has the following responsibilities:
    a) get number of records in pubmed set
    b) return list of names and URIs from namefile using target parser (longnamelist[])
    c) concatenate name and URI and append to namelist[]
    d) open output file for text output and print header, timestamp start
    e) iterate over namelist
       i) call getnameparts function to process and return author name parts
       ii) call getPMrecs to iterate through pubsfile and return name matches
    f) output data to text files and timestamp finish
    g) close output files'''
    
    # declare local variables 
    singlename = -1
    partialmatch = False                         #accept partial lastname matches?
    results = []                                #list/string for output
    numnames = 0
    numVIVOnames = 0
    authorname = []
    finduri = ""
    NameList = []
    infile = ""
    namefile = ""
    startdate = ""
    startdate = str(datetime.datetime.today())
    namefile = cmdLineUINameFile()
    infile = cmdLineUIInFile()

    # input section - get data from         
    if namefile <> "from manual entry":

        #use target parsing to return a list of all names from the VIVO file, so we can get a count
        namexmlout = open(nameXMLfile, 'w')
        namexmlout.write('<?xml version="1.0"?>')
        namerecstatus = getNamerecs(namefile, namexmlout)
        print namerecstatus
        numVIVOnames = len(SearchAuthorName.searchname)
        print "total records processed: " + str(numVIVOnames)

                
    else:

        lastnameinput = raw_input ("enter a name: Lastname, Firstname Middlename")
        VIVOuriinput = raw_input ("enter a valid VIVO uri for this name")
        emailinput = raw_input ("enter a valid email for this name")
        NameList.append(VIVOuriinput + ", " + lastnameinput)
        numVIVOnames = 1
   
        #raise MyError("Bad input.")
        
    # use Xpath to return a list of all titles to give us total number of records in the PUBMED file
    ''' note: this is just for the purposes of the header file - if performance related issues arise, then remove'''
    tree = etree.parse(infile)
    title = tree.xpath('/PubmedArticleSet/PubmedArticle/MedlineCitation/PMID')
    numrecs = len(title)
    title = []
    tree = []

    # header for text output file    
    print ('indexing %s names in %s...' % (numVIVOnames, infile))
    Output.header.append('INSITU Publications Indexing Tool Results - Date: %s \n' % (startdate))
    Output.header.append ('indexing a total of %s names in %s\n' % (numVIVOnames, namefile))
    out = open(outputtextfile, 'w')                              # write to file
    dataout = open(datatextfile, 'w')                              # write to file
    out.write('\n'.join(Output.header))             # write output header at top of report
    out.write('\n ------------------------------------------------------------------------------------ \n\n')
    xmlout = open(outputXMLfile, 'w')
    xmlout.write('<?xml version="1.0"?>')
    xmlexc = open(exceptXMLfile, 'w')
    xmlexc.write('<?xml version="1.0"?>')

    # for all SearchNames stored in SearchAuthorNames, iterate over the pubs comparison getPMrecs 

    for a in range(numVIVOnames):  #change value for testing smaller sets, numVIVOnames for full load
        curnameitems = SearchAuthorName.searchname[a]
        Output.authtext.append('searching %s for %s: \n\n' % (infile, curnameitems[1]))
        authorname = getNameParts(curnameitems)
        print ('person %s of %s: %s %s%s...  analyzing %s records' % (str(a), str(numVIVOnames),SearchAuthorName.lastname, SearchAuthorName.firstinit, SearchAuthorName.midinit, numrecs))
        PMStrings = getPMrecs(infile, xmlout, xmlexc, squelch, partialmatch)
        numresults = Counts.match
        # prepare output string
        out.write (''.join(Output.authtext))
        Output.rectext.append('INSITU returned %s results on keyword %s in tag LastName\n' % (Counts.match, SearchAuthorName.lastname))
        Output.rectext.append('out of a total %s records in %s: \n\n' % (Counts.recs, infile))
        Counts.match = 0
        out.write (''.join(Output.rectext))
        # write results data one line at a time
        dataout.write (''.join(Output.datatext))
        out.write('\n ------------------------------------------------------------------------------------ \n\n')
        Output.authtext = []
        Output.rectext = []
        Output.datatext = []
        PMStrings = [] 
    #all done?  timestamp file with stop time
    finishdate = ""
    finishdate = str(datetime.datetime.today())       
    Output.footer.append("process ended at" + finishdate)
    out.write('%s \n' % (Output.footer))                   # write output footer at bottom of report
    out.close()
    xmlout.close()
    xmlexc.close()
    namexmlout.close()
    dataout.close()
    raise MyError("There aren't any more records to look at.")
                         
if __name__=="__main__":
    try:
        main()
    except AttributeError:
        print "Hey, another attribute error!"
        #print "here's the current value of foundlastname: " + foundlastname       
        #print "here's the current value of foundforename: " + foundforename
        traceback.print_exc()
        print "I'm not exactly sure what to do."
    except MyError as e:
        print "Terminating process.", e.value
    else:        
        print 'An unhandled exception occured!'
        traceback.print_exc()
    finally: 
        p = raw_input ("press ENTER to continue:")
