"""GEOADJUST 1D PDF layout, v2026-11-28.

Pure report presentation: does not modify least-squares computations.
A priori standard deviation is used as the single reported Std Dev (m),
consistent with the main STAR*NET adjusted elevation error-propagation table.
"""
import io
import os
from html import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, Table, TableStyle, KeepTogether

BLUE = colors.HexColor('#1E88E5')
BORDER = colors.HexColor('#D6DDE5')
PALE = colors.HexColor('#F5F8FC')
INK = colors.HexColor('#172331')


def _fonts():
    font_candidates = [
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
    ]
    for normal, bold in font_candidates:
        if os.path.isfile(normal) and os.path.isfile(bold):
            try:
                pdfmetrics.registerFont(TTFont('GeoRegular', normal))
                pdfmetrics.registerFont(TTFont('GeoBold', bold))
                pdfmetrics.registerFontFamily('GeoRegular', normal='GeoRegular', bold='GeoBold')
                return 'GeoRegular', 'GeoBold'
            except Exception:
                continue
    # Built-in font lacks some mathematical glyphs; prefer a compatible Unicode font.
    raise RuntimeError('Unicode PDF font not found. Install DejaVu Sans or Arial to render σ₀² and vᵀPv correctly.')


def _p(value, style):
    return Paragraph(escape(str(value)), style)


def _n(value, digits):
    try:
        if value is None or pd.isna(value):
            return '—'
        number = float(value)
        if abs(number) < 0.5 * 10**(-digits):
            number = 0.0
        return f'{number:.{digits}f}'
    except (TypeError, ValueError):
        return '—'


