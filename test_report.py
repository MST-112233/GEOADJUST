import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from network_1d import adjust_1d_network
from geoadjust_pdf_report import generate_pdf_report

raw=[('BM3','C12',-.4525,32.1495),('C12','C13',-.9941,52.133),('C13','C14',-.2779,20.15),('C14','C15',-.9121,36.348),('C15','BM4',.7017,38.3865),('BM4','C16',-.7017,38.385),('C16','C17',1.095,48.3145),('C17','C18',-.0003,48.308),('C18','C19',.9529,50.009),('C19','BM3',.5893,36.047)]
frame=pd.DataFrame(raw,columns=['From','To','Diff in Height (m)','Distance (m)'])
result=adjust_1d_network(frame,'BM3',50.049,0.003)
meta={'name':'TEST2_27_11_26','instrument':'Leica NA320','observer':'tan','date':'2026-11-27'}
folder=Path(__file__).resolve().parent
for mode in ('dh','bsfs'):
    r=result.copy()
    if mode=='bsfs':
        df=r['residuals'].copy()
        df['Backsight (m)']=1.5
        df['Foresight (m)']=1.5-df['Diff in Height (m)']
        r['residuals']=df
    pdf=generate_pdf_report(r,meta,mode)
    dest=folder/f'GEOADJUST_TEST2_{mode.upper()}_sample.pdf'
    dest.write_bytes(pdf)
    print(dest,len(pdf))
    import fitz
    document=fitz.open(dest)
    print('pages',len(document),'size',document[0].rect)
    text='\n'.join(page.get_text() for page in document)
    for expected in ('Number of Unknowns','Number of Redundant Observations','σ₀²','vᵀPv','Std Dev (m)','Residual (m)'):
        assert expected in text,expected
    assert ('Backsight (m)' in text)==(mode=='bsfs')
    assert 'Observed dH' not in text
    assert 'Adjusted dH' not in text
    assert 'Prior StdDev' not in text
    assert 'Posterior StdDev' not in text
    assert '50.0490' in text
    # ensure no text outside usable page rect
    for pg in document:
        for word in pg.get_text('words'):
            assert word[0]>=5 and word[2]<=pg.rect.width-5,word
    document[0].get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False).save(folder/f'preview_{mode}.png')
