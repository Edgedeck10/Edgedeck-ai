import unittest
from history_window import select
class WindowTests(unittest.TestCase):
 def test_small_sample_retained(self):
  x=[({'stats':{'Minutes':30}},15)]*8
  rows,a=select(x,'Points','NBA');self.assertEqual(rows,x);self.assertEqual(a['validation_games'],0)
 def test_equal_dates_and_larger_tie(self):
  x=[({'stats':{'Minutes':30}},15)]*40
  rows,a=select(x,'Points','NBA');self.assertEqual(len(rows),30);self.assertEqual({s['validation_games'] for s in a['candidates']},{10})
 def test_predict_before_outcome(self):
  x=[({'stats':{'Minutes':30}},15)]*39+[({'stats':{'Minutes':30}},100)]
  _,a=select(x,'Points','NBA');self.assertTrue(all(s['mae']==8.5 for s in a['candidates']))
