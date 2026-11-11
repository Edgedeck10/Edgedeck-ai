import unittest,datetime as dt
import news_feed as n
class News(unittest.TestCase):
 def test_matching_and_failed_fetch_stale_status(self):
  now=dt.datetime(2026,11,11,12,tzinfo=dt.timezone.utc)
  feed=n.collect({'NBA':'basketball/nba'},None,lambda jobs:[('NBA',{'articles':[{'headline':'Starter out with injury','published':now.isoformat(),'links':{'web':{'href':'https://espn.com/story'}},'categories':[{'team':{'id':1}}]}]})],now,{})
  event={'sport':'NBA','home':{'id':'1','name':'One'},'away':{'id':'2','name':'Two'}}
  self.assertEqual(len(n.for_event(event,feed)),1);self.assertTrue(feed['NBA']['articles'][0]['impact_review'])
  missing=n.collect({'NBA':'basketball/nba'},None,lambda jobs:[],now,{'news':feed})
  self.assertIn('failed',missing['NBA']['status']);self.assertEqual(missing['NBA']['articles'],feed['NBA']['articles'])
 def test_review_does_not_change_original(self):
  leg={'id':'x','event_id':'NBA:1','sport':'NBA','odds':-110};ticket={'legs':[leg.copy()]}
  review=n.review(ticket,[leg|{'odds':-150,'probability':.65}],{'NBA:1':{'sport':'NBA','state':'pre'}},[],{'NBA':{'status':'Public feed collected','articles':[]}},'now')
  self.assertEqual(ticket['legs'][0]['odds'],-110);self.assertIn('Price changed',review[0]['alerts'][0])
if __name__=='__main__':unittest.main()
