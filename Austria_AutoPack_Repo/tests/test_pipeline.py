import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from openpyxl import Workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'builder'))
from verify_release import check_pack

class PipelineTests(unittest.TestCase):
    def test_end_to_end_with_synthetic_fixtures_not_for_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);ws=Workbook().active
            ws.append(['BLS Code','Lebensmittelbezeichnung','Food name','ENERCC Energie [kcal/100g]','PROT625 Protein [g/100g]','CHO Carbs [g/100g]','FAT Fat [g/100g]','SUGAR Sugars [g/100g]','FIBT Fiber [g/100g]'])
            ws.append(['D123456','Apfelstrudel gebacken','Apple strudel',220,3,31,9,16,2])
            wb=ws.parent;f=d/'BLS_4_0_Daten_2025_DE.xlsx';wb.save(f)
            with zipfile.ZipFile(d/'BLS.zip','w') as z:z.write(f,arcname='BLS_4_0_Daten_2025_DE.xlsx')
            off=d/'off.jsonl'
            off.write_text(json.dumps({'code':'9000000000001','countries_tags':['en:austria'],'product_name_de':'Apfelstrudel','nutriments':{'energy-kcal_100g':240,'proteins_100g':3,'carbohydrates_100g':35,'fat_100g':10}})+'\n',encoding='utf-8')
            out=d/'dist'
            r=subprocess.run([sys.executable,str(ROOT/'builder'/'build_pack.py'),'--bls',str(d/'BLS.zip'),'--off',str(off),'--max-off','1','--out',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr)
            self.assertEqual(check_pack(out/'Austria-BLS-4.0.dthpack',1,'BLS-4.0')['records'],1)
            self.assertEqual(check_pack(out/'Austria-OpenFoodFacts.dthpack',1,'OpenFoodFacts')['records'],1)
            self.assertNotEqual((out/'Austria-BLS-4.0.dthpack').read_bytes(),(out/'Austria-OpenFoodFacts.dthpack').read_bytes())

if __name__=='__main__':unittest.main()
