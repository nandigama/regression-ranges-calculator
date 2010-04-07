#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
#
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
# Murali Krishna Nandigama
# 
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
import  MySQLdb, sys, os, json, re, datetime, urllib
from optparse import OptionParser

class RegressionRangeCalculation:
  
  def remote_connection(self, rhost, rport, rdb, ruser, rpassword, bzusername, bzpasswd):
    
    self.rhost  =  rhost
    self.rport  =  int(rport)
    self.rdb  =  rdb
    self.ruser  =  ruser
    self.rpasswd  =  rpassword
    
    # While we are at it,store the bugzilla login/passwd also
    # in the self object.This is as better place as any!!
    
    self.bzusername  =  bzusername
    self.bzpasswd  =  bzpasswd
    
    try:
         self.conn  =  MySQLdb.connect (host  =  self.rhost,
                                        port  =  self.rport,
                                        db  =  self.rdb,
                                        user  =  self.ruser,
                                        passwd  =  self.rpasswd)
    except MySQLdb.Error, e:
         print "Error %d: %s" % (e.args[0], e.args[1])
         sys.exit (1)
         
  
  def remote_get_data(self):  
    
    self.cursor  =  self.conn.cursor ()
    try:
      self.cursor.execute ("""
        SELECT d.*,
        b.bug_id,
        b.keywords,
        DATE_FORMAT(b.creation_ts, '%Y-%m-%d') 
        FROM bugs_security.dependencies d,
        bugs_security.bugs b
        WHERE b.bug_id  =  d.dependson
        AND b.keywords LIKE '%regression%'
        AND DATE_FORMAT(b.creation_ts, '%Y-%m-%d') > '2009-01-01'
        """)
    except  MySQLdb.Error, e:
      print "Error %d: %s" % (e.args[0], e.args[1])
      sys.exit (1)
  
  def data_handler(self):
    
    self.today  =  datetime.date.today()
    print "today is ", self.today
    while True:
      row  =  self.cursor.fetchone ()
      if row  ==  None:
        break
        
      
      # Write code here to take the zeroth and 2nd element ,
      # fetch the details of history and main body from bugzilla
      # and then calculate the fix2file as well as file2tag deltas.
      self.run_dates_delta_calculation(row[0], row[2])
    print "Number of rows returned: %d" % self.cursor.rowcount 
    self.cursor.close ()
    self.conn.close ()      
  
  def run_dates_delta_calculation(self, regressor, regression):
    
    self.regressor_details  =   self.fetch_all_info(regressor, 0)
    self.regression_details  =  self.fetch_all_info(regression, 1)
    
    # Get the regressor fix date, regression file date,regression tag date
    # etc.,
    
    if self.regression_details[0][0].startswith('0000-00-00'):
      regression_filedate = regression_tagdate = self.regression_details[1][2][:10]
    else:
      regression_filedate = self.regression_details[1][2][:10]
      regression_tagdate = self.regression_details[0][0][:10]
    regression_product = self.regression_details[1][0]
    regression_component = self.regression_details[1][1]
    
    regressor_fixdate = self.regressor_details[0][0][:10]
    fix2filedate = self.dates_delta(regression_filedate, regressor_fixdate)
    file2tagdate = self.dates_delta(regression_tagdate, regression_filedate)
    today = str(self.today.year)+'-'+str(self.today.month)+'-'+str(self.today.day)
    try:
      self.update_local_db(self.regressor, regressor_fixdate, self.regression,
                           regression_filedate, regression_tagdate,
                           fix2filedate, file2tagdate, today)
    except MySQLdb.Error, e:
         print "Error %d: %s" % (e.args[0], e.args[1])
         sys.exit (1)
      
  
  def fetch_all_info(self, bugid, flag):
    
    if flag  ==  0:
      self.regressor  =  bugid
      history = self.get_bug_history(self.regressor)
      details = self.get_bug_mainbody(self.regressor)
      hist_array = self.parse_regressor_history(history)
      detail_array = self.parse_regressor_details(details)
      
    else:
      self.regression  =  bugid
      history = self.get_bug_history(self.regression)
      details = self.get_bug_mainbody(self.regression)
      hist_array = self.parse_regression_history(history)
      detail_array = self.parse_regression_details(details)
    
    return hist_array,detail_array
  
  def get_bug_history(self,bugid):
    
    bugzilla_api_url = 'https://api-dev.bugzilla.mozilla.org/latest'
    url='%s/bug/%s/history?username=%s&password=%s' % (bugzilla_api_url, bugid, self.bzusername, self.bzpasswd)
    return json.load(urllib.urlopen(url))

  
  def get_bug_mainbody(self,bugid):
    
    bugzilla_api_url = 'https://api-dev.bugzilla.mozilla.org/latest'
    url='%s/bug/%s?username=%s&password=%s' %(bugzilla_api_url, bugid, self.bzusername, self.bzpasswd)
    return json.load(urllib.urlopen(url))
    
  
  def parse_regressor_history(self, buff):
    
    for h in buff['history']:
      for c  in h['changes']:
        if c['field_name']  ==  'resolution' and  c['added'].upper().startswith('FIXED') !=  -1:
          return [h['change_time'], c['field_name'] , c['added']]
    # if the bug is still not FIXED, like one of those tracker bugs
    # return a date of FIX from the future.
    return [u'2020-12-12T05:22:42Z', u'resolution', u'FIXED']
  
  def parse_regressor_details(self, buff):
    
    return [buff['product'], buff['component'], buff['creation_time']]
     
  
  def parse_regression_history(self, buff):
    
    for h in buff['history']:
      for c in h['changes']:
        if c['field_name']  ==  'keywords' and  c['added'].find('regression') !=  -1:
          return [h['change_time'], c['field_name'] , c['added']]
    # if the bug is created as REGRESSION, history does not contain the
    # search strings.return 0000-00-00 for parsing upstream...
    return [u'0000-00-00T00:00:00Z', u'keywords', u'regression']
  
  
  def parse_regression_details(self, buff):
    
    return [buff['product'], buff['component'], buff['creation_time']]
     

  
  def update_local_db(self,regressor,fixdate,regression,creationdate,tagdate,fix2file,file2tag,dayofrecord):
    
    try:
       self.cursorl.execute("""
                          INSERT INTO  RegressionRangesStudy VALUES ( %s, %s, %s, %s, %s, %s, %s, %s)""", (regressor ,fixdate,regression,
                                                                  creationdate,tagdate,fix2file,
                                                                  file2tag,dayofrecord))
    except  MySQLdb.Error, e:
      print "Error %d: %s" % (e.args[0], e.args[1])
      sys.exit (1)
    
     
  
  def create_local_table(self,luser,lpassword):
    
    try:
         self.connl  =  MySQLdb.connect (host  =  'localhost',
                                         user  =  luser,
                                         passwd  =  lpassword,
                                         db  =  'bugmetrics')
         
    except MySQLdb.Error, e:
         print "Error %d: %s" % (e.args[0], e.args[1])
         sys.exit (1)
    
    self.cursorl  =  self.connl.cursor ()
    try:
      self.cursorl.execute ("""
         CREATE TABLE IF NOT EXISTS
         RegressionRangesStudy
         (Regressor INT, FixDate DATE,
          Regression INT, CreationDate DATE,
          TagDate DATE,	Fix2File INT,
          File2Tag INT, dayofrecord DATE )
          """)
    except  MySQLdb.Error, e:
      print "Error %d: %s" % (e.args[0], e.args[1])
      sys.exit (1)

  
  def dates_delta(self,date1,date2):
    
    # calculate delta of dates between the given two dates.
    [y1, m1, d1] = date1.rsplit('-')
    [y2, m2, d2] = date2.rsplit('-')
    delta  =  datetime.date(int(y1), int(m1), int(d1)) - datetime.date(int(y2), int(m2), int(d2))
    return delta.days




