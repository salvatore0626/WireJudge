"""Dependency-free Excel score exports to the user's Downloads folder."""
from pathlib import Path
from datetime import datetime
import os,re,zipfile
from xml.sax.saxutils import escape
from scoring import maximum

def downloads_folder():
    if os.name=='nt':
        # Windows Known Folder API respects redirected Downloads folders.
        import ctypes,uuid
        guid=(ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID('374DE290-123F-4565-9164-39C4925E467B').bytes_le)
        pointer=ctypes.c_void_p()
        shell=ctypes.windll.shell32;ole=ctypes.windll.ole32
        shell.SHGetKnownFolderPath.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
        shell.SHGetKnownFolderPath.restype=ctypes.c_long
        ole.CoTaskMemFree.argtypes=[ctypes.c_void_p]
        try:
            if shell.SHGetKnownFolderPath(ctypes.byref(guid),0,None,ctypes.byref(pointer))==0:
                return Path(ctypes.wstring_at(pointer))
        finally:
            if pointer.value:ole.CoTaskMemFree(pointer)
    return Path.home()/'Downloads'

def export_scores(attempts,scores,wires,numbers,settings,replay):
    if not attempts:raise ValueError('Select at least one attempt.')
    components=[('loc','Localizer'),('glide','Glide'),('aoa','AoA'),('wire','Wire Points'),('total','Total')]
    if settings.recovery_case==3:components=[('position','Platform Position'),('speed','Platform Speed')]+components
    headers=['Player','Attempt','Aircraft','Case','Wire']+[label for _,label in components]+['Maximum']
    rows=[];provisional_rows=set()
    for a in attempts:
        score=scores.get(a.edit_id)
        if score and not score.complete:provisional_rows.add(len(rows)+2)
        rows.append([a.player,numbers[a.edit_id],a.aircraft,settings.recovery_case,wires.get(a.edit_id,'') or 'Not set']+
                    [round(getattr(score,key),1) if score else None for key,_ in components]+
                    [maximum(settings)])
    def column(index):
        name=''
        while index:index,remainder=divmod(index-1,26);name=chr(65+remainder)+name
        return name
    def cell(value,address,style):
        if value is None:return f'<c r="{address}" s="{style}"/>'
        if isinstance(value,(float,int)):return f'<c r="{address}" s="{style}"><v>{value}</v></c>'
        text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))
        return f'<c r="{address}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'
    data=[]
    for number,row in enumerate([headers]+rows,1):
        provisional=number in provisional_rows
        cells=[]
        for index,value in enumerate(row,1):
            style=1 if number==1 else (4 if provisional else 3) if isinstance(value,(float,int)) and index>5 else 2 if provisional else 0
            cells.append(cell(value,f'{column(index)}{number}',style))
        data.append(f'<row r="{number}" ht="24" customHeight="1">'+''.join(cells)+'</row>')
    last=f'{column(len(headers))}{len(rows)+1}'
    widths=''.join(f'<col min="{i}" max="{i}" width="{28 if i==1 else 23 if i==3 else 20 if i>5 else 16}" customWidth="1"/>' for i in range(1,len(headers)+1))
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    sheet=f'<worksheet xmlns="{ns}"><dimension ref="A1:{last}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{widths}</cols><sheetData>'+''.join(data)+f'</sheetData><autoFilter ref="A1:{last}"/></worksheet>'
    styles=f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF24374D"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFCE76"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"/><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="2" fontId="0" fillId="3" borderId="0" xfId="0" applyNumberFormat="1" applyFill="1"/></cellXfs></styleSheet>'
    styles=styles.replace('<fonts count="2">','<numFmts count="1"><numFmt numFmtId="164" formatCode="0.0"/></numFmts><fonts count="2">').replace('numFmtId="2"','numFmtId="164"').replace('</styleSheet>','<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    office='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    files={
        '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{office}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml':f'<workbook xmlns="{ns}" xmlns:r="{office}"><sheets><sheet name="Scores" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{office}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{office}/styles" Target="styles.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml':sheet,'xl/styles.xml':styles}
    folder=downloads_folder();folder.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^\w.-]+','_',Path(replay).stem if replay else 'Replay')[:100]
    name=f'WireJudge_{stem}_Case{settings.recovery_case}_{datetime.now():%Y%m%d_%H%M%S}'
    suffix=0
    while True:
        path=folder/(name+(f'_{suffix}' if suffix else '')+'.xlsx')
        try:stream=path.open('xb');break
        except FileExistsError:suffix+=1
    try:
        with stream,zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,contents in files.items():archive.writestr(name,'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+contents)
    except Exception:
        path.unlink(missing_ok=True);raise
    return path
