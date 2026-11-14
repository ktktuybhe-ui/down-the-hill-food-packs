"""Synthetic fixture only: tests container integrity, not actual food nutrition."""
import tempfile,sys,sqlite3,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'builder'))
from build_pack import insert_records
from export_dthpack import export,verify

class EnvelopeTests(unittest.TestCase):
    def test_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);db=root/'bls.sqlite';out=root/'Austria-BLS.dthpack'
            rec={'id':'bls:TEST','source':'BLS-4.0','source_id':'TEST','de':'Testgericht','en':'Test dish','he':'',
                'n':{'kcal':100,'protein':5,'carbs':10,'fat':4,'sugar':None,'fiber':None},
                'search':'Testgericht test dish','flags':[],'url':'https://blsdb.de/'}
            insert_records(db,[rec])
            result=export(db,out)
            self.assertEqual(result['count'],1)
            self.assertEqual(verify(out)['count'],1)
            contents=bytearray(out.read_bytes());contents[-1]^=1;out.write_bytes(contents)
            with self.assertRaises(ValueError):verify(out)

if __name__=='__main__':unittest.main()
