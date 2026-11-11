import unittest
from opportunity_metrics import framework
from analytics import projection

class Opportunity(unittest.TestCase):
 def test_opportunities_and_receiving_components(self):
  pairs=[({'stats':{'Targets':10,'Receptions':6},'venue':'home'},60),({'stats':{'Targets':5,'Receptions':4},'venue':'away'},40)]*5
  model={'unit':'Targets','base_projection':50,'adjustments':{'venue':1,'weather':.98}}
  a=framework(pairs,'Receiving yards','NFL',model)
  self.assertEqual(a['sample']['games'],10)
  self.assertAlmostEqual(a['sample']['rate'],100/15)
  self.assertAlmostEqual(a['receiving']['catch_rate'],10/15)
  self.assertEqual(a['receiving']['yards_per_reception'],10)
  self.assertEqual(a['windows']['20']['games'],10)
  self.assertEqual(a['splits']['home']['games'],5)
  self.assertIn('EPA',a['missing'])
 def test_missing_exposures_stay_missing(self):
  pairs=[({'stats':{},'venue':'home'},12)]*5
  a=framework(pairs,'Points','NBA',{'unit':'Games','base_projection':12,'adjustments':{}})
  self.assertIsNone(a['sample']['rate'])
  self.assertEqual(a['splits']['away']['games'],0)
  self.assertIsNone(a['splits']['away']['mean'])
  self.assertEqual(a['median'],12)
 def test_framework_does_not_mutate_forecast(self):
  pairs=[({'stats':{'Minutes':30},'venue':'home','event_id':str(i)},15+i) for i in range(10)]
  m=projection(pairs,'Points','NBA',{'venue':'home'}, {'available':True,'multiplier':1.04},'Active',[],{})
  before=m.copy();a=framework(pairs,'Points','NBA',m)
  self.assertEqual(before,m)
  self.assertAlmostEqual(a['base_projection']*1.04,m['mu'])
if __name__=='__main__':unittest.main()
