import sys
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'builder'))
from build_pack import iter_bls,select_off,insert_records,norm,alias_for,off_record

class PackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.aliases=json.loads((Path(__file__).resolve().parents[1]/'builder'/'austria_aliases.json').read_text())
    def tearDown(self):self.tmp.cleanup()
    def test_bls_import_and_hebrew_search(self):
        w=Workbook();s=w.active
        s.append(['BLS Code','Lebensmittelbezeichnung','Food name','ENERCC Energy [kcal/100g]','PROT625 Protein [g/100g]','CHO Carbs [g/100g]','FAT Fat [g/100g]','SUGAR Sugars [g/100g]','FIBT Fiber [g/100g]'])
        s.append(['D123','Apfelstrudel gebacken','Apple strudel',220,3,31,9,16,2])
        s.append(['D124','Nonmatching Dish','Example dish',100,4,20,0,1,2])
        path=self.base/'bls.xlsx';w.save(path)
        records=list(iter_bls(path,self.aliases,'austria-only'))
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['he'],'שטרודל תפוחים')
        db=self.base/'out.sqlite';self.assertEqual(insert_records(db,records),1)
        con=sqlite3.connect(db)
        ids=con.execute('SELECT id FROM food_fts WHERE food_fts MATCH ?',('"שטרודל"*',)).fetchall()
        self.assertEqual(ids,[('bls:D123',)])
        self.assertEqual(con.execute('SELECT kcal_100 FROM foods').fetchone()[0],220)
        con.close()
    def test_off_quality_license_and_country(self):
        product={'code':'9000000000001','countries_tags':['en:austria'],
          'product_name_de':'Apfelstrudel','brands':'TestBrand','scans_n':150,
          'nutriments':{'energy-kcal_100g':240,'proteins_100g':3,'carbohydrates_100g':35,'fat_100g':10}}
        self.assertIsNotNone(off_record(product,self.aliases))
        product['countries_tags']=['en:france']
        self.assertIsNone(off_record(product,self.aliases))
        product['countries_tags']=['en:austria'];del product['nutriments']['proteins_100g']
        self.assertIsNone(off_record(product,self.aliases))
    def test_ranking_off_bulk_and_no_fake_values(self):
        p=self.base/'sample.jsonl';f=p.open('w')
        for i in range(4):
            f.write(json.dumps({'code':f'900000000000{i+1}','countries_tags':['en:austria'],
                'product_name_de':f'Sample {i}', 'scans_n':10*i,
                'nutriments':{'energy-kcal_100g':100+i,'proteins_100g':1,
                'carbohydrates_100g':10,'fat_100g':6}})+'\n')
        f.close()
        names=[x['de'] for x in select_off(p,self.aliases,2)]
        self.assertEqual(names,['Sample 3','Sample 2'])
    def test_no_unverified_hebrew_name(self):
        self.assertFalse(alias_for('completely unrelated',''.split()))

if __name__=='__main__':unittest.main()