def _table(rows, widths, font_name, *, header=False, size=8, hpad=6, vpad=5):
    # Text inside Paragraph flowables naturally wraps instead of bleeding out of boxes.
    table = LongTable(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign='CENTER')
    directives = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.45, BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), hpad),
        ('RIGHTPADDING', (0, 0), (-1, -1), hpad),
        ('TOPPADDING', (0, 0), (-1, -1), vpad),
        ('BOTTOMPADDING', (0, 0), (-1, -1), vpad),
        ('ROWBACKGROUNDS', (0, 1 if header else 0), (-1, -1), [colors.white, PALE]),
    ]
    if header:
        directives.extend([
            ('BACKGROUND', (0, 0), (-1, 0), BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ])
    table.setStyle(TableStyle(directives))
    return table


def _is_bsfs(res_data, input_mode=None):
    if input_mode in ('bsfs', 'dh'):
        return input_mode == 'bsfs'
    df = res_data['residuals']
    if 'Backsight (m)' not in df.columns or 'Foresight (m)' not in df.columns:
        return False
    bs = pd.to_numeric(df['Backsight (m)'], errors='coerce')
    fs = pd.to_numeric(df['Foresight (m)'], errors='coerce')
    # Old calculation engine fills missing direct-dH BS/FS with zero.
    return bool(((bs.notna() & (bs != 0)) | (fs.notna() & (fs != 0))).any())


def generate_pdf_report(res_data, project_meta, input_mode=None):
    """Return A4 PDF bytes. input_mode='dh' hides BS/FS; 'bsfs' includes them."""
    reg, bold = _fonts()
    width, height = A4
    margin = 38
    content_width = width - 2 * margin
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=30, bottomMargin=35, title='GEOADJUST — 1D Levelling Adjustment Report')
    sty_title = ParagraphStyle('geo_title', fontName=bold, fontSize=15, leading=20, textColor=BLUE,
                               alignment=1, spaceAfter=3)
    sty_sub = ParagraphStyle('geo_sub', fontName=reg, fontSize=7.5, leading=11, alignment=1,
                             textColor=INK, spaceAfter=10)
    sty_section = ParagraphStyle('geo_section', fontName=bold, fontSize=11.3, leading=15,
                                 textColor=INK, spaceBefore=9, spaceAfter=5)
    sty_label = ParagraphStyle('geo_label', fontName=bold, fontSize=7.25, leading=9.3, textColor=INK)
    sty_cell = ParagraphStyle('geo_cell', fontName=reg, fontSize=7.5, leading=9.2, textColor=INK)
    sty_center = ParagraphStyle('geo_center', parent=sty_cell, alignment=1)
    sty_header = ParagraphStyle('geo_header', fontName=bold, fontSize=7.2, leading=9.5,
                                alignment=1, textColor=colors.white)
    sty_status = ParagraphStyle('geo_status', fontName=reg, fontSize=7, leading=9.2,
                                alignment=1, textColor=INK)
    sty_note = ParagraphStyle('geo_note', fontName=reg, fontSize=7, leading=10,
                              textColor=colors.HexColor('#526171'), spaceBefore=5)
    story = [Paragraph('GEOADJUST — 1D Levelling Adjustment Report', sty_title),
             Paragraph('Geodetic Network Least Squares Adjustment System (StarNet-Aligned Model)', sty_sub)]
    meta = [
        [_p('Project Name:',sty_label),_p(project_meta.get('name','—'),sty_cell),
         _p('Date:',sty_label),_p(project_meta.get('date','—'),sty_cell)],
        [_p('Instrument:',sty_label),_p(project_meta.get('instrument','—'),sty_cell),
         _p('Observer:',sty_label),_p(project_meta.get('observer','—'),sty_cell)],
    ]
    meta_table = Table(meta, colWidths=[89, 174, 72, content_width-335])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.6,BORDER),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]))
    story.append(meta_table)

    story.append(Paragraph('Adjustment Statistical Summary',sty_section))
    stat_rows = [
        ('Number of Stations:',res_data.get('num_stations','—'),'Instrument Std Error:',f"{res_data.get('instrument_std',0.003):.3f} m/√km"),
        ('Number of Observations:',res_data.get('num_obs','—'),'Number of Unknowns:',res_data.get('num_unknowns','—')),
        ('Number of Redundant Observations:',res_data.get('dof','—'),'Error Factor (σ₀):',_n(res_data.get('sigma0'),6)),
        ('Sum of Squares (vᵀPv):',_n(res_data.get('vTpv'),6),'Chi-Square Test (5%):',res_data.get('chi2_status','—')),
        ('A Posteriori Variance (σ₀²):',_n(res_data.get('sigma0_sq'),6),'Chi-Square Bounds:',
         f"{_n(res_data.get('chi2_lower'),6)} / {_n(res_data.get('chi2_upper'),6)}"),
    ]
    stat_table = _table([[_p(a,sty_label),_p(b,sty_cell),_p(c,sty_label),_p(d,sty_cell)]
                         for a,b,c,d in stat_rows],
                        [170,65,143,content_width-378],reg,size=7.2,hpad=5,vpad=3)
    story.append(stat_table)

    story.append(Paragraph('Adjusted Elevations and Error Propagation (Meters)',sty_section))
    station_cols = ['Station', 'Adjusted RL (m)', 'Std Dev (m)', '95% CI (m)', 'Status']
    station_rows = [[_p(x,sty_header) for x in station_cols]]
    for _,r in res_data['stations'].iterrows():
        # StarNet's primary StdDev column is a priori; retain the existing results unmodified.
        std = r.get('Prior StdDev (m)',r.get('Std Dev (m)',0))
        station_rows.append([
            _p(r.get('Station','—'),sty_center),_p(_n(r.get('Adjusted RL (m)'),4),sty_center),
            _p(_n(std,6),sty_center),_p(_n(r.get('95% CI (m)'),6),sty_center),
            _p(r.get('Status','—'),sty_status),
        ])
    station_widths = [67,100,93,91,content_width-351]
    story.append(_table(station_rows,station_widths,reg,header=True,hpad=4,vpad=3))

    story.append(Paragraph('Adjusted Observations and Residuals',sty_section))
    bsfs = _is_bsfs(res_data,input_mode)
    columns = [('From','From',None),('To','To',None)]
    if bsfs:
        columns += [('Backsight (m)','Backsight (m)',4),('Foresight (m)','Foresight (m)',4)]
    columns += [('Diff in Height (m)','Diff in Height (m)',4),('Distance (m)','Distance (m)',4),
                ('StdErr (m)','StdErr (m)',4),('Residual (m)','Residual (m)',4)]
    obs = res_data['residuals']
    if bsfs:
        widths = [43,43,67,67,79,77,67,content_width-443]
    else:
        widths = [61,61,100,99,97,content_width-418]
    res_rows = [[_p(name,sty_header) for name,_,_ in columns]]
    for _,r in obs.iterrows():
        res_rows.append([_p(_n(r.get(key),digits) if digits is not None else r.get(key,'—'),sty_center)
                         for _,key,digits in columns])
    story.append(_table(res_rows,widths,reg,header=True,hpad=3,vpad=3))
    story.append(Paragraph('Reporting note: Std Dev (m) is the propagated a priori station standard deviation. '
                           'Residuals are rounded to 0.0001 m for display only; statistical tests use the unrounded calculation results.', sty_note))

    def footer(canvas, pdf_doc):
        canvas.saveState()
        canvas.setFont(reg,7)
        canvas.setFillColor(colors.HexColor('#687889'))
        canvas.drawString(margin,23,'GEOADJUST Geodetic Network Adjustment Toolkit')
        canvas.drawRightString(width-margin,23,f'Page {pdf_doc.page}')
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
