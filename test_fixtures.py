import unittest,datetime as dt
from extra_fixtures import extract
class Fixtures(unittest.TestCase):
 def test_nested_match_and_outside_week(self):
  now=dt.datetime(2026,11,11,tzinfo=dt.timezone.utc)
  payload={'events':[{'name':'Tournament','date':'2026-11-14T12:00Z','groupings':[{'competitions':[{'id':'m1','competitors':[{'athlete':{'displayName':'Player A'}},{'athlete':{'displayName':'Player B'}}]}]}]},{'name':'Later','date':'2026-12-01T12:00Z','competitors':[{'athlete':{'displayName':'A'}}]}]}
  rows=extract(payload,'ATP',now);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['event'],'Player A vs Player B');self.assertNotIn('probability',rows[0])
 def test_unknown_timezone_is_not_invented(self):
  now=dt.datetime(2026,11,11,tzinfo=dt.timezone.utc)
  self.assertEqual(extract({'events':[{'id':'tbd','date':'2026-11-14','competitors':[{'athlete':{'displayName':'A'}}]}]},'ATP',now),[])
if __name__=='__main__':unittest.main()