# **** MAIN BODY OF THE CODE STARTS DOWN BELOW *****

# Before the program starts, I should have VPNed and SSH Tunneled
# to my local copy of BugZilla DB in a terminal ...

def main(rhost, rport, rdb, ruser, rpassword, luser, lpassword, bzusername, bzpasswd):
  dm = RegressionRangeCalculation()
  dm.remote_connection(rhost, rport, rdb, ruser, rpassword, bzusername, bzpasswd)
  dm.remote_get_data()
  dm.create_local_table(luser, lpassword)
  dm.data_handler()

# Handle our Command Line
defaults = {}
parser = OptionParser()

parser.add_option("--rhost", action="store", type="string", dest="rhost",
            help = "The remote DB host name or IP")
defaults["rhost"] = '127.0.0.1'

parser.add_option("--rport", action="store", type = "string", dest = "rport",
           help = "The port number for the remote DB host.")
defaults["rport"] = '3307'

parser.add_option("--rdb", action="store", type="string", dest = "rdb",
           help="Remote database name")
defaults["rdb"] = 'bugs_security'

parser.add_option("--ruser", action="store", type="string", dest="ruser",
           help="The remote database user name")
defaults["ruser"] = 'securitygroup'

parser.add_option("--rpassword", action="store", type="string", dest="rpassword",
           help="The remote database user password")

parser.add_option("--luser", action="store", type="string", dest="luser",
           help="The local database user name")
defaults["luser"] = 'root'

parser.add_option("--lpassword", action="store", type="string", dest="lpassword",
           help="The local database user password")

parser.add_option("--bzusername", action="store", type="string", dest="bzusername",
           help="Your Bugzilla user name which is usually an  email address!!")
defaults["bzusername"] = 'mnandigama@mozilla.com'

parser.add_option("--bzpasswd", action="store", type="string", dest="bzpasswd",
           help="The Bugzilla password")

parser.set_defaults(**defaults)




if __name__ == "__main__":
  (options, args) = parser.parse_args()
  main(options.rhost, options.rport, options.rdb,
       options.ruser, options.rpassword, options.luser,
       options.lpassword, options.bzusername, options.bzpasswd)
