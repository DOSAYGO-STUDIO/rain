import tempfile
from pathlib import Path
import unittest
from campaign import inspect_log

class ParseTests(unittest.TestCase):
    def inspect(self,text):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run.log'; path.write_text(text)
            return inspect_log(path)
    def test_partial_is_not_pass(self):
        self.assertFalse(self.inspect('Overall result: pass ( 1 / 1 passed)')['complete_log'])
        self.assertFalse(self.inspect('Verification value is 0x01 - Testing took 1.0 seconds')['complete_log'])
    def test_complete_failure(self):
        x=self.inspect('[[[ BadSeeds Tests ]]]\nOverall result: FAIL ( 240 / 241 passed)\nVerification value is 0x01 - Testing took 12.34 seconds')
        self.assertTrue(x['complete_log']); self.assertEqual(x['reported_result'],'FAIL')
        self.assertEqual(x['total_checks'],241); self.assertEqual(x['elapsed_test_seconds'],12.34)
    def test_performance_units(self):
        x=self.inspect('Average - 137.91 cycles/hash\nAverage - 0.62 bytes/cycle - 2.02 GiB/sec @ 3.5 ghz')
        self.assertEqual(x['small_cycles_per_hash'],137.91)
        self.assertEqual(x['bulk_bytes_per_cycle'],[.62])
        self.assertEqual(x['bulk_gib_per_second_at_reference_3_5ghz'],[2.02])

if __name__=='__main__': unittest.main()
